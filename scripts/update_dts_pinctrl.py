import sys

path = "/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts"
with open(path, "r") as f:
    c = f.read()

# 1. Update sd-lines in dai@16
old_dai = "\t\t\t\t\t\t\tdai@16 {\n\t\t\t\t\t\t\t\treg = <0x10>;\n\t\t\t\t\t\t\t\tqcom,sd-lines = <0x00>;\n\t\t\t\t\t\t\t};"
new_dai = "\t\t\t\t\t\t\tdai@16 {\n\t\t\t\t\t\t\t\treg = <0x10>;\n\t\t\t\t\t\t\t\tqcom,sd-lines = <0x01>;\n\t\t\t\t\t\t\t};"

assert old_dai in c, "old_dai not found"
c = c.replace(old_dai, new_dai, 1)

# 2. Add pri-mi2s-active-state in tlmm (pinctrl@500000) right before qup-i2c0-default-state
target = "\t\t\tqup-i2c0-default-state {"
pinctrl_block = """\t\t\tpri-mi2s-active-state {
\t\t\t\tphandle = <0x87>;

\t\t\t\tsck-pins {
\t\t\t\t\tpins = "gpio113";
\t\t\t\t\tfunction = "pri_mi2s";
\t\t\t\t\tdrive-strength = <0x02>;
\t\t\t\t\tbias-disable;
\t\t\t\t};

\t\t\t\tws-pins {
\t\t\t\t\tpins = "gpio114";
\t\t\t\t\tfunction = "pri_mi2s_ws";
\t\t\t\t\tdrive-strength = <0x02>;
\t\t\t\t\tbias-disable;
\t\t\t\t};

\t\t\t\tdata-pins {
\t\t\t\t\tpins = "gpio115", "gpio116";
\t\t\t\t\tfunction = "pri_mi2s";
\t\t\t\t\tdrive-strength = <0x02>;
\t\t\t\t\tbias-disable;
\t\t\t\t};
\t\t\t};

\t\t\tqup-i2c0-default-state {"""

assert target in c, "target qup-i2c0-default-state not found"
c = c.replace(target, pinctrl_block, 1)

# 3. Add pinctrl to sound node
old_sound = "\tsound {\n\t\tcompatible = \"qcom,sm8250-sndcard\";\n\t\tmodel = \"sm6125-ginkgo-sndcard\";"
new_sound = "\tsound {\n\t\tcompatible = \"qcom,sm8250-sndcard\";\n\t\tmodel = \"sm6125-ginkgo-sndcard\";\n\t\tpinctrl-0 = <0x87>;\n\t\tpinctrl-names = \"default\";"

assert old_sound in c, "old_sound not found"
c = c.replace(old_sound, new_sound, 1)

with open(path, "w") as f:
    f.write(c)

print("Updated DTS successfully!")
