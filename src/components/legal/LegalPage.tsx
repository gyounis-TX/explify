import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./LegalPage.css";

interface LegalPageProps {
  title: string;
  markdownPath: string;
}

/** Minimal markdown→HTML for legal docs (headers, bold, links, lists, paragraphs). */
function renderMarkdown(md: string): string {
  const lines = md.split("\n");
  const html: string[] = [];
  let inList = false;

  for (const raw of lines) {
    const line = raw.trimEnd();

    // Headings
    if (line.startsWith("### ")) {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push(`<h4>${inline(line.slice(4))}</h4>`);
      continue;
    }
    if (line.startsWith("## ")) {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push(`<h3>${inline(line.slice(3))}</h3>`);
      continue;
    }
    if (line.startsWith("# ")) {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push(`<h2>${inline(line.slice(2))}</h2>`);
      continue;
    }

    // Unordered list
    if (/^[-*] /.test(line)) {
      if (!inList) { html.push("<ul>"); inList = true; }
      html.push(`<li>${inline(line.slice(2))}</li>`);
      continue;
    }

    // Close open list
    if (inList) { html.push("</ul>"); inList = false; }

    // Blank line
    if (!line.trim()) {
      continue;
    }

    // Regular paragraph
    html.push(`<p>${inline(line)}</p>`);
  }

  if (inList) html.push("</ul>");
  return html.join("\n");
}

/** Inline markdown: bold, italic, links, code. */
function inline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

export function LegalPage({ title, markdownPath }: LegalPageProps) {
  const navigate = useNavigate();
  const [html, setHtml] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(markdownPath)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load ${markdownPath}`);
        return res.text();
      })
      .then((md) => {
        setHtml(renderMarkdown(md));
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [markdownPath]);

  return (
    <div className="legal-page">
      <div className="legal-page-inner">
        <button className="legal-back-btn" onClick={() => navigate(-1)}>
          &larr; Back
        </button>
        <h1 className="legal-page-title">{title}</h1>
        {loading && <p className="legal-loading">Loading...</p>}
        {error && <p className="legal-error">{error}</p>}
        {html && (
          <div
            className="legal-content"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}
      </div>
    </div>
  );
}
