path = "/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts"
with open(path, "r") as f:
    content = f.read()

# 1. smp2p-adsp interrupt -> 0x189 (GIC_SPI 393)
old_smp2p = "\t\tinterrupts = <0x00 0x117 0x01>;"
# find within smp2p-adsp
idx = content.find("smp2p-adsp")
assert idx != -1, "smp2p-adsp not found"
idx2 = content.find(old_smp2p, idx)
assert idx2 != -1, "old_smp2p not found"
content = content[:idx2] + "\t\tinterrupts = <0x00 0x189 0x01>;" + content[idx2 + len(old_smp2p):]

# 2. remoteproc node: reg @ab00000, wdog 0x18c (GIC_SPI 396)
old_rproc = "remoteproc@a400000"
new_rproc = "remoteproc@ab00000"
assert old_rproc in content, "old_rproc not found"
content = content.replace(old_rproc, new_rproc, 1)

old_reg = "reg = <0x00 0x0a400000 0x00 0x4040>;"
new_reg = "reg = <0x00 0x0ab00000 0x00 0x100>;"
assert old_reg in content, "old_reg not found"
content = content.replace(old_reg, new_reg, 1)

old_wdog = "interrupts-extended = <0x01 0x00 0x11a 0x01"
new_wdog = "interrupts-extended = <0x01 0x00 0x18c 0x01"
assert old_wdog in content, "old_wdog not found"
content = content.replace(old_wdog, new_wdog, 1)

# 3. glink-edge interrupt -> 0x187 (GIC_SPI 391)
idx3 = content.find("remoteproc@ab00000")
idx4 = content.find("glink-edge", idx3)
old_glink = "interrupts = <0x00 0x115 0x01>;"
idx5 = content.find(old_glink, idx4)
assert idx5 != -1, "old_glink not found"
content = content[:idx5] + "interrupts = <0x00 0x187 0x01>;" + content[idx5 + len(old_glink):]

# 4. max98927 reset gpio -> active low 0x01
old_gpio = "reset-gpios = <0x13 0x1b 0x00>;"
new_gpio = "reset-gpios = <0x13 0x1b 0x01>;"
assert old_gpio in content, "old_gpio not found"
content = content.replace(old_gpio, new_gpio, 1)

with open(path, "w") as f:
    f.write(content)
print("DTS successfully updated for Trinket ADSP & MAX98927!")
