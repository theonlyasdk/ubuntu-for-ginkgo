/* Host harness for the production driver's register paths and notifications. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int64_t s64;
#define BIT(n) (1U << (n))
#define GENMASK(h, l) ((~0U >> (31 - (h))) & (~0U << (l)))
#define clamp(v, lo, hi) ((v) < (lo) ? (lo) : (v) > (hi) ? (hi) : (v))
#define div_u64(a, b) ((a) / (b))
#define div_s64(a, b) ((a) / (b))
#define sign_extend32(v, bit) ((int32_t)((uint32_t)(v) << (31 - (bit))) >> (31 - (bit)))
#define dev_err_ratelimited(...) ((void)0)
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define to_delayed_work(ptr) container_of(ptr, struct delayed_work, work)
#define msecs_to_jiffies(ms) (ms)
#define time_after_eq(a, b) ((long)((a) - (b)) >= 0)

enum power_supply_property {
	POWER_SUPPLY_PROP_PRESENT, POWER_SUPPLY_PROP_STATUS,
	POWER_SUPPLY_PROP_CAPACITY, POWER_SUPPLY_PROP_VOLTAGE_NOW,
	POWER_SUPPLY_PROP_CURRENT_NOW, POWER_SUPPLY_PROP_ONLINE,
	POWER_SUPPLY_PROP_USB_TYPE,
};
enum {
	POWER_SUPPLY_STATUS_UNKNOWN, POWER_SUPPLY_STATUS_CHARGING,
	POWER_SUPPLY_STATUS_DISCHARGING, POWER_SUPPLY_STATUS_NOT_CHARGING,
	POWER_SUPPLY_STATUS_FULL, POWER_SUPPLY_USB_TYPE_UNKNOWN,
};
union power_supply_propval { int intval; };
struct mutex { bool locked; };
struct work_struct { int unused; };
struct delayed_work { struct work_struct work; };
struct device { int unused; };
struct regmap {
	u8 data[0x5000];
	unsigned int calls, fail_at, hold_attempts, release_attempts, bulk_reads;
};
struct pmi632_qg;
struct power_supply { struct pmi632_qg *qg; unsigned int events; };
struct pmi632_qg {
	struct device *dev;
	struct regmap *regmap;
	struct mutex lock;
	u32 base, i_lsb_na;
	struct power_supply *psy, *psy_usb;
	struct delayed_work poll_work;
	int last_present, last_usb_present, last_online, last_status;
	unsigned long next_telemetry;
};
static bool estimate_capacity;
static unsigned long jiffies;
static void *system_freezable_wq;
static unsigned int queued;

static void mutex_lock(struct mutex *m) { assert(!m->locked); m->locked = true; }
static void mutex_unlock(struct mutex *m) { assert(m->locked); m->locked = false; }
static struct pmi632_qg *power_supply_get_drvdata(struct power_supply *p) { return p->qg; }
static void power_supply_changed(struct power_supply *p)
{
	assert(!p->qg->lock.locked);
	p->events++;
}
static void queue_delayed_work(void *wq, struct delayed_work *work, unsigned long delay)
{
	(void)wq; (void)work;
	assert(delay == 2000);
	queued++;
}
static int regmap_read(struct regmap *m, unsigned int reg, unsigned int *val)
{
	assert(reg < sizeof(m->data));
	if (++m->calls == m->fail_at)
		return -EIO;
	*val = m->data[reg];
	return 0;
}
static int regmap_bulk_read(struct regmap *m, unsigned int reg, void *buf, size_t len)
{
	assert(reg + len <= sizeof(m->data));
	m->bulk_reads++;
	if (++m->calls == m->fail_at)
		return -EIO;
	memcpy(buf, m->data + reg, len);
	return 0;
}
static int regmap_update_bits(struct regmap *m, unsigned int reg,
			      unsigned int mask, unsigned int val)
{
	assert(reg == 0x4842 && mask == 1);
	if (val) m->hold_attempts++; else m->release_attempts++;
	if (++m->calls == m->fail_at)
		return -EIO;
	m->data[reg] = (m->data[reg] & ~mask) | val;
	return 0;
}

#include "production.h"

static struct regmap map;
static struct pmi632_qg qg;
static struct power_supply battery, usb;
static unsigned int cases;

static void reset(void)
{
	memset(&map, 0, sizeof(map));
	memset(&qg, 0, sizeof(qg));
	qg.regmap = &map;
	qg.base = 0x4800;
	qg.i_lsb_na = 152588;
	battery = (struct power_supply){ .qg = &qg };
	usb = (struct power_supply){ .qg = &qg };
	qg.psy = &battery;
	qg.psy_usb = &usb;
	qg.last_present = qg.last_usb_present = qg.last_online = qg.last_status = -1;
	qg.next_telemetry = 30000;
	jiffies = 0;
	estimate_capacity = false;
	queued = 0;
}

static void put16(unsigned int reg, u16 raw)
{
	map.data[reg] = raw;
	map.data[reg + 1] = raw >> 8;
}

static void test_status(void)
{
	const int expected[] = { POWER_SUPPLY_STATUS_FULL,
		POWER_SUPPLY_STATUS_CHARGING, POWER_SUPPLY_STATUS_CHARGING,
		POWER_SUPPLY_STATUS_CHARGING, POWER_SUPPLY_STATUS_CHARGING,
		POWER_SUPPLY_STATUS_FULL, POWER_SUPPLY_STATUS_NOT_CHARGING,
		POWER_SUPPLY_STATUS_NOT_CHARGING };
	int status, present, online;

	for (int i = 0; i < 8; i++) {
		reset();
		map.data[0x1006] = i | 0x80;
		assert(!pmi632_read_status(&qg, 1, 1, &status));
		assert(status == expected[i]);
		assert(!pmi632_read_status(&qg, 0, 0, &status));
		assert(status == POWER_SUPPLY_STATUS_DISCHARGING);
		assert(!pmi632_read_status(&qg, 1, 0, &status));
		assert(status == ((i == 0 || i == 5) ? POWER_SUPPLY_STATUS_FULL :
			       POWER_SUPPLY_STATUS_DISCHARGING));
		cases += 3;
	}
	reset();
	map.fail_at = 1;
	status = 123;
	assert(pmi632_read_status(&qg, 1, 1, &status) == -EIO && status == 123);
	cases++;
	for (int flags = 0; flags < 4; flags++) {
		reset();
		map.data[0x1310] = BIT(4);
		map.data[0x110b] = ((flags & 1) ? BIT(4) : 0) | ((flags & 2) ? BIT(0) : 0);
		assert(!pmi632_read_usb(&qg, &present, &online));
		assert(present == 1 && online == (flags == 3));
		cases++;
	}
	for (int failure = 1; failure <= 2; failure++) {
		reset();
		map.data[0x1310] = BIT(4);
		map.fail_at = failure;
		assert(pmi632_read_usb(&qg, &present, &online) == -EIO);
		cases++;
	}
	reset();
	assert(!pmi632_read_usb(&qg, &present, &online));
	assert(!present && !online && map.calls == 1);
	cases++;
}

static void test_current(void)
{
	const u16 raw[] = { 0, 1, 0xffff, 32767, 32768 };
	int ua;

	for (int range = 0; range < 2; range++) {
		for (unsigned int i = 0; i < sizeof(raw) / sizeof(raw[0]); i++) {
			reset();
			qg.i_lsb_na = range ? 305176 : 152588;
			put16(0x48c6, raw[i]);
			mutex_lock(&qg.lock);
			assert(!qg_read_current(&qg, &ua));
			mutex_unlock(&qg.lock);
			assert(ua == -(int)((int64_t)(int16_t)raw[i] * qg.i_lsb_na / 1000));
			assert(map.hold_attempts == 1 && map.release_attempts == 1);
			assert(map.data[0x4842] == 0);
			cases++;
		}
	}
	for (int failure = 1; failure <= 3; failure++) {
		reset();
		ua = 123;
		map.fail_at = failure;
		mutex_lock(&qg.lock);
		assert(qg_read_current(&qg, &ua) == -EIO);
		mutex_unlock(&qg.lock);
		assert(ua == 123 && map.release_attempts == 1);
		assert(map.bulk_reads == (failure == 1 ? 0U : 1U));
		cases++;
	}
}

static void test_properties_and_events(void)
{
	union power_supply_propval val = { .intval = 123 };
	reset();
	map.data[0x4808] = BIT(7);
	assert(!qg_get_property(&battery, POWER_SUPPLY_PROP_PRESENT, &val));
	assert(val.intval == 0); /* QG_OK alone does not indicate a battery. */
	map.data[0x4808] |= BIT(0);
	assert(!qg_get_property(&battery, POWER_SUPPLY_PROP_PRESENT, &val));
	assert(val.intval == 1);
	cases += 2;

	assert(qg_get_property(&battery, POWER_SUPPLY_PROP_CAPACITY, &val) == -ENODATA);
	estimate_capacity = true;
	assert(qg_get_property(&battery, POWER_SUPPLY_PROP_CAPACITY, &val) == -ENODATA);
	put16(0x48c0, 0xffff);
	assert(qg_get_property(&battery, POWER_SUPPLY_PROP_VOLTAGE_NOW, &val) == -ENODATA);
	put16(0x48c0, 21000);
	assert(!qg_get_property(&battery, POWER_SUPPLY_PROP_VOLTAGE_NOW, &val));
	assert(val.intval == 4087377);
	cases += 4;

	/* Status and voltage must not touch the current HOLD or require its ADC. */
	assert(!qg_get_property(&battery, POWER_SUPPLY_PROP_STATUS, &val));
	assert(val.intval == POWER_SUPPLY_STATUS_DISCHARGING && !map.hold_attempts);
	assert(!qg_usb_get_property(&usb, POWER_SUPPLY_PROP_USB_TYPE, &val));
	assert(val.intval == POWER_SUPPLY_USB_TYPE_UNKNOWN);
	cases += 2;

	reset();
	pmi632_poll_work(&qg.poll_work.work);
	assert(battery.events == 1 && usb.events == 1 && !map.hold_attempts && !map.bulk_reads);
	pmi632_poll_work(&qg.poll_work.work);
	assert(battery.events == 1 && usb.events == 1);
	map.fail_at = map.calls + 1;
	pmi632_poll_work(&qg.poll_work.work);
	assert(battery.events == 1 && usb.events == 1 && qg.last_online == 0);
	map.data[0x1310] = BIT(4);
	map.data[0x110b] = BIT(4) | BIT(0);
	map.data[0x1006] = 3;
	pmi632_poll_work(&qg.poll_work.work);
	assert(battery.events == 2 && usb.events == 2);
	jiffies = 30000;
	pmi632_poll_work(&qg.poll_work.work);
	assert(battery.events == 3 && usb.events == 2);
	assert(queued == 5 && !qg.lock.locked);
	cases += 5;
}

int main(void)
{
	test_status();
	test_current();
	test_properties_and_events();
	printf("PMI632: %u cases passed (register failures, state decoding, current, notifications)\n", cases);
	return 0;
}
