import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { isAuthError } from './api/client'
import AppShell from './components/AppShell'
import { Skeleton } from './components/ui'
import Workbench from './pages/Workbench'

// Heavier pages (charts, diff, highlighting) load on first visit
const RunTheater = lazy(() => import('./pages/RunTheater'))
const Ledger = lazy(() => import('./pages/Ledger'))
const MemoryExplorer = lazy(() => import('./pages/MemoryExplorer'))
const Benchmarks = lazy(() => import('./pages/Benchmarks'))
const Security = lazy(() => import('./pages/Security'))
const Settings = lazy(() => import('./pages/Settings'))
const NotFound = lazy(() => import('./pages/NotFound'))
const Compare = lazy(() => import('./pages/Compare'))
const Shared = lazy(() => import('./pages/Shared'))
const Login = lazy(() => import('./pages/auth/Login'))
const Signup = lazy(() => import('./pages/auth/Signup'))
const Verify = lazy(() => import('./pages/auth/Verify'))
const Forgot = lazy(() => import('./pages/auth/Forgot'))
const Reset = lazy(() => import('./pages/auth/Reset'))
const Pricing = lazy(() => import('./pages/Pricing'))
const Landing = lazy(() => import('./pages/Landing'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Retrying a missing key only spams the server
      retry: (count, error) => !isAuthError(error) && count < 1,
    },
  },
})

function PageFallback() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Skeleton className="h-10 w-1/2" />
      <Skeleton className="h-64" />
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/shared/:token" element={<Shared />} />
            <Route path="/welcome" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="/forgot" element={<Forgot />} />
            <Route path="/reset" element={<Reset />} />
            <Route element={<AppShell />}>
              <Route path="/" element={<Workbench />} />
              <Route path="/runs/:runId" element={<RunTheater />} />
              <Route path="/history" element={<Ledger />} />
              <Route path="/memory" element={<MemoryExplorer />} />
              <Route path="/eval" element={<Benchmarks />} />
              <Route path="/security" element={<Security />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/compare/:groupId" element={<Compare />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
