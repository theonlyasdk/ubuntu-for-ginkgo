journalctl -b -u 'user@1000.service' --no-pager | grep -iE 'plasma|kwin|fail|crash|segfault|error' | tail -n 40
ps aux | grep -i plasma
