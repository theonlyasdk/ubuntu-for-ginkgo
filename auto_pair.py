import subprocess, time, sys

print("=== Starting Auto Discovery & Pairing Agent (180s Loop) ===")
p = subprocess.Popen(
    ['bluetoothctl'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

def send(cmd):
    print(f">> {cmd}", flush=True)
    p.stdin.write(cmd + "\n")
    p.stdin.flush()

send("power on")
send("agent on")
send("default-agent")
time.sleep(0.5)
send("scan on")

target = "8C:64:A2:A1:70:58"
paired = False
connected = False
start = time.time()

while time.time() - start < 180:
    line = p.stdout.readline()
    if not line:
        break
    sys.stdout.write(line)
    sys.stdout.flush()

    lower = line.lower()
    if (target.lower() in lower or "oneplus" in lower) and not paired:
        print(f"\n*** TARGET HEADSET DETECTED! Initiating pairing... ***", flush=True)
        send(f"pair {target}")
        paired = True
            
    if "(yes/no)" in lower or "confirm" in lower or "authorize" in lower:
        print("\n*** Auto-confirming authentication prompt with 'yes' ***", flush=True)
        send("yes")

    if "pairing successful" in lower or "already paired" in lower:
        print("\n*** PAIRING SUCCEEDED! Trusting and connecting audio... ***", flush=True)
        send(f"trust {target}")
        send(f"connect {target}")

    if "connection successful" in lower:
        print("\n*** ALL PROFILES CONNECTED SUCCESSFULLY! ***", flush=True)
        connected = True
        break

send("scan off")
time.sleep(0.5)
send("quit")
p.terminate()
