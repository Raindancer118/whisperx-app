export interface User {
  user_id: string
  email: string
  name: string
}

export type JobStatus = 'uploading' | 'queued' | 'processing' | 'done' | 'error'

export interface Job {
  id: string
  status: JobStatus
  original_filename: string | null
  file_size: number | null
  model: string
  language: string | null
  output_format: 'md' | 'txt' | 'json'
  diarize: boolean
  error_message: string | null
  total_chunks: number | null
  received_chunks: number
  created_at: string
  updated_at: string | null
  completed_at: string | null
}

export interface CreateJobPayload {
  filename: string
  file_size: number
  total_chunks: number
  model: string
  language?: string
  output_format: string
  diarize: boolean
  notify_email?: string
}

export interface JobResult {
  content: string
  format: string
  filename: string | null
}
