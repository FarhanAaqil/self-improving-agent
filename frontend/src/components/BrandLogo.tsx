import { useState } from 'react'

interface BrandLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  variant?: 'icon' | 'badge' | 'full'
  className?: string
  showSubtitle?: boolean
}

export default function BrandLogo({
  size = 'md',
  variant = 'icon',
  className = '',
  showSubtitle = true,
}: BrandLogoProps) {
  const [imgFailed, setImgFailed] = useState(false)

  const sizeMap = {
    sm: { box: 'h-6 w-6', img: 'h-6 w-6', text: 'text-xs', sub: 'text-[9px]' },
    md: { box: 'h-8 w-8', img: 'h-8 w-8', text: 'text-sm', sub: 'text-[11px]' },
    lg: { box: 'h-10 w-10', img: 'h-10 w-10', text: 'text-base', sub: 'text-xs' },
    xl: { box: 'h-16 w-16', img: 'h-16 w-16', text: 'text-xl', sub: 'text-sm' },
  }

  const { box, img, text, sub } = sizeMap[size]

  const logoMark = (
    <div
      className={`relative shrink-0 ${box} bg-[#10241C] border border-[#FF5A1F]/60 flex items-center justify-center overflow-hidden shadow-xs group-hover:border-[#FF5A1F] transition-colors`}
    >
      {!imgFailed ? (
        <img
          src="/logo-square.jpg"
          alt="CODE_AGENT logo"
          className={`${img} object-cover`}
          onError={() => setImgFailed(true)}
        />
      ) : (
        /* Vector SVG fallback matching exact branding */
        <svg viewBox="0 0 32 32" className="h-4/5 w-4/5" fill="none">
          <rect width="32" height="32" fill="#10241C" />
          <path d="M16 2 L29 8 V24 L16 30 L3 24 V8 Z" stroke="#FF5A1F" strokeWidth="1.5" fill="#142C23" />
          <path d="M10 12 L16 16 L10 20" stroke="#FF5A1F" strokeWidth="2" strokeLinecap="square" fill="none" />
          <line x1="17" y1="20" x2="22" y2="20" stroke="#FF5A1F" strokeWidth="2" strokeLinecap="square" />
          <path d="M14 16 L22 10" stroke="#22D3EE" strokeWidth="1.5" />
          <polygon points="19,9 24,10 22,14" fill="#22D3EE" />
        </svg>
      )}
      {/* Corner accent tick */}
      <span className="absolute top-0 right-0 h-1.5 w-1.5 bg-[#FF5A1F]" />
    </div>
  )

  if (variant === 'icon') {
    return <div className={`inline-flex items-center ${className}`}>{logoMark}</div>
  }

  return (
    <div className={`flex items-center gap-3 group select-none ${className}`}>
      {logoMark}
      <div className="flex flex-col">
        <div className={`font-mono font-bold ${text} text-ink tracking-tight group-hover:text-accent transition-colors flex items-center gap-1.5`}>
          <span>CODE_AGENT</span>
          <span className="text-[10px] px-1 py-0.2 bg-accent/10 text-accent font-mono border border-accent/30 font-medium">
            LEDGER
          </span>
        </div>
        {showSubtitle && (
          <div className={`font-mono ${sub} text-ink-tertiary tracking-normal`}>
            autonomous verification system
          </div>
        )}
      </div>
    </div>
  )
}
