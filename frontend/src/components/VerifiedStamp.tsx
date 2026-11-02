/** The ledger's rubber stamp. Lands once when a run is verified (or stops). */
export default function VerifiedStamp({ status, attempt }: { status: 'verified' | 'stopped'; attempt?: number }) {
  const verified = status === 'verified'
  return (
    <div
      role="img"
      aria-label={verified ? `Verified${attempt ? ` on attempt ${attempt}` : ''}` : 'Not verified'}
      className={`inline-flex animate-stamp-in select-none flex-col items-center border-[3px] px-4 py-1.5 font-mono font-black uppercase leading-none tracking-[0.2em] ${
        verified ? 'border-status-success text-status-success' : 'border-status-danger text-status-danger'
      }`}
      style={{ maskImage: 'radial-gradient(circle at 30% 40%, #000 60%, rgba(0,0,0,0.75) 100%)' }}
    >
      <span className="text-lg">{verified ? 'verified' : 'unsolved'}</span>
      <span className="mt-1 text-[9px] tracking-[0.3em]">
        {verified ? (attempt ? `attempt ${attempt} · sandboxed` : 'sandboxed') : 'lesson saved'}
      </span>
    </div>
  )
}
