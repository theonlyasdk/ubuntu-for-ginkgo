path = "/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts"
with open(path, "r") as f:
    content = f.read()

old_afe_dais = '''\t\t\t\t\t\tdais {
\t\t\t\t\t\t\tcompatible = "qcom,q6afe-dais";
\t\t\t\t\t\t\t#address-cells = <0x01>;
\t\t\t\t\t\t\t#size-cells = <0x00>;
\t\t\t\t\t\t\t#sound-dai-cells = <0x01>;
\t\t\t\t\t\t\tphandle = <0x85>;
\t\t\t\t\t\t};'''

new_afe_dais = '''\t\t\t\t\t\tdais {
\t\t\t\t\t\t\tcompatible = "qcom,q6afe-dais";
\t\t\t\t\t\t\t#address-cells = <0x01>;
\t\t\t\t\t\t\t#size-cells = <0x00>;
\t\t\t\t\t\t\t#sound-dai-cells = <0x01>;
\t\t\t\t\t\t\tphandle = <0x85>;

\t\t\t\t\t\t\tdai@16 {
\t\t\t\t\t\t\t\treg = <0x10>;
\t\t\t\t\t\t\t\tqcom,sd-lines = <0x00>;
\t\t\t\t\t\t\t};
\t\t\t\t\t\t};'''

assert old_afe_dais in content, "old_afe_dais not found"
content = content.replace(old_afe_dais, new_afe_dais, 1)

with open(path, "w") as f:
    f.write(content)
print("Added dai@16 to q6afe-dais successfully!")
