path = "/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts"
with open(path, "r") as f:
    c = f.read()

old_block = """\t\t\t\t\t\t\tdai@0 {
\t\t\t\t\t\t\t\treg = <0x00>;
\t\t\t\t\t\t\t};"""

new_block = """\t\t\t\t\t\t\tdai@0 {
\t\t\t\t\t\t\t\treg = <0x00>;
\t\t\t\t\t\t\t\tdirection = <0x02>;
\t\t\t\t\t\t\t};"""

assert old_block in c, "old_block not found"
c = c.replace(old_block, new_block, 1)

with open(path, "w") as f:
    f.write(c)

print("Updated dai@0 with direction=<0x02> successfully!")
