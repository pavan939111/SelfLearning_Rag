import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import '@fontsource/jetbrains-mono'
import '@fontsource/syne'
import './styles/globals.css'
import Navbar from './components/shared/Navbar'
import Chat from './pages/Chat'
import Transparency from './pages/Transparency'
import Admin from './pages/Admin'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
        <Navbar />
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/transparency" element={<Transparency />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
