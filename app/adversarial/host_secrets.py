# Adversarial test: look for anything that belongs to the host rather than the sandbox.
# The container must not see the Docker socket, the server's secrets, or host home dirs.
import os

leaks = []

if os.path.exists("/var/run/docker.sock"):
    leaks.append("docker socket mounted")

for name in os.environ:
    if any(marker in name.upper() for marker in ("GROQ", "GITHUB", "API_KEY", "TOKEN", "SECRET")):
        leaks.append(f"env var {name}")

for path in ("/root/.ssh", "/home", "/etc/shadow"):
    try:
        if os.path.isdir(path) and os.listdir(path):
            leaks.append(f"listable {path}")
        elif os.path.isfile(path):
            with open(path) as f:
                f.read(1)
            leaks.append(f"readable {path}")
    except OSError:
        pass

if leaks:
    print(f"VULNERABILITY: {leaks}")
    exit(0)
print("BLOCKED: nothing from the host is visible")
exit(1)
