import type { ReactNode } from "react";
import "./GlossaryTooltip.css";

interface GlossaryTooltipProps {
  text: string;
  glossary: Record<string, string>;
}

export function GlossaryTooltip({ text, glossary }: GlossaryTooltipProps) {
  if (!text || Object.keys(glossary).length === 0) {
    return <>{text}</>;
  }

  // Sort terms longest-first to avoid partial matches
  const terms = Object.keys(glossary).sort((a, b) => b.length - a.length);

  // Build regex matching any term, case-insensitive
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");

  const parts = text.split(pattern);
  const seen = new Set<string>();
  const nodes: ReactNode[] = [];

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;

    // Check if this part matches a glossary term
    const matchKey = terms.find(
      (t) => t.toLowerCase() === part.toLowerCase(),
    );

    if (matchKey && !seen.has(matchKey.toLowerCase())) {
      seen.add(matchKey.toLowerCase());
      nodes.push(
        <span
          key={i}
          className="glossary-term"
          tabIndex={0}
          aria-label={`${part}: ${glossary[matchKey]}`}
        >
          {part}
          <span className="glossary-tooltip" role="tooltip">
            {glossary[matchKey]}
          </span>
        </span>,
      );
    } else {
      nodes.push(<span key={i}>{part}</span>);
    }
  }

  return <>{nodes}</>;
}
