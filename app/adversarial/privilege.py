# Adversarial test: are we root, and can we regain privileges?
import os

if os.getuid() == 0 or os.geteuid() == 0:
    print("VULNERABILITY: running as root inside the sandbox")
    exit(0)

try:
    os.setuid(0)
    print("VULNERABILITY: setuid(0) succeeded")
    exit(0)
except PermissionError as e:
    print(f"BLOCKED: unprivileged user, setuid refused ({e})")
    exit(1)
