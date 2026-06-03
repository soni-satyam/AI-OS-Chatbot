import { Message } from '@/types/chat'

const API_BASE = '/api'

export interface StreamMetadata {
  confidence_label: string
  confidence_score: number
  followup_questions: string[]
}

export interface StreamResult {
  content: string
  metadata: StreamMetadata | null
}

export async function* streamChat(
  messages: Message[]
): AsyncGenerator<{ type: 'token'; content: string } | { type: 'metadata'; data: StreamMetadata }> {
  const payload = {
    messages: messages.map(({ role, content }) => ({ role, content })),
    conversation_id: 'default',
  }

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`API error ${response.status}: ${error}`)
  }

  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      while (true) {
        const newlineIndex = buffer.indexOf('\n\n')
        if (newlineIndex === -1) break

        const message = buffer.slice(0, newlineIndex)
        buffer = buffer.slice(newlineIndex + 2)

        const trimmed = message.trim()
        if (!trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6).trim()
        if (data === '[DONE]') return

        try {
          const parsed = JSON.parse(data)

          if (parsed.type === 'token' && parsed.content) {
            yield { type: 'token', content: parsed.content }
          } else if (parsed.type === 'metadata') {
            yield {
              type: 'metadata',
              data: {
                confidence_label: parsed.confidence_label,
                confidence_score: parsed.confidence_score,
                followup_questions: parsed.followup_questions || [],
              },
            }
          } else if (parsed.type === 'error') {
            throw new Error(parsed.content)
          }
          // backward compat: old format had just { content }
          else if (parsed.content) {
            yield { type: 'token', content: parsed.content }
          }
        } catch (e) {
          if (e instanceof SyntaxError) continue
          throw e
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
