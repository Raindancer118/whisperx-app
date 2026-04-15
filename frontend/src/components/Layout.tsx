import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import type { User } from '../lib/types'
import Logo from './Logo'
import Button from './Button'

export default function Layout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.me().then(setUser).catch(() => navigate('/'))
  }, [navigate])

  const logout = async () => {
    await api.logout().catch(() => {})
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
          <Link to="/dashboard" className="flex items-center gap-3">
            <Logo size="sm" />
            <span className="text-slate-300">|</span>
            <span className="text-sm font-medium text-slate-500">WhisperX</span>
          </Link>

          <nav className="flex items-center gap-4">
            {user && (
              <span className="hidden sm:block text-sm text-slate-500 truncate max-w-[180px]">
                {user.name || user.email}
              </span>
            )}
            <Link to="/upload">
              <Button size="sm">Neue Transkription</Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={logout}>
              Abmelden
            </Button>
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">{children}</main>
    </div>
  )
}
