with open(r'C:\Users\User\Documents\GitHub\ginkgo-mainline-linux\out\deployed-unpack\kernel', 'rb') as f:
    import gzip, re
    d = gzip.decompress(f.read())

matches = set(re.findall(rb'nvt_[a-zA-Z0-9_]+', d))
for m in sorted(matches):
    print(m.decode('latin1'))
