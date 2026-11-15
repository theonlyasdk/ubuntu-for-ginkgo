import sys

dts_path = "/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts"
with open(dts_path, "r") as f:
    content = f.read()

# 1. Add phandle to memory@55300000
mem_target = "\t\tmemory@55300000 {\n\t\t\treg = <0x00 0x55300000 0x00 0x1e00000>;\n\t\t\tno-map;\n\t\t};"
mem_repl = "\t\tmemory@55300000 {\n\t\t\treg = <0x00 0x55300000 0x00 0x1e00000>;\n\t\t\tno-map;\n\t\t\tphandle = <0x80>;\n\t\t};"
assert mem_target in content, "mem_target not found"
content = content.replace(mem_target, mem_repl, 1)

# 2. Add max98927 to i2c@4a84000
led_target = "\t\t\t\tled-controller@36 {"
max_node = """\t\t\t\tmax98927: max98927@3a {
\t\t\t\t\tcompatible = "maxim,max98927";
\t\t\t\t\treg = <0x3a>;
\t\t\t\t\t#sound-dai-cells = <0x00>;
\t\t\t\t\treset-gpios = <0x1d 0x1b 0x01>;
\t\t\t\t\tvmon-slot-no = <0x02>;
\t\t\t\t\timon-slot-no = <0x00>;
\t\t\t\t\tstatus = "okay";
\t\t\t\t\tphandle = <0x81>;
\t\t\t\t};

\t\t\t\tled-controller@36 {"""
assert led_target in content, "led_target not found"
content = content.replace(led_target, max_node, 1)

# 3. Add smp2p-adsp after smp2p-mpss
smp2p_target = "\t\tslave-kernel {\n\t\t\tqcom,entry-name = \"slave-kernel\";\n\t\t\tinterrupt-controller;\n\t\t\t#interrupt-cells = <0x02>;\n\t\t\tphandle = <0x6e>;\n\t\t};\n\t};"
smp2p_adsp = """\t\tslave-kernel {
\t\t\tqcom,entry-name = "slave-kernel";
\t\t\tinterrupt-controller;
\t\t\t#interrupt-cells = <0x02>;
\t\t\tphandle = <0x6e>;
\t\t};
\t};

\tsmp2p-adsp {
\t\tcompatible = "qcom,smp2p";
\t\tqcom,smem = <0x1bb 0x1ad>;
\t\tinterrupts = <0x00 0x117 0x01>;
\t\tmboxes = <0x0e 0x0a>;
\t\tqcom,local-pid = <0x00>;
\t\tqcom,remote-pid = <0x02>;

\t\tmaster-kernel {
\t\t\tqcom,entry-name = "master-kernel";
\t\t\t#qcom,smem-state-cells = <0x01>;
\t\t\tphandle = <0x82>;
\t\t};

\t\tslave-kernel {
\t\t\tqcom,entry-name = "slave-kernel";
\t\t\tinterrupt-controller;
\t\t\t#interrupt-cells = <0x02>;
\t\t\tphandle = <0x83>;
\t\t};
\t};"""
assert smp2p_target in content, "smp2p_target not found"
content = content.replace(smp2p_target, smp2p_adsp, 1)

# 4. Add remoteproc@a400000 beside remoteproc@6080000
remoteproc_target = "\t\tremoteproc@6080000 {"
remoteproc_adsp = """\t\tremoteproc@a400000 {
\t\t\tcompatible = "qcom,sm6115-adsp-pas";
\t\t\treg = <0x00 0x0a400000 0x00 0x4040>;
\t\t\tinterrupts-extended = <0x01 0x00 0x11a 0x01 0x83 0x00 0x01 0x83 0x01 0x01 0x83 0x02 0x01 0x83 0x03 0x01>;
\t\t\tinterrupt-names = "wdog", "fatal", "ready", "handover", "stop-ack";
\t\t\tclocks = <0x14 0x00>;
\t\t\tclock-names = "xo";
\t\t\tpower-domains = <0x23 0x00>;
\t\t\tpower-domain-names = "cx";
\t\t\tmemory-region = <0x80>;
\t\t\tqcom,smem-states = <0x82 0x00>;
\t\t\tqcom,smem-state-names = "stop";
\t\t\tstatus = "okay";
\t\t\tfirmware-name = "qcom/sm6125/xiaomi/ginkgo/adsp.mdt";

\t\t\tglink-edge {
\t\t\t\tinterrupts = <0x00 0x115 0x01>;
\t\t\t\tlabel = "lpass";
\t\t\t\tqcom,remote-pid = <0x02>;
\t\t\t\tmboxes = <0x0e 0x08>;

\t\t\t\tapr {
\t\t\t\t\tcompatible = "qcom,apr-v2";
\t\t\t\t\tqcom,glink-channels = "apr_audio_svc";
\t\t\t\t\tqcom,domain = <0x04>;
\t\t\t\t\t#address-cells = <0x01>;
\t\t\t\t\t#size-cells = <0x00>;

\t\t\t\t\tservice@3 {
\t\t\t\t\t\treg = <0x03>;
\t\t\t\t\t\tcompatible = "qcom,q6core";
\t\t\t\t\t\tqcom,protection-domain = "avs/audio", "msm/adsp/audio_pd";
\t\t\t\t\t};

\t\t\t\t\tservice@4 {
\t\t\t\t\t\tcompatible = "qcom,q6afe";
\t\t\t\t\t\treg = <0x04>;
\t\t\t\t\t\tqcom,protection-domain = "avs/audio", "msm/adsp/audio_pd";

\t\t\t\t\t\tdais {
\t\t\t\t\t\t\tcompatible = "qcom,q6afe-dais";
\t\t\t\t\t\t\t#address-cells = <0x01>;
\t\t\t\t\t\t\t#size-cells = <0x00>;
\t\t\t\t\t\t\t#sound-dai-cells = <0x01>;
\t\t\t\t\t\t\tphandle = <0x85>;
\t\t\t\t\t\t};

\t\t\t\t\t\tclock-controller {
\t\t\t\t\t\t\tcompatible = "qcom,q6afe-clocks";
\t\t\t\t\t\t\t#clock-cells = <0x02>;
\t\t\t\t\t\t};
\t\t\t\t\t};

\t\t\t\t\tservice@7 {
\t\t\t\t\t\tcompatible = "qcom,q6asm";
\t\t\t\t\t\treg = <0x07>;
\t\t\t\t\t\tqcom,protection-domain = "avs/audio", "msm/adsp/audio_pd";

\t\t\t\t\t\tdais {
\t\t\t\t\t\t\tcompatible = "qcom,q6asm-dais";
\t\t\t\t\t\t\t#address-cells = <0x01>;
\t\t\t\t\t\t\t#size-cells = <0x00>;
\t\t\t\t\t\t\t#sound-dai-cells = <0x01>;
\t\t\t\t\t\t\tiommus = <0x22 0x1c1 0x00>;
\t\t\t\t\t\t\tphandle = <0x84>;

\t\t\t\t\t\t\tdai@0 {
\t\t\t\t\t\t\t\treg = <0x00>;
\t\t\t\t\t\t\t};
\t\t\t\t\t\t};
\t\t\t\t\t};

\t\t\t\t\tservice@8 {
\t\t\t\t\t\tcompatible = "qcom,q6adm";
\t\t\t\t\t\treg = <0x08>;
\t\t\t\t\t\tqcom,protection-domain = "avs/audio", "msm/adsp/audio_pd";

\t\t\t\t\t\trouting {
\t\t\t\t\t\t\tcompatible = "qcom,q6adm-routing";
\t\t\t\t\t\t\t#sound-dai-cells = <0x00>;
\t\t\t\t\t\t\tphandle = <0x86>;
\t\t\t\t\t\t};
\t\t\t\t\t};
\t\t\t\t};
\t\t\t};
\t\t};

\t\tremoteproc@6080000 {"""
assert remoteproc_target in content, "remoteproc_target not found"
content = content.replace(remoteproc_target, remoteproc_adsp, 1)

# 5. Add sound node before closing brace
sound_node = """
\tsound {
\t\tcompatible = "qcom,sm8250-sndcard";
\t\tmodel = "sm6125-ginkgo-sndcard";

\t\tmm1-dai-link {
\t\t\tlink-name = "MultiMedia1";
\t\t\tcpu {
\t\t\t\tsound-dai = <0x84 0x00>;
\t\t\t};
\t\t};

\t\tpri-mi2s-dai-link {
\t\t\tlink-name = "Primary MI2S";
\t\t\tcpu {
\t\t\t\tsound-dai = <0x85 0x10>;
\t\t\t};
\t\t\tplatform {
\t\t\t\tsound-dai = <0x86>;
\t\t\t};
\t\t\tcodec {
\t\t\t\tsound-dai = <0x81>;
\t\t\t};
\t\t};
\t};
};
"""
# Replace the last };
last_brace_idx = content.rfind("};")
assert last_brace_idx != -1, "last brace not found"
content = content[:last_brace_idx] + sound_node

with open(dts_path, "w") as f:
    f.write(content)
print("DTS patched successfully!")
