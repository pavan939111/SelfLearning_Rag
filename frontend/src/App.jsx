import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import '@fontsource/jetbrains-mono'
import '@fontsource/syne'
import './styles/globals.css'
import './styles/globals.css'
import Sidebar from './components/shared/Sidebar'
import Chat from './pages/Chat'
import Transparency from './pages/Transparency'
import Admin from './pages/Admin'

export default function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <div style={{ display: 'flex', minHeight: '100vh', width: '100vw', background: 'var(--bg-primary)' }}>
        <Sidebar />
        <main style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/transparency" element={<Transparency />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
