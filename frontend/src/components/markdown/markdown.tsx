import ReactMarkdown, {
  defaultUrlTransform,
  type Components,
} from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'

const allowedSchemes = new Set(['http:', 'https:', 'mailto:'])

function safeUrl(url: string) {
  const transformed = defaultUrlTransform(url)
  if (!transformed) return ''
  try {
    const parsed = new URL(transformed)
    return allowedSchemes.has(parsed.protocol) ? transformed : ''
  } catch {
    return ''
  }
}

function linkContent(href: string, label: React.ReactNode) {
  if (!href) return <span>{label}</span>
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline underline-offset-4"
    >
      {label}
    </a>
  )
}

export function Markdown({
  children,
  headingOffset = 0,
}: {
  children: string
  headingOffset?: number
}) {
  const heading = (depth: number, children: React.ReactNode) => {
    const level = Math.min(6, depth + headingOffset)
    const Tag = `h${level}` as keyof React.JSX.IntrinsicElements
    return (
      <Tag className={`${depth <= 2 ? 'text-base' : 'text-sm'} font-medium`}>
        {children}
      </Tag>
    )
  }
  const components: Components = {
    p: ({ children }) => <p>{children}</p>,
    h1: ({ children }) => heading(1, children),
    h2: ({ children }) => heading(2, children),
    h3: ({ children }) => heading(3, children),
    h4: ({ children }) => heading(4, children),
    h5: ({ children }) => heading(5, children),
    h6: ({ children }) => heading(6, children),
    a: ({ href = '', children }) => linkContent(safeUrl(href), children),
    img: ({ src = '', alt = '' }) => {
      const href = safeUrl(src)
      return linkContent(href, alt || src)
    },
    ul: ({ children, className, ...props }) => (
      <ul className={`list-disc pl-5 ${className ?? ''}`} {...props}>
        {children}
      </ul>
    ),
    ol: ({ children, className, ...props }) => (
      <ol className={`list-decimal pl-5 ${className ?? ''}`} {...props}>
        {children}
      </ol>
    ),
    li: ({ children, className, ...props }) => (
      <li
        className={
          className?.includes('task-list-item') ? 'list-none' : className
        }
        {...props}
      >
        {children}
      </li>
    ),
    input: ({ checked }) => (
      <input
        type="checkbox"
        checked={checked}
        disabled
        aria-label={checked ? 'Done' : 'Not done'}
        readOnly
      />
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">
        {children}
      </blockquote>
    ),
    code: ({ children, className }) => (
      <code
        className={`font-mono text-xs rounded-control bg-muted px-1 ${className ?? ''}`}
      >
        {children}
      </code>
    ),
    pre: ({ children }) => (
      <pre
        tabIndex={0}
        className="overflow-x-auto rounded-control bg-muted p-3 font-mono text-xs"
      >
        {children}
      </pre>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto">
        <table>{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border border-border px-2 py-1 font-medium">{children}</th>
    ),
    td: ({ children }) => (
      <td className="border border-border px-2 py-1">{children}</td>
    ),
    hr: () => <hr className="border-border" />,
  }

  return (
    <div className="grid gap-2 break-words text-sm">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={components}
        urlTransform={safeUrl}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
