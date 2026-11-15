// SPDX-License-Identifier: GPL-2.0-only
/*
 * PMI632 battery telemetry and charger-state monitor for ginkgo.
 * Register definitions follow Xiaomi ginkgo-p-oss qg-reg.h, qg-util.c and
 * smb5-reg.h. This does not configure charging, implement the CAF fuel-gauge
 * algorithm, or negotiate USB power.
 */
#include <linux/bitops.h>
#include <linux/bits.h>
#include <linux/errno.h>
#include <linux/jiffies.h>
#include <linux/math64.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>
#include <linux/workqueue.h>

#define QG_PERPH_TYPE			0x04
#define QG_PERPH_SUBTYPE			0x05
#define QG_TYPE				0x0d
#define QG_ADC_IBAT_5A			0x03
#define QG_ADC_IBAT_10A			0x04
#define QG_STATUS1			0x08
#define QG_BATT_PRESENT_BIT		BIT(0)
#define QG_DATA_CTL2			0x42
#define QG_BURST_AVG_HOLD			BIT(0)
#define QG_LAST_ADC_V			0xc0
#define QG_LAST_BURST_AVG_I		0xc6
#define QG_V_LSB_NV			194637
#define QG_I_LSB_5A_NA			152588
#define QG_I_LSB_10A_NA			305176

#define PMI632_CHGR_STATUS1		0x1006
#define PMI632_CHGR_STATUS_MASK		GENMASK(2, 0)
#define PMI632_CHGR_INHIBIT		0
#define PMI632_CHGR_TRICKLE		1
#define PMI632_CHGR_PRE			2
#define PMI632_CHGR_FULLON		3
#define PMI632_CHGR_TAPER			4
#define PMI632_CHGR_TERMINATE		5
#define PMI632_CHGR_PAUSE			6
#define PMI632_CHGR_DISABLE		7
#define PMI632_POWER_PATH_STATUS		0x110b
#define PMI632_USE_USBIN			BIT(4)
#define PMI632_VALID_INPUT_POWER		BIT(0)
#define PMI632_USBIN_INT_RT_STS		0x1310
#define PMI632_USBIN_PLUGIN		BIT(4)
#define PMI632_POLL_MS			2000
#define PMI632_TELEMETRY_MS		30000

static bool estimate_capacity;
module_param(estimate_capacity, bool, 0444);
MODULE_PARM_DESC(estimate_capacity,
	"Expose an approximate 3.4-4.35 V linear capacity estimate (default off)");

struct pmi632_qg {
	struct device *dev;
	struct regmap *regmap;
	/* Serializes property reads, polling and the burst HOLD transaction. */
	struct mutex lock;
	u32 base;
	u32 i_lsb_na;
	struct power_supply *psy;
	struct power_supply *psy_usb;
	struct delayed_work poll_work;
	int last_present;
	int last_usb_present;
	int last_online;
	int last_status;
	unsigned long next_telemetry;
};

static int qg_read16(struct pmi632_qg *qg, u32 off, u16 *val)
{
	u8 buf[2];
	int ret;

	ret = regmap_bulk_read(qg->regmap, qg->base + off, buf, sizeof(buf));
	if (ret)
		return ret;
	*val = buf[0] | ((u16)buf[1] << 8);
	return 0;
}

static int qg_read_present(struct pmi632_qg *qg, int *present)
{
	unsigned int val;
	int ret;

	ret = regmap_read(qg->regmap, qg->base + QG_STATUS1, &val);
	if (!ret)
		*present = !!(val & QG_BATT_PRESENT_BIT);
	return ret;
}

static int qg_read_voltage(struct pmi632_qg *qg, int *uv)
{
	u16 raw;
	int ret;

	ret = qg_read16(qg, QG_LAST_ADC_V, &raw);
	if (ret)
		return ret;
	/* Do not turn an empty/invalid ADC result into a valid empty battery. */
	if (!raw || raw == 0xffff)
		return -ENODATA;
	*uv = div_u64((u64)raw * QG_V_LSB_NV, 1000);
	return 0;
}

/* Caller holds lock across HOLD, sample and release, including failures. */
static int qg_read_current(struct pmi632_qg *qg, int *ua)
{
	u16 raw;
	int ret, release_ret;

	ret = regmap_update_bits(qg->regmap, qg->base + QG_DATA_CTL2,
				 QG_BURST_AVG_HOLD, QG_BURST_AVG_HOLD);
	if (!ret)
		ret = qg_read16(qg, QG_LAST_BURST_AVG_I, &raw);
	/* Also attempt release if the HOLD write reported a bus error. */
	release_ret = regmap_update_bits(qg->regmap, qg->base + QG_DATA_CTL2,
					 QG_BURST_AVG_HOLD, 0);
	if (release_ret)
		dev_err_ratelimited(qg->dev, "cannot release QG sample hold: %d\n",
				    release_ret);
	if (ret || release_ret)
		return ret ? ret : release_ret;
	/* Hardware is discharge-positive; power_supply uses charge-positive. */
	*ua = -div_s64((s64)sign_extend32(raw, 15) * qg->i_lsb_na, 1000);
	return 0;
}

static int pmi632_read_usb(struct pmi632_qg *qg, int *present, int *online)
{
	unsigned int val;
	int ret;

	ret = regmap_read(qg->regmap, PMI632_USBIN_INT_RT_STS, &val);
	if (ret)
		return ret;
	*present = !!(val & PMI632_USBIN_PLUGIN);
	*online = 0;
	if (!*present)
		return 0;
	ret = regmap_read(qg->regmap, PMI632_POWER_PATH_STATUS, &val);
	if (!ret)
		*online = !!(val & PMI632_USE_USBIN) &&
			  !!(val & PMI632_VALID_INPUT_POWER);
	return ret;
}

static int pmi632_read_status(struct pmi632_qg *qg, int present,
			      int online, int *status)
{
	unsigned int val;
	int ret;

	if (!present) {
		*status = POWER_SUPPLY_STATUS_DISCHARGING;
		return 0;
	}
	ret = regmap_read(qg->regmap, PMI632_CHGR_STATUS1, &val);
	if (ret)
		return ret;
	switch (val & PMI632_CHGR_STATUS_MASK) {
	case PMI632_CHGR_TRICKLE:
	case PMI632_CHGR_PRE:
	case PMI632_CHGR_FULLON:
	case PMI632_CHGR_TAPER:
		*status = online ? POWER_SUPPLY_STATUS_CHARGING :
				   POWER_SUPPLY_STATUS_DISCHARGING;
		break;
	case PMI632_CHGR_INHIBIT:
	case PMI632_CHGR_TERMINATE:
		*status = POWER_SUPPLY_STATUS_FULL;
		break;
	case PMI632_CHGR_PAUSE:
	case PMI632_CHGR_DISABLE:
		*status = online ? POWER_SUPPLY_STATUS_NOT_CHARGING :
				   POWER_SUPPLY_STATUS_DISCHARGING;
		break;
	default:
		*status = POWER_SUPPLY_STATUS_UNKNOWN;
		break;
	}
	return 0;
}

static int qg_get_property(struct power_supply *psy,
			   enum power_supply_property psp,
			   union power_supply_propval *val)
{
	struct pmi632_qg *qg = power_supply_get_drvdata(psy);
	int ret, uv, present, online;

	mutex_lock(&qg->lock);
	switch (psp) {
	case POWER_SUPPLY_PROP_PRESENT:
		ret = qg_read_present(qg, &val->intval);
		break;
	case POWER_SUPPLY_PROP_VOLTAGE_NOW:
		ret = qg_read_voltage(qg, &val->intval);
		break;
	case POWER_SUPPLY_PROP_CURRENT_NOW:
		ret = qg_read_current(qg, &val->intval);
		break;
	case POWER_SUPPLY_PROP_CAPACITY:
		/* SOC_MONOTONIC is software-written, not an autonomous SOC gauge. */
		ret = -ENODATA;
		if (!estimate_capacity)
			break;
		ret = qg_read_voltage(qg, &uv);
		if (!ret)
			val->intval = clamp((uv - 3400000) / 9500, 0, 100);
		break;
	case POWER_SUPPLY_PROP_STATUS:
		ret = pmi632_read_usb(qg, &present, &online);
		if (!ret)
			ret = pmi632_read_status(qg, present, online, &val->intval);
		break;
	default:
		ret = -EINVAL;
		break;
	}
	mutex_unlock(&qg->lock);
	return ret;
}

static enum power_supply_property qg_props[] = {
	POWER_SUPPLY_PROP_PRESENT,
	POWER_SUPPLY_PROP_STATUS,
	POWER_SUPPLY_PROP_CAPACITY,
	POWER_SUPPLY_PROP_VOLTAGE_NOW,
	POWER_SUPPLY_PROP_CURRENT_NOW,
};

static const struct power_supply_desc qg_desc = {
	.name = "qcom-battery",
	.type = POWER_SUPPLY_TYPE_BATTERY,
	.properties = qg_props,
	.num_properties = ARRAY_SIZE(qg_props),
	.get_property = qg_get_property,
};

static enum power_supply_property qg_usb_props[] = {
	POWER_SUPPLY_PROP_ONLINE,
	POWER_SUPPLY_PROP_PRESENT,
	POWER_SUPPLY_PROP_USB_TYPE,
};

static int qg_usb_get_property(struct power_supply *psy,
			       enum power_supply_property psp,
			       union power_supply_propval *val)
{
	struct pmi632_qg *qg = power_supply_get_drvdata(psy);
	unsigned int stat;
	int present, online, ret;

	if (psp == POWER_SUPPLY_PROP_USB_TYPE) {
		val->intval = POWER_SUPPLY_USB_TYPE_UNKNOWN;
		return 0;
	}
	if (psp != POWER_SUPPLY_PROP_ONLINE && psp != POWER_SUPPLY_PROP_PRESENT)
		return -EINVAL;
	mutex_lock(&qg->lock);
	if (psp == POWER_SUPPLY_PROP_PRESENT) {
		ret = regmap_read(qg->regmap, PMI632_USBIN_INT_RT_STS, &stat);
		if (!ret)
			val->intval = !!(stat & PMI632_USBIN_PLUGIN);
	} else {
		ret = pmi632_read_usb(qg, &present, &online);
		if (!ret)
			val->intval = online;
	}
	mutex_unlock(&qg->lock);
	return ret;
}

static const struct power_supply_desc qg_usb_desc = {
	.name = "qcom-usb",
	.type = POWER_SUPPLY_TYPE_USB,
	.usb_types = BIT(POWER_SUPPLY_USB_TYPE_UNKNOWN),
	.properties = qg_usb_props,
	.num_properties = ARRAY_SIZE(qg_usb_props),
	.get_property = qg_usb_get_property,
};

static void pmi632_poll_work(struct work_struct *work)
{
	struct pmi632_qg *qg = container_of(to_delayed_work(work),
						 struct pmi632_qg, poll_work);
	bool battery_changed = false, usb_changed = false;
	int present, online, status, ret;

	mutex_lock(&qg->lock);
	ret = pmi632_read_usb(qg, &present, &online);
	if (!ret) {
		usb_changed = present != qg->last_usb_present ||
			      online != qg->last_online;
		qg->last_usb_present = present;
		qg->last_online = online;
		ret = pmi632_read_status(qg, present, online, &status);
		if (!ret) {
			battery_changed = status != qg->last_status;
			qg->last_status = status;
		}
	}
	if (ret)
		dev_err_ratelimited(qg->dev, "charger status read failed: %d\n", ret);
	ret = qg_read_present(qg, &present);
	if (!ret) {
		battery_changed |= present != qg->last_present;
		qg->last_present = present;
	} else {
		dev_err_ratelimited(qg->dev, "battery presence read failed: %d\n", ret);
	}
	/* Gauge telemetry is requested by consumers, never by this fast poll. */
	if (time_after_eq(jiffies, qg->next_telemetry)) {
		battery_changed = true;
		qg->next_telemetry = jiffies + msecs_to_jiffies(PMI632_TELEMETRY_MS);
	}
	mutex_unlock(&qg->lock);
	/* The core may call get_property(); never notify with lock held. */
	if (battery_changed || usb_changed)
		power_supply_changed(qg->psy);
	if (usb_changed)
		power_supply_changed(qg->psy_usb);
	queue_delayed_work(system_freezable_wq, &qg->poll_work,
			   msecs_to_jiffies(PMI632_POLL_MS));
}

static void pmi632_qg_cancel_work(void *data)
{
	struct pmi632_qg *qg = data;

	cancel_delayed_work_sync(&qg->poll_work);
}

static int pmi632_qg_probe(struct platform_device *pdev)
{
	struct power_supply_config psy_cfg = {};
	struct pmi632_qg *qg;
	unsigned int type;
	int ret;

	qg = devm_kzalloc(&pdev->dev, sizeof(*qg), GFP_KERNEL);
	if (!qg)
		return -ENOMEM;
	qg->dev = &pdev->dev;
	qg->regmap = dev_get_regmap(pdev->dev.parent, NULL);
	if (!qg->regmap)
		return dev_err_probe(&pdev->dev, -ENODEV, "no parent regmap\n");
	mutex_init(&qg->lock);
	ret = of_property_read_u32(pdev->dev.of_node, "reg", &qg->base);
	if (ret)
		return ret;
	ret = regmap_read(qg->regmap, qg->base + QG_PERPH_TYPE, &type);
	if (ret)
		return dev_err_probe(&pdev->dev, ret, "QG type read\n");
	if (type != QG_TYPE)
		return dev_err_probe(&pdev->dev, -ENODEV, "not a QG peripheral\n");
	ret = regmap_read(qg->regmap, qg->base + QG_PERPH_SUBTYPE, &type);
	if (ret)
		return dev_err_probe(&pdev->dev, ret, "QG subtype read\n");
	switch (type) {
	case QG_ADC_IBAT_5A:
		qg->i_lsb_na = QG_I_LSB_5A_NA;
		break;
	case QG_ADC_IBAT_10A:
		qg->i_lsb_na = QG_I_LSB_10A_NA;
		break;
	default:
		return dev_err_probe(&pdev->dev, -ENODEV, "unsupported QG subtype\n");
	}
	qg->last_present = -1;
	qg->last_usb_present = -1;
	qg->last_online = -1;
	qg->last_status = -1;
	qg->next_telemetry = jiffies;
	INIT_DELAYED_WORK(&qg->poll_work, pmi632_poll_work);
	platform_set_drvdata(pdev, qg);
	psy_cfg.drv_data = qg;
	psy_cfg.fwnode = dev_fwnode(&pdev->dev);
	qg->psy = devm_power_supply_register(&pdev->dev, &qg_desc, &psy_cfg);
	if (IS_ERR(qg->psy))
		return dev_err_probe(&pdev->dev, PTR_ERR(qg->psy), "battery register\n");
	psy_cfg.fwnode = NULL;
	qg->psy_usb = devm_power_supply_register(&pdev->dev, &qg_usb_desc, &psy_cfg);
	if (IS_ERR(qg->psy_usb))
		return dev_err_probe(&pdev->dev, PTR_ERR(qg->psy_usb), "USB register\n");
	/* Added last: stop polling before devres unregisters either supply. */
	ret = devm_add_action_or_reset(&pdev->dev, pmi632_qg_cancel_work, qg);
	if (ret)
		return ret;
	queue_delayed_work(system_freezable_wq, &qg->poll_work, 0);
	dev_info(&pdev->dev, "PMI632 telemetry monitor at %#x\n", qg->base);
	return 0;
}

static int pmi632_qg_suspend(struct device *dev)
{
	pmi632_qg_cancel_work(dev_get_drvdata(dev));
	return 0;
}

static int pmi632_qg_resume(struct device *dev)
{
	struct pmi632_qg *qg = dev_get_drvdata(dev);

	qg->next_telemetry = jiffies;
	queue_delayed_work(system_freezable_wq, &qg->poll_work, 0);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(pmi632_qg_pm_ops,
			       pmi632_qg_suspend, pmi632_qg_resume);

static void pmi632_qg_shutdown(struct platform_device *pdev)
{
	pmi632_qg_cancel_work(platform_get_drvdata(pdev));
}

static const struct of_device_id pmi632_qg_of_match[] = {
	{ .compatible = "qcom,pmi632-qg" },
	{ }
};
MODULE_DEVICE_TABLE(of, pmi632_qg_of_match);

static struct platform_driver pmi632_qg_driver = {
	.probe = pmi632_qg_probe,
	.shutdown = pmi632_qg_shutdown,
	.driver = {
		.name = "qcom-pmi632-qg",
		.of_match_table = pmi632_qg_of_match,
		.pm = pm_sleep_ptr(&pmi632_qg_pm_ops),
	},
};
module_platform_driver(pmi632_qg_driver);

MODULE_DESCRIPTION("Qualcomm PMI632 battery telemetry and charger monitor");
MODULE_LICENSE("GPL");
