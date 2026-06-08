import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  className?: string;
  emptyFallback?: string;
};

export default function MarkdownContent({ content, className = "", emptyFallback }: Props) {
  const trimmed = content.trim();
  if (!trimmed) {
    return emptyFallback ? <p className="muted markdown-empty">{emptyFallback}</p> : null;
  }

  return (
    <div className={`markdown-body ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
