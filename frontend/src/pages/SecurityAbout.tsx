import {
  AlertTriangle,
  Cpu,
  Database,
  FileCheck,
  FolderLock,
  Globe,
  HardDrive,
  Info,
  Lock,
  Server,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Zap,
} from 'lucide-react'

export default function SecurityAbout() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
          <ShieldCheck className="h-6 w-6 text-indigo-400" />
          <span>Security Architecture & Threat Model</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Technical specifications of container isolation, sandbox security boundaries, and architectural limitations.
        </p>
      </div>

      {/* Philosophy banner */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
        <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Lock className="h-4 w-4 text-emerald-400" />
          <span>Core Security Premise</span>
        </h2>
        <p className="text-xs text-slate-400 leading-relaxed">
          In an autonomous code generation agent, LLM output must be treated as completely untrusted arbitrary code. Simple process spawning via Python <code className="text-slate-300">subprocess.run()</code> or in-memory <code className="text-slate-300">exec()</code> is vulnerable to host file access, network exfiltration, persistence attacks, and system exhaustion.
        </p>
      </div>

      {/* 4 Sandbox Isolation Layers */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
          <Terminal className="h-4 w-4 text-indigo-400" />
          <span>Container Isolation Controls</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <Globe className="h-4 w-4 text-rose-400" />
              <span>Zero Outbound Network</span>
            </div>
            <div className="font-mono text-xs text-indigo-300 bg-slate-950 p-2 rounded border border-slate-800">
              --network none
            </div>
            <p className="text-xs text-slate-400">
              Generated code runs with loopback and physical network interfaces disabled. Prohibits socket creation, remote HTTP dialing, credential exfiltration, and botnet propagation.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <Cpu className="h-4 w-4 text-amber-400" />
              <span>Resource & Compute Capping</span>
            </div>
            <div className="font-mono text-xs text-indigo-300 bg-slate-950 p-2 rounded border border-slate-800">
              --memory=256m --cpus=0.5
            </div>
            <p className="text-xs text-slate-400">
              Hard kernel cgroup limits prevent algorithmic exhaustion, runaway loops, and fork bombs. Hitting 256MB triggers an instantaneous kernel OOM termination.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <FolderLock className="h-4 w-4 text-sky-400" />
              <span>Immutable Filesystem</span>
            </div>
            <div className="font-mono text-xs text-indigo-300 bg-slate-950 p-2 rounded border border-slate-800">
              --read-only --tmpfs /tmp:rw,size=64m
            </div>
            <p className="text-xs text-slate-400">
              Container root filesystem is entirely immutable. Only a 64MB RAM-backed tmpfs mount at <code className="text-slate-300">/tmp</code> is writable, preventing binary tampering or malicious persistence.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <Zap className="h-4 w-4 text-emerald-400" />
              <span>Host-Controlled Timeout</span>
            </div>
            <div className="font-mono text-xs text-indigo-300 bg-slate-950 p-2 rounded border border-slate-800">
              subprocess.run(timeout=10) + docker rm -f
            </div>
            <p className="text-xs text-slate-400">
              Execution timeouts are enforced externally by the host supervisor rather than in-process signals, ensuring malicious code cannot trap or intercept SIGALRM to outlive the timeout.
            </p>
          </div>
        </div>
      </div>

      {/* Adversarial Testing Suite */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <FileCheck className="h-4 w-4 text-indigo-400" />
          <span>Adversarial Test Suite Fixtures</span>
        </h2>
        <p className="text-xs text-slate-400">
          The CI test pipeline executes 5 explicit attack vectors on every commit to verify that security controls cannot silently regress:
        </p>
        <div className="space-y-2 text-xs font-mono">
          {[
            {
              name: 'outbound_network.py',
              target: 'Network socket',
              expected: 'Blocked by --network none with URLError',
            },
            {
              name: 'read_host_file.py',
              target: 'Host /etc/shadow, ~/.ssh',
              expected: 'Blocked by container filesystem mount isolation',
            },
            {
              name: 'fork_bomb.py',
              target: 'Memory / CPU exhaustion',
              expected: 'Killed by cgroup memory hard limit (256MB)',
            },
            {
              name: 'write_outside_tmp.py',
              target: 'Root filesystem write',
              expected: 'Blocked by --read-only with ReadOnlyFilesystem error',
            },
            {
              name: 'outlive_timeout.py',
              target: 'Background child process',
              expected: 'Terminated by host supervisor timeout cleanup',
            },
          ].map((item) => (
            <div
              key={item.name}
              className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-1"
            >
              <div className="flex items-center gap-2 text-slate-200">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>{item.name}</span>
                <span className="text-slate-500 font-sans text-[11px]">({item.target})</span>
              </div>
              <span className="text-slate-400 text-[11px]">{item.expected}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Architectural Limitations & Boundary Notice */}
      <div className="bg-slate-900/40 border border-slate-800/90 rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <span>Documented Limitations & Trust Boundary</span>
        </h2>
        <div className="space-y-2 text-xs text-slate-400 leading-relaxed">
          <p>
            <strong className="text-slate-200">1. Single Language Runtime:</strong> Currently supports Python 3.11 environments only. Multi-language sandboxing (Node, Go, Rust) is out of scope.
          </p>
          <p>
            <strong className="text-slate-200">2. Docker Socket Risk:</strong> In production containerized deployments, granting the API service container access to the host Docker daemon socket (<code className="text-slate-300">/var/run/docker.sock</code>) confers root-equivalent host privileges. For hostile public multi-tenant environments, run sandboxes on isolated VM worker nodes or microVM platforms like Firecracker / gVisor.
          </p>
          <p>
            <strong className="text-slate-200">3. Evaluation Scope:</strong> The HumanEval benchmark subset is capped at 50 representative problems to adhere to API token limits while maintaining statistically meaningful pass@1 and pass@5 comparisons.
          </p>
        </div>
      </div>
    </div>
  )
}
