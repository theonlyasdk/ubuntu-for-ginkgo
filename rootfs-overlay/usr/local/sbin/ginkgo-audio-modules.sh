#!/bin/sh
# Load Ginkgo audio subsystem kernel modules in strict dependency order

MOD_DIR="/lib/modules/ginkgo-extra"

load_mod() {
    [ -f "$MOD_DIR/$1.ko" ] && insmod "$MOD_DIR/$1.ko" 2>/dev/null || true
}

# 0. Start ADSP remoteproc if present
for d in /sys/class/remoteproc/remoteproc*; do
    if [ -f "$d/name" ] && [ "$(cat "$d/name")" = "adsp" ]; then
        state=$(cat "$d/state")
        if [ "$state" != "running" ]; then
            echo start > "$d/state" 2>/dev/null || true
        fi
        break
    fi
done

# 1. ALSA core
load_mod soundcore
load_mod snd
load_mod snd-timer
load_mod snd-pcm
load_mod snd-pcm-dmaengine
load_mod snd-compress
load_mod snd-soc-core

# 2. Speaker amplifier
load_mod snd-soc-max98927

# 3. Qualcomm APR & QDSP6
load_mod pdr_interface
load_mod apr
load_mod snd-q6dsp-common
load_mod q6core
load_mod q6afe
load_mod q6afe-clocks
load_mod q6afe-dai
load_mod q6adm
load_mod q6routing
load_mod q6asm
load_mod q6asm-dai

# 4. SoundWire & WCD Codecs
load_mod slimbus
load_mod soundwire-bus
load_mod soundwire-qcom
load_mod snd-soc-wcd-common
load_mod snd-soc-wcd-classh
load_mod snd-soc-wcd-mbhc
load_mod snd-soc-wcd937x
load_mod snd-soc-wcd937x-sdw
load_mod snd-soc-lpass-macro-common
load_mod snd-soc-lpass-rx-macro
load_mod snd-soc-lpass-tx-macro

# 5. Machine sound driver
load_mod snd-soc-qcom-common
load_mod snd-soc-qcom-sdw
load_mod snd-soc-sm8250

# 6. Default routing for speaker playback
(
    sleep 1
    amixer -c sm6125ginkgosnd cset name='PRI_MI2S_RX Audio Mixer MultiMedia1' 1 2>/dev/null || true
    amixer -c sm6125ginkgosnd cset name='Amp DSP Switch' 1 2>/dev/null || true
    amixer -c sm6125ginkgosnd cset name='Speaker Volume' 5 2>/dev/null || true
    amixer -c sm6125ginkgosnd cset name='Digital Volume' 115 2>/dev/null || true
) &

exit 0
