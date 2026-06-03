'use client'

import { Message } from '@/types/chat'
import Markdown from './Markdown'

interface MessageBubbleProps {
  message: Message
  onFollowup?: (q: string) => void
}

function ConfidenceBadge({ label, score }: { label: string; score: number }) {
  const colors = {
    High: 'bg-green-500/10 text-green-400 border-green-500/20',
    Medium: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    Low: 'bg-red-500/10 text-red-400 border-red-500/20',
    None: 'bg-muted/10 text-muted border-muted/20',
  }
  const color = colors[label as keyof typeof colors] || colors.None
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${color}`}>
      <span className="w-1 h-1 rounded-full bg-current" />
      {label} confidence · {Math.round(score * 100)}%
    </span>
  )
}

export default function MessageBubble({ message, onFollowup }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 animate-fade-up ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold
        ${isUser ? 'bg-accent text-white' : 'bg-surface border border-border text-accent'}`}>
        {isUser ? 'U' : 'AI'}
      </div>

      <div className="flex flex-col gap-2 max-w-[80%]">
        {/* Bubble */}
        <div className={`rounded-2xl px-4 py-3
          ${isUser
            ? 'bg-accent text-white rounded-tr-sm'
            : 'bg-surface border border-border text-text rounded-tl-sm'}`}>
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          ) : (
            <Markdown content={message.content} isStreaming={message.isStreaming} />
          )}
        </div>

        {/* Confidence badge — only for assistant messages after streaming */}
        {!isUser && !message.isStreaming && message.confidence_label && (
          <div className="px-1">
            <ConfidenceBadge
              label={message.confidence_label}
              score={message.confidence_score || 0}
            />
          </div>
        )}

        {/* Follow-up questions */}
        {!isUser && !message.isStreaming && message.followup_questions && message.followup_questions.length > 0 && (
          <div className="flex flex-col gap-1.5 px-1">
            <p className="text-[10px] text-muted uppercase tracking-wide">You may also ask</p>
            {message.followup_questions.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowup?.(q)}
                className="text-xs text-left text-text-dim hover:text-accent border border-border hover:border-accent/40
                           rounded-lg px-3 py-1.5 bg-surface/50 transition-colors duration-150"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
