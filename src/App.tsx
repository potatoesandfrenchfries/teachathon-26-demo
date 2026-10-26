import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProgressProvider } from './context/ProgressContext'
import { StudentMap } from './components/WorldMap/StudentMap'
import { LevelPage } from './components/Level/LevelPage'
import { ReviewPage } from './components/Review/ReviewPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ProgressProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<StudentMap />} />
            <Route path="/level/:levelId" element={<LevelPage />} />
            <Route path="/review" element={<ReviewPage />} />
          </Routes>
        </BrowserRouter>
      </ProgressProvider>
    </QueryClientProvider>
  )
}

export default App
