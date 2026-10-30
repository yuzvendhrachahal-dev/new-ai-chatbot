import React from 'react';

export interface ParsedProductCard {
  type: 'product';
  name: string;
  price?: string;
  description?: string;
  url: string;
}

export interface ParsedFeatureCard {
  type: 'feature';
  title: string;
  description: string;
  button_text: string;
  url: string;
}

export interface ParsedTextBlock {
  type: 'text';
  text: string;
}

export type ParsedSegment = ParsedTextBlock | ParsedProductCard | ParsedFeatureCard;

export const isSafeUrl = (url: string | undefined | null): boolean => {
  if (!url || typeof url !== 'string') return false;
  const clean = url.trim();
  if (!/^https?:\/\//i.test(clean)) return false;
  if (/^(javascript|data|vbscript|file):/i.test(clean)) return false;
  try {
    const parsed = new URL(clean);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
};

export const openSafeUrl = (url: string | undefined | null) => {
  if (url && isSafeUrl(url)) {
    window.open(url.trim(), '_blank', 'noopener,noreferrer');
  }
};

export const parseMessageSegments = (rawText: string): ParsedSegment[] => {
  if (!rawText) return [];

  const segments: ParsedSegment[] = [];
  const cardRegex = /:::(product_card|feature_card)\r?\n([\s\S]*?):::/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = cardRegex.exec(rawText)) !== null) {
    const textBefore = rawText.slice(lastIndex, match.index).trim();
    if (textBefore) {
      segments.push({ type: 'text', text: textBefore });
    }

    const cardType = match[1];
    const cardContent = match[2];
    const lines = cardContent.split(/\r?\n/);
    const data: Record<string, string> = {};

    for (const line of lines) {
      const colonIdx = line.indexOf(':');
      if (colonIdx !== -1) {
        const key = line.slice(0, colonIdx).trim().toLowerCase();
        const val = line.slice(colonIdx + 1).trim();
        data[key] = val;
      }
    }

    if (cardType === 'product_card') {
      if (data.name && data.url) {
        segments.push({
          type: 'product',
          name: data.name,
          price: data.price || undefined,
          description: data.description || undefined,
          url: data.url
        });
      }
    } else if (cardType === 'feature_card') {
      if (data.title && data.url) {
        segments.push({
          type: 'feature',
          title: data.title,
          description: data.description || '',
          button_text: data.button || data.button_text || 'Open Service',
          url: data.url
        });
      }
    }

    lastIndex = match.index + match[0].length;
  }

  const textAfter = rawText.slice(lastIndex).trim();
  if (textAfter) {
    segments.push({ type: 'text', text: textAfter });
  }

  // Fallback for legacy markdown product items if present
  if (segments.length === 0 || (segments.length === 1 && segments[0].type === 'text')) {
    const textToCheck = segments.length === 1 ? (segments[0] as ParsedTextBlock).text : rawText;
    const legacySegments = tryParseLegacyProducts(textToCheck);
    if (legacySegments && legacySegments.length > 0) {
      return legacySegments;
    }
  }

  return segments.length > 0 ? segments : [{ type: 'text', text: rawText }];
};

const tryParseLegacyProducts = (text: string): ParsedSegment[] | null => {
  if (!text || (!text.includes('AstroVed.com](') && !text.includes('**Product Name:**'))) {
    return null;
  }

  const items = text.split(/\n\s*---\s*\n/);
  if (items.length <= 1 && !text.includes('**Product Name:**')) {
    return null;
  }

  const segments: ParsedSegment[] = [];
  for (const item of items) {
    const trimmed = item.trim();
    if (!trimmed) continue;

    const urlMatch = trimmed.match(/https:\/\/www\.astroved\.com\/[^\s)]+/);
    const nameMatch = trimmed.match(/\*\*Product Name:\*\*\s*(.+)/i) || trimmed.match(/###\s*\[([^\]]+)\]/);
    const priceMatch = trimmed.match(/\*\*Price:\*\*\s*([^\n]+)/i);

    if (urlMatch && nameMatch) {
      const descLines = trimmed.split('\n').filter(l => {
        const cleanL = l.trim();
        return !cleanL.startsWith('###') &&
               !cleanL.startsWith('**Product Name:') &&
               !cleanL.startsWith('**Price:') &&
               !cleanL.startsWith('- [View') &&
               !cleanL.startsWith('*(Remedial') &&
               !cleanL.startsWith('Namaste! Here are relevant');
      });
      const description = descLines.join(' ').trim();

      segments.push({
        type: 'product',
        name: nameMatch[1].trim(),
        price: priceMatch ? priceMatch[1].trim() : undefined,
        description: description || undefined,
        url: urlMatch[0].trim()
      });
    } else {
      const cleanIntro = trimmed
        .replace(/###\s*\[[^\]]+\]\([^\)]+\)/g, '')
        .replace(/\*\*Product Name:\*\*[^\n]+/g, '')
        .replace(/\*\*Price:\*\*[^\n]+/g, '')
        .replace(/-?\s*\[View Offerings[^\]]*\]\([^\)]+\)/g, '')
        .replace(/\*\(Remedial reference item[^\)]*\)\*/g, '')
        .trim();
      if (cleanIntro) {
        segments.push({ type: 'text', text: cleanIntro });
      }
    }
  }

  return segments.length > 0 ? segments : null;
};

export const MessageRenderer: React.FC<{ text: string }> = ({ text }) => {
  const segments = parseMessageSegments(text);

  return (
    <div className="message-content-wrapper">
      {segments.map((seg, idx) => {
        if (seg.type === 'text') {
          const formatted = seg.text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br/>');
          return (
            <div
              key={idx}
              className="message-text-segment"
              dangerouslySetInnerHTML={{ __html: formatted }}
            />
          );
        }

        if (seg.type === 'product') {
          return (
            <div
              key={idx}
              className="astroved-product-card"
              onClick={() => openSafeUrl(seg.url)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  openSafeUrl(seg.url);
                }
              }}
            >
              <div className="product-card-body">
                <div className="product-card-name">{seg.name}</div>
                {seg.price && (
                  <div className="product-card-price">{seg.price}</div>
                )}
                {seg.description && (
                  <div className="product-card-desc">{seg.description}</div>
                )}
              </div>
              <button
                type="button"
                className="product-card-view-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  openSafeUrl(seg.url);
                }}
              >
                View Product ↗
              </button>
            </div>
          );
        }

        if (seg.type === 'feature') {
          return (
            <div
              key={idx}
              className="astroved-feature-card"
              onClick={() => openSafeUrl(seg.url)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  openSafeUrl(seg.url);
                }
              }}
            >
              <div className="feature-service-name">{seg.title}</div>
              <div className="feature-card-desc">{seg.description}</div>
              <button
                type="button"
                className="feature-card-action-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  openSafeUrl(seg.url);
                }}
              >
                {seg.button_text} ↗
              </button>
            </div>
          );
        }

        return null;
      })}
    </div>
  );
};
