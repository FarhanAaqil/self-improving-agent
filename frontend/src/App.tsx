import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

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
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <header className="border-b border-slate-800 bg-slate-900/50 px-6 py-4">
          <h1 className="text-xl font-semibold tracking-tight">Self-Improving Code Agent</h1>
        </header>
        <main className="flex-1 p-6">
          <p className="text-slate-400">Agent interface initialized with TanStack Query.</p>
        </main>
      </div>
    </QueryClientProvider>
  )
}

export default App
