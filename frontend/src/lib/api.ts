import type { CreateJobPayload, Job, JobResult, User } from './types'

const BASE = '/api/web/jobs'
const CHUNK_SIZE = 10 * 1024 * 1024 // 10 MB

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: 'include', ...init })
  if (res.status === 401) {
    window.location.href = '/auth/login'
    return Promise.reject(new Error('Nicht angemeldet'))
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Unbekannter Fehler')
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  me(): Promise<User> {
    return request('/api/web/jobs/me/info')
  },

  logout(): Promise<void> {
    return request('/auth/logout', { method: 'POST' })
  },

  // ── Jobs ──────────────────────────────────────────────────────────────────
  listJobs(): Promise<Job[]> {
    return request(BASE)
  },

  getJob(id: string): Promise<Job> {
    return request(`${BASE}/${id}`)
  },

  deleteJob(id: string): Promise<void> {
    return request(`${BASE}/${id}`, { method: 'DELETE' })
  },

  getResult(id: string): Promise<JobResult> {
    return request(`${BASE}/${id}/result`)
  },

  downloadUrl(id: string, fmt: string): string {
    return `${BASE}/${id}/download?fmt=${fmt}`
  },

  // ── Chunked upload ────────────────────────────────────────────────────────
  async uploadFile(
    file: File,
    payload: Omit<CreateJobPayload, 'filename' | 'file_size' | 'total_chunks'>,
    onProgress: (pct: number) => void,
  ): Promise<Job> {
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)

    // Create job record
    const job: Job = await request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        total_chunks: totalChunks,
        ...payload,
      } satisfies CreateJobPayload),
    })

    // Upload chunks sequentially
    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE
      const chunk = file.slice(start, start + CHUNK_SIZE)
      const form = new FormData()
      form.append('chunk', chunk, `chunk_${i}`)

      let attempt = 0
      while (attempt < 3) {
        try {
          await request(`${BASE}/${job.id}/chunks/${i}`, { method: 'POST', body: form })
          break
        } catch (e) {
          if (++attempt >= 3) throw e
          await new Promise(r => setTimeout(r, 1000 * attempt))
        }
      }

      onProgress(Math.round(((i + 1) / totalChunks) * 100))
    }

    return job
  },
}
