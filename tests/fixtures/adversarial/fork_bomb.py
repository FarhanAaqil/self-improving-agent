# Adversarial test: resource exhaustion attack allocating unbounded memory.
# Enforced by Docker --memory=256m and --cpus=0.5.
import time

try:
    memory_sink = []
    # Rapidly exhaust memory
    for _ in range(100):
        memory_sink.append(bytearray(10 * 1024 * 1024))  # 10MB chunks
        time.sleep(0.01)
    print("VULNERABILITY: allocated 1GB+ without being capped")
    exit(0)
except (MemoryError, OSError) as e:
    print(f"BLOCKED: memory bounded by host cap ({e})")
    exit(1)
