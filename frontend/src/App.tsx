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
            <Route element={<AppShell />}>
              <Route path="/" element={<Workbench />} />
              <Route path="/runs/:runId" element={<RunTheater />} />
              <Route path="/history" element={<Ledger />} />
              <Route path="/memory" element={<MemoryExplorer />} />
              <Route path="/eval" element={<Benchmarks />} />
              <Route path="/security" element={<Security />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/compare/:groupId" element={<Compare />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
