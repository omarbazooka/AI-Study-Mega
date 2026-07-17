/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
import React, { useState } from "react";
import { aiService } from "@/services/ai.service";
import { AIResponse, Citation } from "@/types/api/ai";
import { FileText, Loader2, Sparkles, BookOpen } from "lucide-react";
import { CitationList } from "./CitationList";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface SummaryViewProps {
  documentId: string | null;
  sessionId: string | null;
  disabled: boolean;
  activePageId?: string;
  activePageContent?: string;
  onUpdatePage?: (id: string, updates: { content: string }) => void;
}

// Used for inserting into Tiptap (page editor)
// NOTE: Tiptap strips unknown HTML/CSS, so we store math as code blocks
const markdownToHtml = (markdown: string): string => {
  let html = markdown;

  // Block math: \[...\] and $$...$$ → <pre> code block (Tiptap-safe)
  html = html.replace(/\$\$([\s\S]+?)\$\$/g, (_, latex) =>
    `<pre><code>${latex.trim()}</code></pre>`
  );
  html = html.replace(/\\\[([\s\S]+?)\\\]/g, (_, latex) =>
    `<pre><code>${latex.trim()}</code></pre>`
  );

  // Inline math: \(...\) and $...$ → inline code (Tiptap-safe)
  html = html.replace(/\\\(([\s\S]+?)\\\)/g, (_, latex) =>
    `<code>${latex.trim()}</code>`
  );
  html = html.replace(/\$([^\$\n]+?)\$/g, (_, latex) =>
    `<code>${latex.trim()}</code>`
  );

  // Headers (order matters: #### before ### before ##)
  html = html.replace(/^#### (.*?)$/gm, '<h4>$1</h4>');
  html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');

  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Lists
  const lines = html.split('\n');
  let inList = false;
  const resultLines: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) { resultLines.push('<ul>'); inList = true; }
      resultLines.push(`<li>${trimmed.substring(2)}</li>`);
    } else {
      if (inList) { resultLines.push('</ul>'); inList = false; }
      if (trimmed) {
        const isHtmlTag = trimmed.startsWith('<h') || trimmed.startsWith('<ul') ||
          trimmed.startsWith('<li') || trimmed.startsWith('<pre') || trimmed.startsWith('<blockquote');
        if (isHtmlTag) {
          resultLines.push(trimmed);
        } else {
          resultLines.push(`<p>${trimmed}</p>`);
        }
      } else {
        resultLines.push('<p></p>');
      }
    }
  }
  if (inList) resultLines.push('</ul>');
  return resultLines.join('\n');
};

// Preprocess LaTeX delimiters → formats that remark-math understands
// \[...\]  →  $$\n...\n$$  (block math on its own lines)
// \(...\)  →  $...$         (inline math)
const preprocessForMath = (content: string): string => {
  let out = content;
  out = out.replace(/\\\[([\s\S]+?)\\\]/g, (_, latex) => `\n$$\n${latex.trim()}\n$$\n`);
  out = out.replace(/\\\(([\s\S]+?)\\\)/g, (_, latex) => `$${latex.trim()}$`);
  return out;
};

const markdownComponents = {
  p: ({ node, ...props }: any) => (
    <p className="text-sm text-zinc-300 leading-relaxed font-medium mb-2.5" {...props} />
  ),
  ul: ({ node, ...props }: any) => (
    <ul className="ml-4 list-disc text-sm text-zinc-300 leading-relaxed font-medium mb-1.5" {...props} />
  ),
  li: ({ node, ...props }: any) => <li className="mb-1" {...props} />,
  strong: ({ node, ...props }: any) => <strong className="font-bold text-zinc-100" {...props} />,
  h4: ({ node, ...props }: any) => <h4 className="text-sm font-bold text-zinc-300 mt-3 mb-1" {...props} />,
  h3: ({ node, ...props }: any) => <h3 className="text-md font-bold text-zinc-200 mt-4 mb-2" {...props} />,
  h2: ({ node, ...props }: any) => <h2 className="text-lg font-bold text-zinc-100 mt-5 mb-3" {...props} />,
  h1: ({ node, ...props }: any) => <h1 className="text-xl font-bold text-zinc-100 mt-6 mb-4" {...props} />,
};

const renderContent = (content: string): React.ReactNode => (
  <ReactMarkdown
    remarkPlugins={[remarkMath]}
    rehypePlugins={[[rehypeKatex, { throwOnError: false, errorColor: '#cc0000' }]]}
    components={markdownComponents}
  >
    {preprocessForMath(content)}
  </ReactMarkdown>
);

export const SummaryView: React.FC<SummaryViewProps> = ({
  documentId,
  sessionId,
  disabled,
  activePageId,
  activePageContent,
  onUpdatePage,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<AIResponse | null>(null);
  const [style, setStyle] = useState<"bullet_points" | "paragraph">("bullet_points");
  const [size, setSize] = useState<"concise" | "medium" | "detailed">("medium");
  const [language, setLanguage] = useState<"ar" | "en">("ar");

  const handleGenerateSummary = async () => {
    if (!documentId || !sessionId || isLoading || disabled) return;

    setIsLoading(true);
    setResponse(null);
    try {
      const summaryRes = await aiService.generateSummary(documentId, {
        session_id: sessionId,
        language,
        summary_style: style,
        summary_size: size,
      });
      setResponse(summaryRes);
    } catch (err: any) {
      toast.error(err.message || "Failed to generate summary.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateSummaryInPage = async () => {
    if (!documentId || !sessionId || isLoading || disabled) return;
    if (!activePageId || !onUpdatePage) {
      toast.error("Please select a page first.");
      return;
    }

    setIsLoading(true);
    setResponse(null);
    try {
      const summaryRes = await aiService.generateSummary(documentId, {
        session_id: sessionId,
        language,
        summary_style: style,
        summary_size: size,
      });
      setResponse(summaryRes);
      
      if (summaryRes.message) {
        const summaryHtml = markdownToHtml(summaryRes.message);
        const existingContent = activePageContent || "";
        const separator = existingContent ? '<p></p><hr><p></p>' : '';
        const newContent = existingContent + separator + summaryHtml;
        onUpdatePage(activePageId, { content: newContent });
        toast.success("Summary successfully inserted into page!");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to generate summary.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4 custom-scrollbar">
      {/* Configuration Header Card */}
      <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 backdrop-blur-md flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col">
            <span className="text-sm font-bold text-zinc-200">Document Summarizer</span>
            <span className="text-xs text-zinc-500 font-medium">Condense the context into study formats</span>
          </div>
          <BookOpen className="h-5 w-5 text-primary/80" />
        </div>

        <div className="grid grid-cols-3 gap-2 mt-1">
          {/* Format Selection */}
          <div className="flex flex-col gap-1">
            <label htmlFor="summary-format" className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Format</label>
            <select
              id="summary-format"
              value={style}
              onChange={(e) => setStyle(e.target.value as any)}
              className="h-9 px-1 rounded-lg border border-zinc-800 bg-zinc-950 text-[10px] text-zinc-300 outline-none cursor-pointer"
            >
              <option value="bullet_points">Bullet Points</option>
              <option value="paragraph">Paragraph</option>
            </select>
          </div>

          {/* Size Selection */}
          <div className="flex flex-col gap-1">
            <label htmlFor="summary-size" className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Size</label>
            <select
              id="summary-size"
              value={size}
              onChange={(e) => setSize(e.target.value as any)}
              className="h-9 px-1 rounded-lg border border-zinc-800 bg-zinc-950 text-[10px] text-zinc-300 outline-none cursor-pointer"
            >
              <option value="concise">Small</option>
              <option value="medium">Medium</option>
              <option value="detailed">Large</option>
            </select>
          </div>

          {/* Language Selection */}
          <div className="flex flex-col gap-1">
            <label htmlFor="summary-language" className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Language</label>
            <select
              id="summary-language"
              value={language}
              onChange={(e) => setLanguage(e.target.value as any)}
              className="h-9 px-1 rounded-lg border border-zinc-800 bg-zinc-950 text-[10px] text-zinc-300 outline-none cursor-pointer"
            >
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-2 mt-2">
          <button
            onClick={handleGenerateSummary}
            disabled={disabled || isLoading}
            className="flex items-center justify-center gap-2 h-9 w-full rounded-full bg-primary text-white text-xs font-semibold hover:bg-primary-dark transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:scale-100 disabled:cursor-not-allowed cursor-pointer"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Generate Summary
          </button>

          <button
            onClick={handleGenerateSummaryInPage}
            disabled={disabled || isLoading || !activePageId}
            className="flex items-center justify-center gap-2 h-9 w-full rounded-full bg-purple-950/60 border border-purple-500/30 text-white text-xs font-semibold hover:bg-purple-900/80 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:scale-100 disabled:cursor-not-allowed cursor-pointer"
            title={!activePageId ? "Select a page to write summary" : "Generate and write summary directly to page content"}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileText className="h-4 w-4" />
            )}
            Generate Summary in Page
          </button>
        </div>
      </div>

      {/* Summary Output */}
      {isLoading && (
        <div className="flex-1 flex flex-col items-center justify-center gap-2.5 text-zinc-500 min-h-[160px]">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <span className="text-xs font-semibold tracking-wide">
            Analyzing document structure...
          </span>
        </div>
      )}

      {response && (
        <div className="p-5 rounded-2xl border border-zinc-800 bg-zinc-900/40 backdrop-blur-md shadow-md animate-fade-in">
          <div className="flex flex-col">
            {response.error ? (
              <p className="text-sm text-red-400 font-semibold">{response.error}</p>
            ) : (
              <>
                {renderContent(response.message)}
                {response.citations && response.citations.length > 0 && (
                  <CitationList citations={response.citations} />
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
