import type { Metadata } from 'next'
import Script from 'next/script'
import './globals.css'
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: 'AI Chat',
  description: 'Streaming AI chatbot powered by Puter',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>

        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
        />
      </body>
    </html>
  )
}