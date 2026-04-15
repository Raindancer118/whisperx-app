import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import Logo from '../components/Logo'
import Button from '../components/Button'

export default function Login() {
  const [params] = useSearchParams()
  const error = params.get('error')

  // If already logged in, try to redirect
  useEffect(() => {
    fetch('/api/web/jobs/me/info', { credentials: 'include' })
      .then(r => { if (r.ok) window.location.href = '/dashboard' })
      .catch(() => {})
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 flex flex-col">
      {/* Header */}
      <header className="p-6 sm:p-8">
        <Logo size="md" />
      </header>

      {/* Center card */}
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden">
            {/* Navy top bar */}
            <div className="h-1.5 bg-gradient-to-r from-navy to-accent" />

            <div className="px-8 py-10">
              {/* Icon */}
              <div className="w-14 h-14 rounded-2xl bg-navy-50 border border-navy-100 flex items-center justify-center mb-6">
                <svg className="w-7 h-7 text-navy" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                </svg>
              </div>

              <h1 className="text-2xl font-display font-bold text-navy mb-1">
                WhisperX
              </h1>
              <p className="text-slate-500 text-sm mb-8">
                Audio-Transkription mit Sprecher-Diarisierung
              </p>

              {error && (
                <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                  Anmeldung fehlgeschlagen. Bitte versuche es erneut.
                </div>
              )}

              <a href="/auth/login" className="block w-full">
                <Button size="lg" className="w-full">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
                  </svg>
                  Mit Volantic anmelden
                </Button>
              </a>

              <p className="mt-6 text-center text-xs text-slate-400">
                Du wirst zu{' '}
                <span className="font-medium text-slate-500">accounts.volantic.de</span>
                {' '}weitergeleitet
              </p>
            </div>
          </div>

          {/* Tagline */}
          <p className="mt-6 text-center text-sm text-slate-400">
            Powered by{' '}
            <span className="font-medium text-slate-500">WhisperX</span>
            {' '}+{' '}
            <span className="font-medium text-slate-500">pyannote.audio</span>
          </p>
        </div>
      </div>
    </div>
  )
}
