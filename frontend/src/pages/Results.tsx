import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api } from '../lib/api'
import type { Job, JobResult } from '../lib/types'
import Layout from '../components/Layout'
import Badge from '../components/Badge'
import Button from '../components/Button'

function formatDate(iso: string | null) {
  if (!iso) return '–'
  return new Intl.DateTimeFormat('de', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(iso))
}

export default function Results() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()

  const [job, setJob] = useState<Job | null>(null)
  const [result, setResult] = useState<JobResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    if (!jobId) return
    try {
      const j = await api.getJob(jobId)
      setJob(j)
      if (j.status === 'done') {
        const r = await api.getResult(jobId)
        setResult(r)
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // Poll until done
    const id = setInterval(() => {
      if (job && (job.status === 'queued' || job.status === 'processing')) load()
    }, 5000)
    return () => clearInterval(id)
  }, [jobId, job?.status])

  if (loading) return (
    <Layout>
      <div className="flex justify-center py-20">
        <span className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    </Layout>
  )

  if (error || !job) return (
    <Layout>
      <div className="text-center py-20">
        <p className="text-red-600 mb-4">{error ?? 'Job nicht gefunden'}</p>
        <Button onClick={() => navigate('/dashboard')} variant="secondary">Zurück</Button>
      </div>
    </Layout>
  )

  return (
    <Layout>
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-display font-bold text-navy truncate max-w-lg">
              {job.original_filename ?? 'Transkription'}
            </h1>
            <Badge status={job.status} />
          </div>
          <p className="text-sm text-slate-500">
            Erstellt: {formatDate(job.created_at)}
            {job.completed_at && ` · Fertig: ${formatDate(job.completed_at)}`}
            {' · '}{job.model}
          </p>
        </div>

        <div className="flex gap-2">
          {job.status === 'done' && (
            <>
              {(['md', 'txt', 'json'] as const).map(fmt => (
                <a key={fmt} href={api.downloadUrl(job.id, fmt)}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-50 transition-colors">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  .{fmt}
                </a>
              ))}
            </>
          )}
          <Button variant="secondary" onClick={() => navigate('/dashboard')}>
            Dashboard
          </Button>
        </div>
      </div>

      {/* States */}
      {job.status === 'queued' && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-8 text-center">
          <span className="h-8 w-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto block mb-3" />
          <p className="font-semibold text-amber-700">In der Warteschlange</p>
          <p className="text-sm text-amber-600 mt-1">Die Transkription startet in Kürze…</p>
        </div>
      )}

      {job.status === 'processing' && (
        <div className="bg-violet-50 border border-violet-200 rounded-2xl p-8 text-center">
          <span className="h-8 w-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto block mb-3" />
          <p className="font-semibold text-violet-700">Wird transkribiert</p>
          <p className="text-sm text-violet-600 mt-1">WhisperX arbeitet gerade — das kann je nach Dateigröße einige Minuten dauern.</p>
        </div>
      )}

      {job.status === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
          <p className="font-semibold text-red-700 mb-1">Fehler bei der Transkription</p>
          <p className="text-sm text-red-600 font-mono">{job.error_message}</p>
        </div>
      )}

      {/* Result content */}
      {job.status === 'done' && result && (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {result.format === 'md' ? 'Markdown' : result.format === 'txt' ? 'Plaintext' : 'JSON'}
            </span>
            <span className="text-xs text-slate-400">
              {result.content.length.toLocaleString('de')} Zeichen
            </span>
          </div>

          <div className="p-6 max-h-[70vh] overflow-y-auto scrollbar-thin">
            {result.format === 'md' ? (
              <div className="prose prose-slate prose-sm max-w-none">
                <ReactMarkdown>{result.content}</ReactMarkdown>
              </div>
            ) : result.format === 'json' ? (
              <pre className="text-xs text-slate-700 whitespace-pre-wrap break-all font-mono">
                {JSON.stringify(JSON.parse(result.content), null, 2)}
              </pre>
            ) : (
              <pre className="text-sm text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                {result.content}
              </pre>
            )}
          </div>
        </div>
      )}
    </Layout>
  )
}
