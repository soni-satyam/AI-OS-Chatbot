import type { Metadata } from 'next'
import './globals.css'


// SEO 
export const metadata: Metadata = {
  title: 'AI Chat',
  description: 'Streaming AI chatbot powered by Puter',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
