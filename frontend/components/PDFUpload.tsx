'use client'

import { useState, useRef } from 'react'

export interface PDFFile {
  session_id: string
  filename: string
  total_chunks: number
  total_chars: number
}

interface PDFUploadProps {
  pdfs: PDFFile[]
  onUpload: (pdf: PDFFile) => void
  onRemove: (session_id: string) => void
}

export default function PDFUpload({ pdfs, onUpload, onRemove }: PDFUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = async (files: File[]) => {
    const pdfFiles = files.filter(f => f.name.endsWith('.pdf'))
    const nonPdfs = files.filter(f => !f.name.endsWith('.pdf'))

    if (nonPdfs.length) {
      setError(`Skipped ${nonPdfs.length} non-PDF file(s)`)
    }

    if (!pdfFiles.length) return

    setUploading(true)
    setError(null)

    for (const file of pdfFiles) {
      // Check duplicate
      if (pdfs.some((p: PDFFile) => p.filename === file.name)) {
        setError(`'${file.name}' already uploaded, skipping`)
        continue
      }

      setUploadProgress(`Uploading ${file.name}...`)

      const formData = new FormData()
      formData.append('file', file)

      try {
        const res = await fetch('/api/pdf/upload', {
          method: 'POST',
          body: formData,
          signal: AbortSignal.timeout(300000),
        })

        const data = await res.json()
        if (!res.ok) {
          setError(`'${file.name}': ${data.detail || 'Upload failed'}`)
          continue
        }

        onUpload(data as PDFFile)
      } catch (err) {
        if (err instanceof Error && err.name === 'TimeoutError') {
          setError(`'${file.name}' timed out — too large`)
        } else {
          setError(`'${file.name}': ${err instanceof Error ? err.message : 'Upload failed'}`)
        }
      }
    }

    setUploadProgress('')
    setUploading(false)
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleRemove = async (session_id: string, filename: string) => {
    try {
      await fetch(`/api/pdf/remove/${session_id}`, { method: 'DELETE' })
      onRemove(session_id)
    } catch {
      setError(`Failed to remove '${filename}'`)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    if (files.length) handleFiles(files)
  }

  return (
    <div className="flex flex-col gap-2">

      {/* Loaded PDFs list */}
      {pdfs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {pdfs.map((pdf) => (
            <div
              key={pdf.session_id}
              className="flex items-center gap-2 px-3 py-1.5 bg-accent/10 border border-accent/30 rounded-xl"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#7c6af7" strokeWidth="2" strokeLinecap="round" className="shrink-0">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <div className="flex flex-col min-w-0">
                <span className="text-xs text-accent truncate max-w-[140px]">{pdf.filename}</span>
                <span className="text-[10px] text-muted">{pdf.total_chunks} chunks</span>
              </div>
              <button
                onClick={() => handleRemove(pdf.session_id, pdf.filename)}
                className="text-muted hover:text-red-400 transition-colors shrink-0"
                aria-label="Remove PDF"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Upload button */}
      <div>
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => !uploading && inputRef.current?.click()}
          className="flex items-center gap-2 px-3 py-2 border border-dashed border-border hover:border-accent/50 rounded-xl cursor-pointer transition-colors duration-200 text-muted hover:text-text-dim group w-fit"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0 group-hover:stroke-accent transition-colors">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <span className="text-xs">
            {uploading ? uploadProgress || 'Processing...' : pdfs.length > 0 ? 'Add another PDF' : 'Upload PDF'}
          </span>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            multiple                    // ← add this
            className="hidden"
            onChange={(e) => {
              const files = Array.from(e.target.files || [])
              if (files.length) handleFiles(files)   // ← changed
            }}
          />
        </div>
        {error && <p className="text-xs text-red-400 mt-1 px-1">{error}</p>}
      </div>
    </div>
  )
}