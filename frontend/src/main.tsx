import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { applyPreferences } from './hooks/usePreferences'
import './index.css'

// Apply theme before first paint so there's no flash of the wrong colors
applyPreferences()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
