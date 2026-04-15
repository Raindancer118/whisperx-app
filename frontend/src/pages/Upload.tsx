import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { clsx } from 'clsx'
import { api } from '../lib/api'
import Layout from '../components/Layout'
import Button from '../components/Button'

// ── Step indicator ────────────────────────────────────────────────────────────
const STEPS = ['Datei', 'Optionen', 'E-Mail', 'Upload']

function StepIndicator({ current }: { current: number }) {
  return (
    <nav className="flex items-center gap-0 mb-10">
      {STEPS.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <div key={i} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <div className={clsx(
                'w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-semibold transition-all',
                done  ? 'bg-accent border-accent text-white' :
                active ? 'bg-white border-accent text-accent' :
                         'bg-white border-slate-200 text-slate-400'
              )}>
                {done ? (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                ) : i + 1}
              </div>
              <span className={clsx(
                'text-xs font-medium whitespace-nowrap',
                active ? 'text-accent' : done ? 'text-slate-500' : 'text-slate-400'
              )}>{label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={clsx(
                'flex-1 h-px mx-2 mb-4 transition-colors',
                done ? 'bg-accent' : 'bg-slate-200'
              )} />
            )}
          </div>
        )
      })}
    </nav>
  )
}

// ── Step 1: File drop ─────────────────────────────────────────────────────────
function Step1({ onNext }: { onNext: (file: File) => void }) {
  const [file, setFile] = useState<File | null>(null)

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'audio/*': [], 'video/*': [] },
    maxFiles: 1,
    multiple: false,
  })

  const fmt = (b: number) => b > 1e9 ? `${(b/1e9).toFixed(2)} GB` : `${(b/1e6).toFixed(1)} MB`

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-display font-bold text-navy">Audiodatei auswählen</h2>
        <p className="text-sm text-slate-500 mt-1">MP3, WAV, M4A, MP4, WEBM — bis zu mehreren GB</p>
      </div>

      <div {...getRootProps()} className={clsx(
        'border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all',
        isDragActive ? 'border-accent bg-accent/5' : 'border-slate-300 hover:border-slate-400 bg-white',
        file && 'border-emerald-400 bg-emerald-50'
      )}>
        <input {...getInputProps()} />
        {file ? (
          <div className="space-y-2">
            <div className="w-12 h-12 rounded-xl bg-emerald-100 mx-auto flex items-center justify-center">
              <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m9 9 10.5-3m0 6.553v3.75a2.25 2.25 0 0 1-1.632 2.163l-1.32.377a1.803 1.803 0 1 1-.99-3.467l2.31-.66a2.25 2.25 0 0 0 1.632-2.163Zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 0 1-1.632 2.163l-1.32.377a1.803 1.803 0 0 1-.99-3.467l2.31-.66A2.25 2.25 0 0 0 9 15.553Z" />
              </svg>
            </div>
            <p className="font-medium text-navy">{file.name}</p>
            <p className="text-sm text-slate-500">{fmt(file.size)}</p>
            <p className="text-xs text-emerald-600">Datei ausgewählt — klicke um zu ändern</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-xl bg-slate-100 mx-auto flex items-center justify-center">
              <svg className="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-slate-700">
                {isDragActive ? 'Loslassen zum Hochladen' : 'Datei hier ablegen oder klicken'}
              </p>
              <p className="text-sm text-slate-400 mt-1">Drag & Drop unterstützt</p>
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <Button disabled={!file} onClick={() => file && onNext(file)}>
          Weiter
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
        </Button>
      </div>
    </div>
  )
}

// ── Step 2: Options ───────────────────────────────────────────────────────────
interface Options { model: string; language: string; outputFormat: string; diarize: boolean }

function Step2({ onNext, onBack }: { onNext: (o: Options) => void; onBack: () => void }) {
  const [model, setModel] = useState('large-v3')
  const [language, setLanguage] = useState('')
  const [outputFormat, setOutputFormat] = useState('md')
  const [diarize, setDiarize] = useState(true)

  const sel = 'w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent bg-white'
  const label = 'block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5'

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-display font-bold text-navy">Transkriptions-Optionen</h2>
        <p className="text-sm text-slate-500 mt-1">Wähle Modell, Sprache und Ausgabeformat</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={label}>Modell</label>
            <select className={sel} value={model} onChange={e => setModel(e.target.value)}>
              <option value="large-v3">large-v3 (empfohlen)</option>
              <option value="medium">medium (schneller)</option>
              <option value="small">small (am schnellsten)</option>
              <option value="base">base</option>
            </select>
          </div>
          <div>
            <label className={label}>Sprache</label>
            <select className={sel} value={language} onChange={e => setLanguage(e.target.value)}>
              <option value="">Automatisch erkennen</option>
              <option value="de">Deutsch</option>
              <option value="en">Englisch</option>
              <option value="fr">Französisch</option>
              <option value="es">Spanisch</option>
              <option value="it">Italienisch</option>
              <option value="pt">Portugiesisch</option>
              <option value="nl">Niederländisch</option>
              <option value="pl">Polnisch</option>
            </select>
          </div>
        </div>

        <div>
          <label className={label}>Ausgabeformat</label>
          <div className="grid grid-cols-3 gap-3">
            {[
              { v: 'md', label: 'Markdown', desc: 'Sprecher fett, strukturiert' },
              { v: 'txt', label: 'Text', desc: 'Einfacher Plaintext' },
              { v: 'json', label: 'JSON', desc: 'Maschinenlesbar' },
            ].map(({ v, label: l, desc }) => (
              <button key={v} onClick={() => setOutputFormat(v)}
                className={clsx(
                  'border rounded-xl p-3 text-left transition-all',
                  outputFormat === v
                    ? 'border-accent bg-accent/5 text-accent'
                    : 'border-slate-200 bg-white hover:border-slate-300 text-slate-700'
                )}>
                <p className="font-semibold text-sm">{l}</p>
                <p className="text-xs opacity-70 mt-0.5">{desc}</p>
              </button>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <div className={clsx(
            'w-10 h-6 rounded-full transition-colors relative',
            diarize ? 'bg-accent' : 'bg-slate-200'
          )} onClick={() => setDiarize(!diarize)}>
            <div className={clsx(
              'absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform',
              diarize ? 'translate-x-4' : 'translate-x-0.5'
            )} />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">Sprecher-Diarisierung</p>
            <p className="text-xs text-slate-400">Unterscheidet verschiedene Sprecher (pyannote.audio)</p>
          </div>
        </label>
      </div>

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>Zurück</Button>
        <Button onClick={() => onNext({ model, language, outputFormat, diarize })}>
          Weiter
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
        </Button>
      </div>
    </div>
  )
}

// ── Step 3: Email ─────────────────────────────────────────────────────────────
function Step3({
  userEmail,
  onNext,
  onBack,
}: {
  userEmail: string
  onNext: (email: string | null) => void
  onBack: () => void
}) {
  const [choice, setChoice] = useState<'account' | 'custom' | 'none'>('account')
  const [custom, setCustom] = useState('')

  const next = () => {
    if (choice === 'account') onNext(userEmail)
    else if (choice === 'custom') onNext(custom || null)
    else onNext(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-display font-bold text-navy">E-Mail-Benachrichtigung</h2>
        <p className="text-sm text-slate-500 mt-1">Wir schicken dir Bescheid, wenn das Transkript fertig ist</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-3">
        {[
          { v: 'account' as const, label: 'Account-E-Mail verwenden', sub: userEmail },
          { v: 'custom'  as const, label: 'Andere E-Mail-Adresse', sub: 'Eigene Adresse eingeben' },
          { v: 'none'    as const, label: 'Keine Benachrichtigung', sub: 'Ergebnis manuell abrufen' },
        ].map(({ v, label, sub }) => (
          <label key={v} className={clsx(
            'flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all',
            choice === v ? 'border-accent bg-accent/5' : 'border-slate-200 hover:border-slate-300'
          )}>
            <div className={clsx(
              'w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors',
              choice === v ? 'border-accent' : 'border-slate-300'
            )}>
              {choice === v && <div className="w-2 h-2 rounded-full bg-accent" />}
            </div>
            <div onClick={() => setChoice(v)}>
              <p className="text-sm font-medium text-slate-700">{label}</p>
              <p className="text-xs text-slate-400">{sub}</p>
            </div>
          </label>
        ))}

        {choice === 'custom' && (
          <input
            type="email"
            placeholder="name@beispiel.de"
            value={custom}
            onChange={e => setCustom(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent mt-1"
          />
        )}
      </div>

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>Zurück</Button>
        <Button onClick={next}
          disabled={choice === 'custom' && !custom.includes('@')}>
          Upload starten
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
          </svg>
        </Button>
      </div>
    </div>
  )
}

// ── Step 4: Upload progress / done ────────────────────────────────────────────
function Step4({ file, options, email, onDone }: {
  file: File
  options: Options
  email: string | null
  onDone: (jobId: string) => void
}) {
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [started, setStarted] = useState(false)
  const navigate = useNavigate()

  const run = useCallback(async () => {
    if (started) return
    setStarted(true)
    try {
      const job = await api.uploadFile(
        file,
        {
          model: options.model,
          language: options.language || undefined,
          output_format: options.outputFormat,
          diarize: options.diarize,
          notify_email: email || undefined,
        },
        setProgress,
      )
      onDone(job.id)
    } catch (e: any) {
      setError(e.message ?? 'Upload fehlgeschlagen')
    }
  }, [file, options, email, onDone, started])

  // Auto-start
  useState(() => { run() })

  if (error) {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-red-100 mx-auto flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
          </div>
          <p className="font-semibold text-red-700 mb-1">Upload fehlgeschlagen</p>
          <p className="text-sm text-red-600">{error}</p>
          <Button className="mt-4" onClick={() => navigate('/upload')} variant="secondary">
            Erneut versuchen
          </Button>
        </div>
      </div>
    )
  }

  if (progress < 100) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-display font-bold text-navy">Datei wird hochgeladen</h2>
          <p className="text-sm text-slate-500 mt-1">{file.name}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-8 space-y-4">
          <div className="flex justify-between text-sm">
            <span className="text-slate-600">Fortschritt</span>
            <span className="font-semibold text-navy">{progress}%</span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 text-center">
            Große Dateien werden in Blöcken übertragen — bitte Fenster nicht schließen
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="bg-white border border-emerald-200 rounded-2xl p-8 text-center">
        <div className="w-14 h-14 rounded-full bg-emerald-100 mx-auto flex items-center justify-center mb-4">
          <svg className="w-7 h-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
          </svg>
        </div>
        <h3 className="font-display font-bold text-navy text-lg mb-1">Upload abgeschlossen!</h3>
        <p className="text-sm text-slate-500">
          Die Transkription läuft jetzt im Hintergrund.
          {email && <><br />Du erhältst eine E-Mail an <strong>{email}</strong>, wenn sie fertig ist.</>}
        </p>
        <Button className="mt-6" onClick={() => navigate('/dashboard')}>
          Zum Dashboard
        </Button>
      </div>
    </div>
  )
}

// ── Upload wizard (root) ──────────────────────────────────────────────────────
export default function Upload() {
  const [step, setStep] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [options, setOptions] = useState<Options | null>(null)
  const [email, setEmail] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [userEmail] = useState('') // fetched below
  const navigate = useNavigate()

  // Fetch user email for pre-fill
  const [resolvedEmail, setResolvedEmail] = useState('')
  useState(() => {
    api.me().then(u => setResolvedEmail(u.email)).catch(() => {})
  })

  if (jobId && step === 3) {
    return (
      <Layout>
        <div className="max-w-xl mx-auto">
          <StepIndicator current={3} />
          <Step4 file={file!} options={options!} email={email} onDone={id => setJobId(id)} />
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="max-w-xl mx-auto">
        <StepIndicator current={step} />

        {step === 0 && <Step1 onNext={f => { setFile(f); setStep(1) }} />}
        {step === 1 && <Step2 onNext={o => { setOptions(o); setStep(2) }} onBack={() => setStep(0)} />}
        {step === 2 && (
          <Step3
            userEmail={resolvedEmail}
            onNext={em => { setEmail(em); setStep(3) }}
            onBack={() => setStep(1)}
          />
        )}
        {step === 3 && file && options && (
          <Step4
            file={file}
            options={options}
            email={email}
            onDone={id => { setJobId(id) }}
          />
        )}
      </div>
    </Layout>
  )
}
