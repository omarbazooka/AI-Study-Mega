import React from "react";
import { MessageItem } from "@/types/api/sessions";
import { Citation } from "@/types/api/ai";
import { CitationList } from "./CitationList";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import katex from "katex";

interface ChatMessageProps {
  message: MessageItem;
  citations?: Citation[];
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, citations }) => {
  const isUser = message.role === "user";

  const renderWithMath = (content: string): React.ReactNode[] => {
    // Handle all LaTeX delimiters: $$...$$, \[...\], $...$, \(...\)
    let processed = content;
    processed = processed.replace(/\$\$([\s\S]+?)\$\$/g, (_, l) => `\x00BLOCK\x00${l}\x00ENDBLOCK\x00`);
    processed = processed.replace(/\\\[([\s\S]+?)\\\]/g, (_, l) => `\x00BLOCK\x00${l}\x00ENDBLOCK\x00`);
    processed = processed.replace(/\\\(([\s\S]+?)\\\)/g, (_, l) => `\x00INLINE\x00${l}\x00ENDINLINE\x00`);
    processed = processed.replace(/\$([^\$\n]+?)\$/g, (_, l) => `\x00INLINE\x00${l}\x00ENDINLINE\x00`);

    const parts: React.ReactNode[] = [];
    const blockSplit = processed.split(/(\x00BLOCK\x00[\s\S]*?\x00ENDBLOCK\x00)/);
    blockSplit.forEach((segment, i) => {
      if (segment.startsWith('\x00BLOCK\x00')) {
        const latex = segment.replace('\x00BLOCK\x00', '').replace('\x00ENDBLOCK\x00', '').trim();
        try {
          const html = katex.renderToString(latex, { displayMode: true, throwOnError: false });
          parts.push(<div key={`block-${i}`} dangerouslySetInnerHTML={{ __html: html }} className="my-3 overflow-x-auto text-center" />);
        } catch {
          parts.push(<div key={`block-${i}`} className="text-red-400 font-mono text-xs my-2">{latex}</div>);
        }
      } else {
        const inlineSplit = segment.split(/(\x00INLINE\x00[\s\S]*?\x00ENDINLINE\x00)/);
        inlineSplit.forEach((inlineSeg, j) => {
          if (inlineSeg.startsWith('\x00INLINE\x00')) {
            const latex = inlineSeg.replace('\x00INLINE\x00', '').replace('\x00ENDINLINE\x00', '').trim();
            try {
              const html = katex.renderToString(latex, { displayMode: false, throwOnError: false });
              parts.push(<span key={`inline-${i}-${j}`} dangerouslySetInnerHTML={{ __html: html }} />);
            } catch {
              parts.push(<span key={`inline-${i}-${j}`} className="text-red-400 font-mono text-xs">{latex}</span>);
            }
          } else if (inlineSeg.trim()) {
            parts.push(
              <ReactMarkdown
                key={`md-${i}-${j}`}
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ node, ...props }) => <p className="text-sm text-zinc-300 leading-relaxed font-medium mb-2" {...props} />,
                  ul: ({ node, ...props }) => <ul className="ml-4 list-disc text-sm text-zinc-300 leading-relaxed font-medium mb-1" {...props} />,
                  li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                  strong: ({ node, ...props }) => <strong className="font-bold text-zinc-100" {...props} />,
                  h4: ({ node, ...props }) => <h4 className="text-sm font-bold text-zinc-300 mt-2 mb-1" {...props} />,
                  h3: ({ node, ...props }) => <h3 className="text-md font-bold text-zinc-200 mt-3 mb-1.5" {...props} />,
                  h2: ({ node, ...props }) => <h2 className="text-lg font-bold text-zinc-100 mt-4 mb-2" {...props} />,
                  h1: ({ node, ...props }) => <h1 className="text-xl font-bold text-zinc-100 mt-5 mb-3" {...props} />,
                  table: ({ node, ...props }) => <div className="overflow-x-auto my-3 max-w-full"><table className="border-collapse border border-zinc-800 w-full text-xs text-zinc-300" {...props} /></div>,
                  thead: ({ node, ...props }) => <thead className="bg-zinc-800/40" {...props} />,
                  th: ({ node, ...props }) => <th className="border border-zinc-800 px-3 py-2 text-left font-bold text-zinc-200" {...props} />,
                  td: ({ node, ...props }) => <td className="border border-zinc-800 px-3 py-2 text-left" {...props} />,
                }}
              >
                {inlineSeg}
              </ReactMarkdown>
            );
          }
        });
      }
    });
    return parts;
  };

  const renderContent = (content: string) => {
    return <>{renderWithMath(content)}</>;
  };

  return (
    <div className={`flex flex-col gap-1.5 max-w-[85%] ${isUser ? "self-end items-end" : "self-start items-start"}`}>
      {/* Bubble container */}
      <div
        className={`px-4.5 py-3 rounded-2xl transition-all duration-200 shadow-md ${
          isUser
            ? "bg-primary text-white rounded-br-none font-semibold text-sm"
            : "bg-zinc-900/60 border border-zinc-800 text-zinc-200 rounded-bl-none"
        }`}
      >
        {isUser ? (
          <p className="text-sm leading-relaxed font-medium whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="flex flex-col">
            {renderContent(message.content)}
            {citations && citations.length > 0 && <CitationList citations={citations} />}
          </div>
        )}
      </div>
      
      {/* Timestamp info */}
      <span className="text-[10px] text-zinc-500 font-mono px-1">
        {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  );
};
