#!/bin/sh
set -e

TS_ADDR=$(grep -w 'ts' /proc/kallsyms | head -n1 | awk '{print "0x"$1}')
AWAKE_ADDR=$(grep -w 'bTouchIsAwake' /proc/kallsyms | head -n1 | awk '{print "0x"$1}')
FW_ADDR=$(grep -w 'nvt_update_firmware' /proc/kallsyms | head -n1 | awk '{print "0x"$1}')
CHK_ADDR=$(grep -w 'nvt_check_fw_reset_state' /proc/kallsyms | head -n1 | awk '{print "0x"$1}')
IRQ_ADDR=$(grep -w 'nvt_irq_enable' /proc/kallsyms | head -n1 | awk '{print "0x"$1}')

if [ -n "$TS_ADDR" ] && [ -n "$AWAKE_ADDR" ] && [ -n "$FW_ADDR" ] && [ -n "$CHK_ADDR" ] && [ -n "$IRQ_ADDR" ]; then
    echo "ginkgo-touch-sync: loading module with resolved kallsyms addresses"
    insmod /lib/modules/ginkgo-extra/ginkgo_touch_sync.ko \
        addr_ts=$TS_ADDR \
        addr_awake=$AWAKE_ADDR \
        addr_fw=$FW_ADDR \
        addr_chk=$CHK_ADDR \
        addr_irq=$IRQ_ADDR 2>/dev/null || true
else
    echo "ginkgo-touch-sync: warning: some symbols not found in kallsyms"
fi
