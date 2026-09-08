export default function SecurityAbout() {
  return (
    <article className="max-w-[720px] space-y-8 py-2 font-sans text-ink leading-relaxed">
      {/* Title & Introduction */}
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Security Architecture & Threat Model
        </h1>
        <p className="text-sm text-ink-secondary leading-normal">
          Technical specifications of container isolation, host sandbox boundaries, and architectural limitations.
        </p>
      </header>

      <hr className="border-border" />

      {/* Section 1: Core Premise */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold text-ink">
          1. Core Security Premise
        </h2>
        <p className="text-sm text-ink-secondary">
          In an autonomous code generation system, model output must be treated as untrusted arbitrary code. Simple process spawning via Python <code className="px-1 py-0.5 rounded bg-surface-sunken border border-border text-xs font-mono text-ink">subprocess.run()</code> or in-memory <code className="px-1 py-0.5 rounded bg-surface-sunken border border-border text-xs font-mono text-ink">exec()</code> exposes the host system to file system traversal, network exfiltration, persistence, and algorithmic resource exhaustion.
        </p>
        <p className="text-sm text-ink-secondary">
          Every synthesized script is mounted read-only into an ephemeral Docker container and executed under strict kernel-level cgroup constraints. If Docker is unavailable, the agent fails closed by default rather than running unverified code on the host.
        </p>
      </section>

      <hr className="border-border" />

      {/* Section 2: Sandbox Isolation Controls */}
      <section className="space-y-4">
        <h2 className="text-base font-semibold text-ink">
          2. Container Isolation Controls
        </h2>

        <div className="space-y-3 text-sm text-ink-secondary">
          <div>
            <div className="font-medium text-ink flex items-center justify-between">
              <span>Network isolation</span>
              <code className="text-xs font-mono text-accent">--network none</code>
            </div>
            <p className="mt-1">
              Loopback and physical network interfaces are disabled within the container. Code cannot initiate TCP/UDP connections, resolve external DNS, exfiltrate API credentials, or communicate with local networks.
            </p>
          </div>

          <div>
            <div className="font-medium text-ink flex items-center justify-between">
              <span>Resource & memory bounds</span>
              <code className="text-xs font-mono text-accent">--memory=256m --cpus=0.5</code>
            </div>
            <p className="mt-1">
              Linux kernel cgroups bound memory and CPU usage. Memory consumption exceeding 256MB triggers an immediate kernel OOM killer termination, neutralizing fork bombs and memory exhaustion loops.
            </p>
          </div>

          <div>
            <div className="font-medium text-ink flex items-center justify-between">
              <span>Read-only root filesystem</span>
              <code className="text-xs font-mono text-accent">--read-only --tmpfs /tmp:rw,size=64m</code>
            </div>
            <p className="mt-1">
              The container filesystem is mounted strictly read-only. Only a volatile 64MB RAM-backed tmpfs mount at <code className="px-1 py-0.5 rounded bg-surface-sunken border border-border text-xs font-mono text-ink">/tmp</code> permits scratch files, preventing persistent file system modifications.
            </p>
          </div>

          <div>
            <div className="font-medium text-ink flex items-center justify-between">
              <span>Host-enforced timeout supervisor</span>
              <code className="text-xs font-mono text-accent">timeout=10s + docker rm -f</code>
            </div>
            <p className="mt-1">
              Timeouts are enforced by the host supervisor process using wall-clock deadlines rather than in-process signals. Untrusted scripts cannot intercept or suppress termination.
            </p>
          </div>
        </div>
      </section>

      <hr className="border-border" />

      {/* Section 3: Verification & Adversarial Test Suite */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold text-ink">
          3. Adversarial Test Suite
        </h2>
        <p className="text-sm text-ink-secondary">
          The container boundary is verified continuously through regression test fixtures in <code className="px-1 py-0.5 rounded bg-surface-sunken border border-border text-xs font-mono text-ink">tests/test_sandbox_isolation.py</code>:
        </p>
        <ul className="text-xs text-ink-secondary space-y-1.5 list-disc list-inside font-mono">
          <li>outbound_network.py — attempts HTTP exfiltration via urllib to external IP</li>
          <li>read_host_file.py — attempts directory traversal to host /etc/shadow or /etc/passwd</li>
          <li>fork_bomb.py — initiates recursive process spawning to exhaust memory</li>
          <li>write_outside_tmp.py — attempts binary drops to /usr/local/bin and /bin</li>
          <li>outlive_timeout.py — overrides SIGTERM/SIGALRM to loop indefinitely</li>
        </ul>
      </section>

      <hr className="border-border" />

      {/* Section 4: Threat Model & Boundaries */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold text-ink">
          4. Honest Threat Model Limitations
        </h2>
        <p className="text-sm text-ink-secondary">
          Security requires transparency regarding what the system does not solve:
        </p>
        <ul className="text-sm text-ink-secondary space-y-2 list-disc list-inside">
          <li>
            <strong className="text-ink">Container escape zero-days:</strong> Standard Docker isolation shares the host Linux kernel. In multi-tenant enterprise deployments, microVM isolation (such as AWS Firecracker or gVisor runsc) should replace standard runc.
          </li>
          <li>
            <strong className="text-ink">Logic errors vs malicious code:</strong> Sandbox controls verify execution safety, not semantic correctness against business rules.
          </li>
          <li>
            <strong className="text-ink">Docker socket exposure:</strong> In containerized deployments (Docker-in-Docker), access to <code className="px-1 py-0.5 rounded bg-surface-sunken border border-border text-xs font-mono text-ink">/var/run/docker.sock</code> grants root-equivalent control over the host engine and must be restricted to trusted networks.
          </li>
        </ul>
      </section>
    </article>
  )
}
