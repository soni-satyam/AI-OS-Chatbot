'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Message } from '@/types/chat'
import { streamChat } from '@/lib/api'
import MessageBubble from '@/components/MessageBubble'
import TypingIndicator from '@/components/TypingIndicator'
import ChatInput from '@/components/ChatInput'
import PDFUpload from '@/components/PDFUpload'
import { PDFFile } from '@/components/PDFUpload'

//AI instruction sent to LLM
const SYSTEM_MESSAGE = "You are a helpful, concise, and friendly AI assistant. Use markdown formatting when appropriate for clarity."

let idCounter = 0
const genId = () => `msg-${++idCounter}-${Date.now()}`

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]) //stores all chat messages
  const [isLoading, setIsLoading] = useState(false)       // tracks if ai responding
  const [showTyping, setShowTyping] = useState(false)    // typing animation
  const [error, setError] = useState<string | null>(null) // stores errors
  const messagesEndRef = useRef<HTMLDivElement>(null)
  // const abortRef = useRef<AbortController | null>(null)

  const [userScrolled, setUserScrolled] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const [pdfs, setPdfs] = useState<PDFFile[]>([])

  const scrollToBottom = useCallback((force = false) => {
    if (force || !userScrolled) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [userScrolled])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100

      if (isNearBottom) {
        setUserScrolled(false)
        setShowScrollBtn(false)
      } else {
        setUserScrolled(true)
        setShowScrollBtn(true)
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])


  useEffect(() => {
    scrollToBottom()
  }, [messages, showTyping, scrollToBottom])

  const handleSend = async (content: string) => {
    if (isLoading) return
    setError(null)

    const userMsg: Message = { id: genId(), role: 'user', content }
    const assistantId = genId()

    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)
    setShowTyping(true)

    const historyMessages = [
      { id: 'system', role: 'system' as const, content: SYSTEM_MESSAGE },
      ...messages,
      userMsg,
    ]

    try {
      let firstChunk = true
      let streamedText = ''
      let lastUpdate = Date.now()

      for await (const event of streamChat(historyMessages)) {

        // Token event — update message content
        if (event.type === 'token') {
          streamedText += event.content

          if (firstChunk) {
            firstChunk = false
            setShowTyping(false)
            setMessages((prev) => [
              ...prev,
              { id: assistantId, role: 'assistant', content: streamedText, isStreaming: true },
            ])
            lastUpdate = Date.now()
            continue
          }

          const now = Date.now()
          if (now - lastUpdate > 50) {
            lastUpdate = now
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: streamedText } : m
              )
            )
          }
        }

        // Metadata event — attach confidence + follow-ups to message
        else if (event.type === 'metadata') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                  ...m,
                  content: streamedText,
                  isStreaming: false,
                  confidence_label: event.data.confidence_label,
                  confidence_score: event.data.confidence_score,
                  followup_questions: event.data.followup_questions,
                }
                : m
            )
          )
          return
        }
      }

      // Final flush if metadata never came (plain chat mode)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: streamedText, isStreaming: false } : m
        )
      )
    } catch (err) {
      setShowTyping(false)
      const msg = err instanceof Error ? err.message : 'Something went wrong'
      setError(msg)
    } finally {
      setIsLoading(false)
      setShowTyping(false)
    }
  }


  const handleClear = () => {
    if (isLoading) return
    setMessages([])
    setError(null)
  }

  return (
    <div className="flex flex-col h-screen bg-bg overflow-hidden">
      {/* Header */}
      <header className="shrink-0 flex items-center justify-between px-6 py-4 border-b border-border bg-surface/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="w-8 h-8 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7c6af7" strokeWidth="2" strokeLinecap="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-text tracking-wide">AI Chat</h1>
            <p className="text-xs text-muted">Powered by Groq · Gemini Flash</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Status dot */}
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <span className={`w-1.5 h-1.5 rounded-full ${isLoading ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'}`} />
            {isLoading ? 'Thinking…' : 'Ready'}
          </div>

          {messages.length > 0 && (
            <button
              onClick={handleClear}
              disabled={isLoading}
              className="text-xs text-muted hover:text-text-dim transition-colors px-2 py-1 rounded-lg hover:bg-border disabled:opacity-50"
            >
              Clear
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <main ref={containerRef} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-4">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}

          {showTyping && <TypingIndicator />}

          {error && (
            <div className="flex items-start gap-2 text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3 animate-fade-up">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 mt-0.5">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={() => {
              setUserScrolled(false)
              setShowScrollBtn(false)
              scrollToBottom(true)
            }}
            className="
              fixed bottom-28 right-6 z-50
              w-10 h-10 rounded-full
              bg-surface border border-border
              flex items-center justify-center
              text-muted hover:text-text hover:border-accent
              shadow-lg transition-all duration-200
              hover:scale-110 active:scale-95
              animate-fade-up
    "
            aria-label="Scroll to bottom"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <polyline points="19 12 12 19 5 12" />
            </svg>
          </button>
        )}
      </main>

      {/* Input */}
      <footer className="shrink-0 px-4 py-4 border-t border-border bg-surface/30 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto flex flex-col gap-2">
          <PDFUpload
            pdfs={pdfs}
            onUpload={(pdf) => setPdfs((prev) => [...prev, pdf])}
            onRemove={(session_id) => setPdfs((prev) => prev.filter(p => p.session_id !== session_id))}
          />
          {pdfs.length > 0 && (
            <p className="text-xs text-muted">
              {pdfs.length} PDF{pdfs.length > 1 ? 's' : ''} loaded — ask anything across all documents
            </p>
          )}
          <ChatInput onSend={handleSend} disabled={isLoading} />
          <p className="text-center text-xs text-muted">
            AI can make mistakes. Verify important information.
          </p>
        </div>
      </footer>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-6 text-center animate-fade-up">
      {/* Icon */}
      <div className="w-16 h-16 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#7c6af7" strokeWidth="1.5" strokeLinecap="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>

      <div>
        <h2 className="text-xl font-semibold text-text mb-2">Start a conversation</h2>
        <p className="text-sm text-muted max-w-xs">
          Ask anything — code, writing, analysis, or just chat.
        </p>
      </div>

      {/* Suggestions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg mt-2">
        {[
          '✦ Explain quantum computing simply',
          '✦ Write a Python web scraper',
          '✦ Summarize the key ideas in stoicism',
          '✦ Help me debug my React component',
        ].map((suggestion) => (
          <div
            key={suggestion}
            className="text-xs text-muted border border-border rounded-xl px-3 py-2.5 bg-surface/50 text-left"
          >
            {suggestion}
          </div>
        ))}
      </div>
    </div>
  )
}

