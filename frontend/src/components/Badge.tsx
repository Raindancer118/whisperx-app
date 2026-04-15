import { clsx } from 'clsx'
import type { JobStatus } from '../lib/types'

const config: Record<JobStatus, { label: string; cls: string; dot: string }> = {
  uploading: { label: 'Wird hochgeladen', cls: 'bg-blue-50 text-blue-700 border-blue-200', dot: 'bg-blue-500 animate-pulse' },
  queued:    { label: 'In Warteschlange', cls: 'bg-amber-50 text-amber-700 border-amber-200', dot: 'bg-amber-500' },
  processing:{ label: 'Wird transkribiert', cls: 'bg-violet-50 text-violet-700 border-violet-200', dot: 'bg-violet-500 animate-pulse' },
  done:      { label: 'Fertig', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500' },
  error:     { label: 'Fehler', cls: 'bg-red-50 text-red-700 border-red-200', dot: 'bg-red-500' },
}

export default function Badge({ status }: { status: JobStatus }) {
  const { label, cls, dot } = config[status] ?? config.error
  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border', cls)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', dot)} />
      {label}
    </span>
  )
}
