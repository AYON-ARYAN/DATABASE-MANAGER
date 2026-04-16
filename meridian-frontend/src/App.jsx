import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './context/AuthContext'
import { DbProvider } from './context/DbContext'
import { ToastProvider } from './context/ToastContext'
import LoadingSpinner from './components/ui/LoadingSpinner'

import LoginPage from './pages/LoginPage'
import QueryPage from './pages/QueryPage'
import ReviewPage from './pages/ReviewPage'
import OverviewPage from './pages/OverviewPage'
import DashboardsPage from './pages/DashboardsPage'
import DashboardViewPage from './pages/DashboardViewPage'
import AnalysisPage from './pages/AnalysisPage'
import InsightsPage from './pages/InsightsPage'
import DatabasesPage from './pages/DatabasesPage'
import CreateDatabasePage from './pages/CreateDatabasePage'
import SnapshotsPage from './pages/SnapshotsPage'
import AdminPage from './pages/AdminPage'
import CommandGuidePage from './pages/CommandGuidePage'
import CommandCenterPage from './pages/CommandCenterPage'
import SamplesPage from './pages/SamplesPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30000 } }
})

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen bg-zinc-950 flex items-center justify-center"><LoadingSpinner size="lg" /></div>
  if (!user) return <Navigate to="/login" replace />
  return <DbProvider>{children}</DbProvider>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><QueryPage /></ProtectedRoute>} />
      <Route path="/review" element={<ProtectedRoute><ReviewPage /></ProtectedRoute>} />
      <Route path="/overview" element={<ProtectedRoute><OverviewPage /></ProtectedRoute>} />
      <Route path="/dashboards" element={<ProtectedRoute><DashboardsPage /></ProtectedRoute>} />
      <Route path="/dashboards/:id" element={<ProtectedRoute><DashboardViewPage /></ProtectedRoute>} />
      <Route path="/analysis" element={<ProtectedRoute><AnalysisPage /></ProtectedRoute>} />
      <Route path="/insights" element={<ProtectedRoute><InsightsPage /></ProtectedRoute>} />
      <Route path="/databases" element={<ProtectedRoute><DatabasesPage /></ProtectedRoute>} />
      <Route path="/create-database" element={<ProtectedRoute><CreateDatabasePage /></ProtectedRoute>} />
      <Route path="/snapshots" element={<ProtectedRoute><SnapshotsPage /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
      <Route path="/command-guide" element={<ProtectedRoute><CommandGuidePage /></ProtectedRoute>} />
      <Route path="/command-center" element={<ProtectedRoute><CommandCenterPage /></ProtectedRoute>} />
      <Route path="/samples" element={<ProtectedRoute><SamplesPage /></ProtectedRoute>} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter basename="/app">
            <AppRoutes />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
