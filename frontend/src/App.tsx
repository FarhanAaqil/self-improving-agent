import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import EvalDashboard from './pages/EvalDashboard'
import NewRun from './pages/NewRun'
import RunDetail from './pages/RunDetail'
import RunHistory from './pages/RunHistory'
import SecurityAbout from './pages/SecurityAbout'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<NewRun />} />
          <Route path="/history" element={<RunHistory />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/eval" element={<EvalDashboard />} />
          <Route path="/security" element={<SecurityAbout />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
