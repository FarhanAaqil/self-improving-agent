# Adversarial test: attempts to write to container root filesystem.
# With --read-only and --tmpfs /tmp, writing outside /tmp must fail with OSError/ReadOnlyFilesystem.
import os

escape_targets = ["/app/escape.txt", "/root/malicious.sh", "/etc/hacked.conf"]
escaped = False

for target in escape_targets:
    try:
        with open(target, "w") as f:
            f.write("escaped")
        escaped = True
        break
    except OSError:
        continue

if escaped:
    print("VULNERABILITY: successfully wrote to read-only container path!")
    exit(0)
else:
    print("BLOCKED: container root is read-only")
    exit(1)
