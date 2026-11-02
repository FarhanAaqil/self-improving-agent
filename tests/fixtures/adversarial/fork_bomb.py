# Adversarial test: a real fork bomb.
# --pids-limit must stop process creation long before the host notices.
import os
import time

children = 0
try:
    for _ in range(500):
        pid = os.fork()
        if pid == 0:
            time.sleep(3)
            os._exit(0)
        children += 1
    print(f"VULNERABILITY: spawned {children} processes without hitting a limit")
    exit(0)
except OSError as e:
    print(f"BLOCKED: process limit hit after {children} forks ({e})")
    exit(1)
