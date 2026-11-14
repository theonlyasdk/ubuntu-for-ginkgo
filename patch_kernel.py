import gzip
import sys

kernel_path = 'out/deployed-unpack/kernel'
print('Reading', kernel_path)
with open(kernel_path, 'rb') as f:
    raw = f.read()

data = bytearray(gzip.decompress(raw))
needle = b'androidboot.mode=charger'
idx = 0
matches = []
while True:
    pos = data.find(needle, idx)
    if pos == -1:
        break
    matches.append(pos)
    idx = pos + 1

print('Found', len(matches), 'matches at:', matches)
for m in matches:
    print('Context at', m, ':', repr(bytes(data[m-30:m+70])))

# In nt36xxx.c:
# if (strstr(saved_command_line, "androidboot.mode=charger") != NULL) {
#     NVT_LOG("androidboot.mode=charger, doesn't support touch in the charging mode!\n");
# }
# Notice the first match is the search needle for strstr!
# The second match is the format string for NVT_LOG!
# If we replace the search needle (the first match), strstr will look for something that never exists!
# Length of needle is 24 bytes: b'androidboot.mode=charger'
# Replacement: b'androidboot.mode=nocharg' (exact same 24 bytes)

replacement = b'androidboot.mode=nocharg'
assert len(replacement) == len(needle)

data[matches[0]:matches[0]+len(replacement)] = replacement
print('Replaced match 0 with', replacement)

# Verify
assert data.find(needle) == matches[1]
print('Verification passed: match 0 successfully changed, match 1 intact.')

# Compress with gzip level 9
out_path = 'out/Image.gz'
print('Writing patched kernel to', out_path)
with gzip.open(out_path, 'wb', compresslevel=9) as f:
    f.write(data)

print('Done!')
