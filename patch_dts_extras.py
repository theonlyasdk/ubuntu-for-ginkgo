dts_path = "/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts"
with open(dts_path, "r") as f:
    content = f.read()

# 1. Update usb-vbus-regulator@1100
old_vbus = """\t\t\t\tusb-vbus-regulator@1100 {
\t\t\t\t\tcompatible = "qcom,pmi632-vbus-reg", "qcom,pm8150b-vbus-reg";
\t\t\t\t\treg = <0x1100>;
\t\t\t\t\tstatus = "disabled";
\t\t\t\t\tphandle = <0x1c>;
\t\t\t\t};"""

new_vbus = """\t\t\t\tusb-vbus-regulator@1100 {
\t\t\t\t\tcompatible = "qcom,pmi632-vbus-reg", "qcom,pm8150b-vbus-reg";
\t\t\t\t\treg = <0x1100>;
\t\t\t\t\tstatus = "okay";
\t\t\t\t\tregulator-name = "vbus";
\t\t\t\t\tregulator-min-microamp = <0x7a120>;
\t\t\t\t\tregulator-max-microamp = <0x2dc6c0>;
\t\t\t\t\tphandle = <0x1c>;
\t\t\t\t};"""

assert old_vbus in content, "old_vbus not found"
content = content.replace(old_vbus, new_vbus, 1)

# 2. Add otg-vbus consumer
otg_consumer = """\totg-vbus {
\t\tcompatible = "regulator-output";
\t\tvout-supply = <0x1c>;
\t};

"""
insert_point = "\tchosen {"
assert insert_point in content, "chosen not found"
content = content.replace(insert_point, otg_consumer + insert_point, 1)

# 3. Enable rtc@6000
old_rtc = """\t\t\t\trtc@6000 {
\t\t\t\t\tcompatible = "qcom,pm8941-rtc";
\t\t\t\t\treg = <0x6000 0x6100>;
\t\t\t\t\treg-names = "rtc", "alarm";
\t\t\t\t\tinterrupts = <0x00 0x61 0x01 0x01>;
\t\t\t\t\tstatus = "disabled";
\t\t\t\t};"""

new_rtc = """\t\t\t\trtc@6000 {
\t\t\t\t\tcompatible = "qcom,pm8941-rtc";
\t\t\t\t\treg = <0x6000 0x6100>;
\t\t\t\t\treg-names = "rtc", "alarm";
\t\t\t\t\tinterrupts = <0x00 0x61 0x01 0x01>;
\t\t\t\t\tstatus = "okay";
\t\t\t\t};"""

assert old_rtc in content, "old_rtc not found"
content = content.replace(old_rtc, new_rtc, 1)

with open(dts_path, "w") as f:
    f.write(content)

print("VBUS, OTG consumer, and RTC enabled in sm6125-xiaomi-ginkgo.dts!")
