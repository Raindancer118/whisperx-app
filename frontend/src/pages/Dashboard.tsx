import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import type { Job } from '../lib/types'
import Layout from '../components/Layout'
import Badge from '../components/Badge'
import Button from '../components/Button'

function formatSize(bytes: number | null): string {
  if (!bytes) return '–'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '–'
  return new Intl.DateTimeFormat('de', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(iso))
}

function JobCard({ job, onDelete }: { job: Job; onDelete: () => void }) {
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Job und Transkript löschen?')) return
    setDeleting(true)
    await api.deleteJob(job.id).catch(() => {})
    onDelete()
  }

  return (
    <div
      className="group bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition-all cursor-pointer"
      onClick={() => job.status === 'done' && navigate(`/results/${job.id}`)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Filename */}
          <p className="font-medium text-navy truncate text-sm">
            {job.original_filename ?? 'Unbekannte Datei'}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">
            {formatSize(job.file_size)} · {job.model} · {formatDate(job.created_at)}
          </p>
        </div>
        <Badge status={job.status} />
      </div>

      {/* Progress bar for uploading */}
      {job.status === 'uploading' && job.total_chunks && (
        <div className="mt-3">
          <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300 rounded-full"
              style={{ width: `${Math.round((job.received_chunks / job.total_chunks) * 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {Math.round((job.received_chunks / job.total_chunks) * 100)}% hochgeladen
          </p>
        </div>
      )}

      {job.status === 'error' && job.error_message && (
        <p className="mt-2 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {job.error_message}
        </p>
      )}

      <div className="mt-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        {job.status === 'done' && (
          <Button size="sm" variant="secondary" onClick={e => { e.stopPropagation(); navigate(`/results/${job.id}`) }}>
            Ergebnis ansehen
          </Button>
        )}
        <Button size="sm" variant="ghost" loading={deleting} onClick={handleDelete}
          className="text-red-500 hover:bg-red-50">
          Löschen
        </Button>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  const loadJobs = async () => {
    setLoading(true)
    try {
      setJobs(await api.listJobs())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadJobs()
    // Poll while any job is active
    const id = setInterval(() => {
      if (jobs.some(j => j.status === 'uploading' || j.status === 'queued' || j.status === 'processing')) {
        loadJobs()
      }
    }, 4000)
    return () => clearInterval(id)
  }, [jobs.length])

  const active = jobs.filter(j => j.status !== 'done' && j.status !== 'error')
  const done = jobs.filter(j => j.status === 'done' || j.status === 'error')

  return (
    <Layout>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-display font-bold text-navy">Meine Transkriptionen</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {jobs.length === 0 ? 'Noch keine Jobs' : `${jobs.length} Job${jobs.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <Link to="/upload">
          <Button size="md">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Neu
          </Button>
        </Link>
      </div>

      {loading && jobs.length === 0 && (
        <div className="flex justify-center py-20">
          <span className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {!loading && jobs.length === 0 && (
        <div className="text-center py-20 bg-white rounded-2xl border border-dashed border-slate-300">
          <div className="w-14 h-14 rounded-2xl bg-slate-100 mx-auto flex items-center justify-center mb-4">
            <svg className="w-7 h-7 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </div>
          <h3 className="font-display font-semibold text-navy text-lg mb-1">Noch keine Transkriptionen</h3>
          <p className="text-slate-500 text-sm mb-6">Lade eine Audiodatei hoch und lass WhisperX die Arbeit machen.</p>
          <Link to="/upload"><Button>Erste Transkription starten</Button></Link>
        </div>
      )}

      {active.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Aktiv</h2>
          <div className="grid gap-3">
            {active.map(j => <JobCard key={j.id} job={j} onDelete={loadJobs} />)}
          </div>
        </section>
      )}

      {done.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Abgeschlossen</h2>
          <div className="grid gap-3">
            {done.map(j => <JobCard key={j.id} job={j} onDelete={loadJobs} />)}
          </div>
        </section>
      )}
    </Layout>
  )
}
