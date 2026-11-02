import { BarChart3, Brain, History, Settings, ShieldCheck, Sparkles } from 'lucide-react'

export const NAV_ITEMS = [
  { to: '/', label: 'workbench', short: 'new', icon: Sparkles },
  { to: '/history', label: 'ledger', short: 'ledger', icon: History },
  { to: '/memory', label: 'memory', short: 'memory', icon: Brain },
  { to: '/eval', label: 'benchmarks', short: 'evals', icon: BarChart3 },
  { to: '/security', label: 'security', short: 'safety', icon: ShieldCheck },
  { to: '/settings', label: 'settings', short: 'settings', icon: Settings },
]
