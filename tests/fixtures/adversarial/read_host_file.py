# Adversarial test: attempts to read sensitive host/system paths outside the container mount.
# Sandbox isolation must ensure host credentials and sensitive files are never accessible.

targets = ["/etc/shadow", "/etc/passwd", "/root/.ssh/id_rsa"]
leaked = []

for target in targets:
    try:
        with open(target, "r") as f:
            content = f.read(32)
            if "root:" in content:
                leaked.append(target)
    except Exception:
        pass

if leaked:
    print(f"VULNERABILITY: read sensitive host file(s): {leaked}")
    exit(0)
else:
    print("BLOCKED: host filesystem isolated")
    exit(1)
