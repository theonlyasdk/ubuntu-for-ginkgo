#!/bin/sh
case "$1/$2" in
  post/*)
    if [ -w /sys/kernel/ginkgo_touch/resume ]; then
      echo "touch-wake: resuming touchscreen after suspend..." > /dev/kmsg
      echo 1 > /sys/kernel/ginkgo_touch/resume
    fi
    ;;
esac
