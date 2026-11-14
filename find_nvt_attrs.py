with open(r'C:\Users\User\Documents\GitHub\ginkgo-mainline-linux\out\deployed-unpack\kernel', 'rb') as f:
    import gzip, re
    d = gzip.decompress(f.read())

print("Length:", len(d))
matches = set(re.findall(rb'(?:nvt_|NT36|touch)[a-zA-Z0-9_]{3,}', d))
for m in sorted(matches):
    try:
        s = m.decode('latin1')
        if any(k in s.lower() for k in ['sysfs', 'attr', 'wake', 'suspend', 'resume', 'reset', 'power', 'sleep', 'state', 'mode']):
            print(s)
    except:
        pass
