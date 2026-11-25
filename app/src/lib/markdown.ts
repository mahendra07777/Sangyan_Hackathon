export type InlineToken =
  | { type: "text"; content: string }
  | { type: "bold"; content: string }
  | { type: "italic"; content: string };

export type MarkdownBlock =
  | { type: "paragraph"; lines: InlineToken[][] }
  | { type: "ul"; items: InlineToken[][] }
  | { type: "ol"; items: InlineToken[][] }
  | { type: "blockquote"; lines: InlineToken[][] };

const INLINE_PATTERN =
  /(\*\*([^\s*](?:[^*]*[^\s*])?)\*\*)|(\*([^\s*](?:[^*]*[^\s*])?)\*)/g;

/**
 * Tokenizes inline bold (**text**) and italic (*text*) safely into plain data structures.
 * Never interprets or outputs raw HTML.
 */
export function parseInlineMarkdown(text: string): InlineToken[] {
  if (!text) return [];

  const tokens: InlineToken[] = [];
  let lastIndex = 0;
  INLINE_PATTERN.lastIndex = 0;

  let match: RegExpExecArray | null;
  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }

    if (match[2] !== undefined) {
      tokens.push({ type: "bold", content: match[2] });
    } else if (match[4] !== undefined) {
      tokens.push({ type: "italic", content: match[4] });
    }

    lastIndex = INLINE_PATTERN.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push({ type: "text", content: text.slice(lastIndex) });
  }

  return tokens;
}

const UL_ITEM_RE = /^\s*[-*]\s+(.+)$/;
const OL_ITEM_RE = /^\s*\d+\.\s+(.+)$/;
const BLOCKQUOTE_RE = /^\s*>\s?(.*)$/;

/**
 * Parses text into structured paragraphs, unordered/ordered lists, and blockquotes
 * while preserving line breaks and blank-line spacing.
 */
export function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  if (!markdown) return [];

  const normalized = markdown.replace(/\r\n?/g, "\n");
  const rawLines = normalized.split("\n");
  const blocks: MarkdownBlock[] = [];

  let currentParagraph: InlineToken[][] = [];
  let currentList: { type: "ul" | "ol"; items: InlineToken[][] } | null = null;
  let currentQuote: InlineToken[][] = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      blocks.push({ type: "paragraph", lines: currentParagraph });
      currentParagraph = [];
    }
  };

  const flushList = () => {
    if (currentList) {
      blocks.push({ type: currentList.type, items: currentList.items });
      currentList = null;
    }
  };

  const flushQuote = () => {
    if (currentQuote.length > 0) {
      blocks.push({ type: "blockquote", lines: currentQuote });
      currentQuote = [];
    }
  };

  for (const line of rawLines) {
    if (line.trim() === "") {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }

    const ulMatch = UL_ITEM_RE.exec(line);
    if (ulMatch) {
      flushParagraph();
      flushQuote();
      if (!currentList || currentList.type !== "ul") {
        flushList();
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push(parseInlineMarkdown(ulMatch[1]));
      continue;
    }

    const olMatch = OL_ITEM_RE.exec(line);
    if (olMatch) {
      flushParagraph();
      flushQuote();
      if (!currentList || currentList.type !== "ol") {
        flushList();
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push(parseInlineMarkdown(olMatch[1]));
      continue;
    }

    const quoteMatch = BLOCKQUOTE_RE.exec(line);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      currentQuote.push(parseInlineMarkdown(quoteMatch[1]));
      continue;
    }

    flushList();
    flushQuote();
    currentParagraph.push(parseInlineMarkdown(line));
  }

  flushParagraph();
  flushList();
  flushQuote();

  return blocks;
}
