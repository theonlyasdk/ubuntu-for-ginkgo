#!/usr/bin/env python3
"""Run a command on ginkgo. Set GINKGO_IP to use Wi-Fi instead of USB."""

import os
import sys
import threading

import paramiko


def copy_stream(source, destination):
    while chunk := source.read(4096):
        destination.write(chunk)
        destination.flush()


def main():
    command = " ".join(sys.argv[1:]) or "uname -a"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            os.environ.get("GINKGO_IP", "192.168.7.2"),
            username="root",
            password=os.environ.get("GINKGO_ROOT_PASSWORD", "password"),
            timeout=5,
            banner_timeout=5,
            auth_timeout=5,
            look_for_keys=False,
            allow_agent=False,
        )
        stdin, stdout, stderr = client.exec_command(command)
        stdin.close()
        threads = [
            threading.Thread(target=copy_stream, args=(stdout, sys.stdout.buffer)),
            threading.Thread(target=copy_stream, args=(stderr, sys.stderr.buffer)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return stdout.channel.recv_exit_status()
    except (OSError, paramiko.SSHException) as exc:
        print(f"SSH: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
