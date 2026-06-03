export type Role = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  role: Role
  content: string
  isStreaming?: boolean
  // New fields from production RAG
  confidence_label?: string     // "High" | "Medium" | "Low" | "None"
  confidence_score?: number     // 0.0 to 1.0
  followup_questions?: string[] // 3 suggested follow-up questions
}

export interface ChatState {
  messages: Message[]
  isLoading: boolean
  error: string | null
}
