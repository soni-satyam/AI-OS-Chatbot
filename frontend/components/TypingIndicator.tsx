'use client'

export default function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-up">
      {/* Avatar */}
      <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold bg-surface border border-border text-accent">
        AI
      </div>

      {/* Dots */}
      <div className="bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-4 flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-muted inline-block"
            style={{
              animation: 'typingDot 1.2s ease-in-out infinite',
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
        <style jsx>{`
          @keyframes typingDot {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
            30% { transform: translateY(-6px); opacity: 1; }
          }
        `}</style>
      </div>
    </div>
  )
}
