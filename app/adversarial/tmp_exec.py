# Adversarial test: drop an executable into the only writable place and run it.
# /tmp is mounted noexec, so the kernel must refuse to execute it.
import os
import subprocess

path = "/tmp/payload.sh"
with open(path, "w") as f:
    f.write("#!/bin/sh\necho pwned\n")
os.chmod(path, 0o755)

try:
    out = subprocess.run([path], capture_output=True, text=True, timeout=2)
    if "pwned" in out.stdout:
        print("VULNERABILITY: executed a binary dropped in /tmp")
        exit(0)
except PermissionError as e:
    print(f"BLOCKED: /tmp is noexec ({e})")
    exit(1)
print("BLOCKED: payload did not run")
exit(1)
