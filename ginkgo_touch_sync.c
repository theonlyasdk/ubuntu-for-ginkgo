#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/delay.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Antigravity");
MODULE_DESCRIPTION("Ginkgo Touchscreen Resume Sync Module");

static unsigned long addr_ts = 0xffffffea0e09c5a0;
static unsigned long addr_awake = 0xffffffea0e09c5a8;
static unsigned long addr_fw = 0xffffffea0cece8d0;
static unsigned long addr_chk = 0xffffffea0cecd8c8;
static unsigned long addr_irq = 0xffffffea0c0aa8a0;

module_param(addr_ts, ulong, 0644);
MODULE_PARM_DESC(addr_ts, "Address of ts pointer");
module_param(addr_awake, ulong, 0644);
MODULE_PARM_DESC(addr_awake, "Address of bTouchIsAwake");
module_param(addr_fw, ulong, 0644);
MODULE_PARM_DESC(addr_fw, "Address of nvt_update_firmware");
module_param(addr_chk, ulong, 0644);
MODULE_PARM_DESC(addr_chk, "Address of nvt_check_fw_reset_state");
module_param(addr_irq, ulong, 0644);
MODULE_PARM_DESC(addr_irq, "Address of nvt_irq_enable");

typedef int32_t (*fn_update_fw_t)(char *filename);
typedef int32_t (*fn_check_fw_t)(int state);
typedef void (*fn_irq_enable_t)(bool enable);

static struct kobject *touch_kobj;

static int do_touch_resume(void)
{
	void **pts = (void **)addr_ts;
	uint8_t *pawake = (uint8_t *)addr_awake;
	fn_update_fw_t fn_update_fw = (fn_update_fw_t)addr_fw;
	fn_check_fw_t fn_check_fw = (fn_check_fw_t)addr_chk;
	fn_irq_enable_t fn_irq_enable = (fn_irq_enable_t)addr_irq;
	void *ts_val;
	int ret;

	if (!pts || !pawake || !fn_update_fw || !fn_check_fw || !fn_irq_enable) {
		pr_err("ginkgo_touch_sync: null function or variable pointers!\n");
		return -EINVAL;
	}

	ts_val = *pts;
	if (!ts_val) {
		pr_err("ginkgo_touch_sync: *ts is NULL!\n");
		return -ENODEV;
	}

	pr_info("ginkgo_touch_sync: starting resume, ts=%px, awake=%d\n", ts_val, *pawake);

	/* Set awake to 0 during reload */
	*pawake = 0;

	pr_info("ginkgo_touch_sync: updating firmware novatek_ts_tianma_fw.bin\n");
	ret = fn_update_fw("novatek_ts_tianma_fw.bin");
	if (ret) {
		pr_err("ginkgo_touch_sync: fn_update_fw failed with %d\n", ret);
	} else {
		pr_info("ginkgo_touch_sync: firmware updated, checking reset state...\n");
		ret = fn_check_fw(0xa1);
		pr_info("ginkgo_touch_sync: fn_check_fw returned %d\n", ret);
	}

	pr_info("ginkgo_touch_sync: enabling irq...\n");
	fn_irq_enable(true);

	*pawake = 1;

	pr_info("ginkgo_touch_sync: resume sequence complete! awake=%d\n", *pawake);
	return 0;
}

static ssize_t resume_store(struct kobject *kobj, struct kobj_attribute *attr,
			    const char *buf, size_t count)
{
	int ret;
	ret = do_touch_resume();
	if (ret)
		return ret;
	return count;
}

static ssize_t status_show(struct kobject *kobj, struct kobj_attribute *attr,
			   char *buf)
{
	void **pts = (void **)addr_ts;
	uint8_t *pawake = (uint8_t *)addr_awake;
	void *ts_val = pts ? *pts : NULL;
	int awake_val = pawake ? *pawake : -1;

	return sysfs_emit(buf, "ts=%px awake=%d\n", ts_val, awake_val);
}

static struct kobj_attribute resume_attr = __ATTR(resume, 0200, NULL, resume_store);
static struct kobj_attribute status_attr = __ATTR_RO(status);

static struct attribute *attrs[] = {
	&resume_attr.attr,
	&status_attr.attr,
	NULL,
};

static struct attribute_group attr_group = {
	.attrs = attrs,
};

static int __init ginkgo_touch_sync_init(void)
{
	int ret;

	pr_info("ginkgo_touch_sync: init module, ts_addr=%lx awake_addr=%lx\n",
		addr_ts, addr_awake);

	touch_kobj = kobject_create_and_add("ginkgo_touch", kernel_kobj);
	if (!touch_kobj)
		return -ENOMEM;

	ret = sysfs_create_group(touch_kobj, &attr_group);
	if (ret) {
		kobject_put(touch_kobj);
		return ret;
	}

	pr_info("ginkgo_touch_sync: /sys/kernel/ginkgo_touch created successfully\n");
	return 0;
}

static void __exit ginkgo_touch_sync_exit(void)
{
	kobject_put(touch_kobj);
	pr_info("ginkgo_touch_sync: module exited\n");
}

module_init(ginkgo_touch_sync_init);
module_exit(ginkgo_touch_sync_exit);
