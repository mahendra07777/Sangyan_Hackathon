import { Fragment } from "react";
import { parseMarkdownBlocks, type InlineToken } from "../../lib/markdown";

interface SafeMarkdownProps {
  content: string;
  className?: string;
}

function renderInlineTokens(tokens: InlineToken[]) {
  return tokens.map((token, idx) => {
    if (token.type === "bold") {
      return (
        <strong key={idx} className="font-bold text-primary-900">
          {token.content}
        </strong>
      );
    }
    if (token.type === "italic") {
      return (
        <em key={idx} className="italic text-neutral-700">
          {token.content}
        </em>
      );
    }
    return <Fragment key={idx}>{token.content}</Fragment>;
  });
}

function renderLinesWithBreaks(lines: InlineToken[][]) {
  return lines.map((lineTokens, lineIdx) => (
    <Fragment key={lineIdx}>
      {lineIdx > 0 && <br />}
      {renderInlineTokens(lineTokens)}
    </Fragment>
  ));
}

/**
 * Safely renders Markdown (bold, italic, paragraphs, lists, blockquotes) into React elements.
 * Never interprets or injects raw HTML/scripts.
 */
export function SafeMarkdown({ content, className = "" }: SafeMarkdownProps) {
  const blocks = parseMarkdownBlocks(content);
  if (blocks.length === 0) return null;

  return (
    <div className={`space-y-3 ${className}`.trim()}>
      {blocks.map((block, idx) => {
        if (block.type === "ul") {
          return (
            <ul key={idx} className="list-disc pl-5 space-y-1.5">
              {block.items.map((itemTokens, itemIdx) => (
                <li key={itemIdx}>{renderInlineTokens(itemTokens)}</li>
              ))}
            </ul>
          );
        }

        if (block.type === "ol") {
          return (
            <ol key={idx} className="list-decimal pl-5 space-y-1.5">
              {block.items.map((itemTokens, itemIdx) => (
                <li key={itemIdx}>{renderInlineTokens(itemTokens)}</li>
              ))}
            </ol>
          );
        }

        if (block.type === "blockquote") {
          return (
            <blockquote
              key={idx}
              className="pl-3.5 py-1 border-l-2 border-accent-500/50 bg-neutral-50/80 rounded-r text-neutral-700"
            >
              {renderLinesWithBreaks(block.lines)}
            </blockquote>
          );
        }

        return (
          <p key={idx} className="leading-relaxed">
            {renderLinesWithBreaks(block.lines)}
          </p>
        );
      })}
    </div>
  );
}
