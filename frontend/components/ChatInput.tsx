'use client'

import { useState, useRef, useEffect } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled: boolean
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }, [value])

  const handleSubmit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="relative flex items-end gap-3 bg-surface border border-border rounded-2xl px-4 py-3 focus-within:border-accent-dim transition-colors duration-200">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Send a message… (Enter to send, Shift+Enter for newline)"
        disabled={disabled}
        rows={1}
        className="
          flex-1 bg-transparent text-text text-sm resize-none outline-none
          placeholder:text-muted font-sans leading-relaxed
          disabled:opacity-50 disabled:cursor-not-allowed
          max-h-[200px] min-h-[24px]
        "
        style={{ scrollbarWidth: 'thin' }}
      />

      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        className="
          shrink-0 w-9 h-9 rounded-xl flex items-center justify-center
          bg-accent hover:bg-accent-dim
          disabled:opacity-30 disabled:cursor-not-allowed
          transition-all duration-200 hover:scale-105 active:scale-95
        "
        aria-label="Send message"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  )
}
