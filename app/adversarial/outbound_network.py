# Adversarial test: attempts outbound HTTP request.
# With --network none, this must fail with a socket or network error.
import urllib.request

try:
    urllib.request.urlopen("https://example.com", timeout=2)
    print("VULNERABILITY: outbound network call succeeded!")
    exit(0)
except Exception as e:
    print(f"BLOCKED: outbound network unreachable ({e})")
    exit(1)
