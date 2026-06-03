'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface MarkdownProps {
  content: string
  isStreaming?: boolean
}

export default function Markdown({ content, isStreaming }: MarkdownProps) {
  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const isBlock = !!(node?.position?.start.line !== node?.position?.end.line || match)

            if (isBlock && match) {
              return (
                <SyntaxHighlighter
                  style={oneDark as Record<string, React.CSSProperties>}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    fontSize: '0.8rem',
                    fontFamily: "'JetBrains Mono', monospace",
                    background: '#0d0d1a',
                  }}
                  codeTagProps={{
                    style: { fontFamily: "'JetBrains Mono', monospace" },
                  }}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              )
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="typing-cursor" />}
    </div>
  )
}
