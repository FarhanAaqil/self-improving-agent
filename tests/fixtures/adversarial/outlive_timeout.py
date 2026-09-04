# Adversarial test: spawns child background process designed to survive parent termination.
# Host-side Docker kill must destroy the entire container namespace, cleaning up orphans.
import subprocess
import sys
import time

# Attempt to detach a background sleep process
subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(60)"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Parent hangs until host timeout forces a kill
time.sleep(60)
