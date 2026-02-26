import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import type { ChatSession, ChatMessage } from "../../types/sidecar";
import "./PatientChat.css";

const API_BASE = import.meta.env.VITE_API_URL || "";

async function loadChatSession(token: string): Promise<ChatSession> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}`);
  if (res.status === 410) {
    throw new Error("expired");
  }
  if (!res.ok) {
    throw new Error("not_found");
  }
  return res.json();
}

async function sendChatMessage(
  token: string,
  content: string,
): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (res.status === 410) {
    throw new Error("expired");
  }
  if (res.status === 429) {
    throw new Error("limit_reached");
  }
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: "send_failed" }));
    throw new Error(errBody.detail || "send_failed");
  }
  return res.json();
}

async function requestSimplify(token: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}/simplify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 410) throw new Error("expired");
  if (res.status === 429) throw new Error("limit_reached");
  if (!res.ok) throw new Error("simplify_failed");
  return res.json();
}

async function requestDetail(token: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}/detail`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 410) throw new Error("expired");
  if (res.status === 429) throw new Error("limit_reached");
  if (!res.ok) throw new Error("detail_failed");
  return res.json();
}

async function requestKeyFindings(token: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}/key-findings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 410) throw new Error("expired");
  if (res.status === 429) throw new Error("limit_reached");
  if (!res.ok) throw new Error("key_findings_failed");
  return res.json();
}

async function requestMeasurements(token: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}/measurements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 410) throw new Error("expired");
  if (res.status === 429) throw new Error("limit_reached");
  if (!res.ok) throw new Error("measurements_failed");
  return res.json();
}

async function requestQuestions(token: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat/sessions/${token}/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 410) throw new Error("expired");
  if (res.status === 429) throw new Error("limit_reached");
  if (!res.ok) throw new Error("questions_failed");
  return res.json();
}

/** Clean markdown: strip headings and rules but keep bold for rendering. */
function cleanMarkdown(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, "")      // ### headings → plain text
    .replace(/\*{3}(.+?)\*{3}/g, "**$1**") // ***bold-italic*** → bold
    .replace(/^---+$/gm, "")           // --- horizontal rules
    .replace(/\n{3,}/g, "\n\n");       // collapse excess blank lines
}

/** Render a line of text, converting **bold** to <strong> elements. */
function renderFormattedLine(text: string, key: number): JSX.Element {
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  const boldRe = /\*\*(.+?)\*\*/g;
  let match: RegExpExecArray | null;
  while ((match = boldRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<strong key={`b${match.index}`}>{match[1]}</strong>);
    lastIndex = boldRe.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return <p key={key}>{parts}</p>;
}

/** Split text on any newline boundary for paragraph rendering. */
function splitParagraphs(text: string): string[] {
  return text.split(/\n{1,}/).filter(Boolean);
}

export function PatientChat() {
  const { token } = useParams<{ token: string }>();
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [actionLoading, setActionLoading] = useState<"simplify" | "detail" | "key-findings" | "measurements" | "questions" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(true);
  const [widthMode, setWidthMode] = useState<"default" | "wide" | "narrow">("default");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (!token) {
      setError("not_found");
      return;
    }
    loadChatSession(token)
      .then((s) => {
        setSession(s);
        setMessages(s.messages);
      })
      .catch((e) => {
        setError(e.message === "expired" ? "expired" : "not_found");
      });
  }, [token]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = useCallback(async () => {
    if (!token || !input.trim() || sending || actionLoading) return;

    const content = input.trim();
    setInput("");
    setSending(true);

    // Optimistically add patient message
    const patientMsg: ChatMessage = {
      role: "patient",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, patientMsg]);

    try {
      const assistantMsg = await sendChatMessage(token, content);
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      const err = e as Error;
      if (err.message === "expired") {
        setError("expired");
      } else if (err.message === "limit_reached") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "This chat session has reached its message limit. Please contact your care team for further questions.",
            created_at: new Date().toISOString(),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "I'm having trouble responding right now. Please try again in a moment.",
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }, [token, input, sending, actionLoading]);

  const handleAction = useCallback(async (action: "simplify" | "detail" | "key-findings" | "measurements" | "questions") => {
    if (!token || sending || actionLoading) return;
    setActionLoading(action);

    // Show synthetic patient message matching what the backend stores
    const patientTextMap: Record<string, string> = {
      simplify: "Can you simplify the explanation for me?",
      detail: "Can you give me a more detailed explanation of all my results?",
      "key-findings": "Can you explain my key findings?",
      measurements: "Can you walk me through my measurements?",
      questions: "What questions should I ask my doctor?",
    };
    const patientMsg: ChatMessage = {
      role: "patient",
      content: patientTextMap[action],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, patientMsg]);

    try {
      const fnMap: Record<string, (t: string) => Promise<ChatMessage>> = {
        simplify: requestSimplify,
        detail: requestDetail,
        "key-findings": requestKeyFindings,
        measurements: requestMeasurements,
        questions: requestQuestions,
      };
      const msg = await fnMap[action](token);
      setMessages((prev) => [...prev, msg]);
    } catch (e) {
      const err = e as Error;
      if (err.message === "expired") {
        setError("expired");
      } else if (err.message === "limit_reached") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "This chat session has reached its message limit. Please contact your care team for further questions.",
            created_at: new Date().toISOString(),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              `I'm having trouble generating that right now. Please try again in a moment.`,
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } finally {
      setActionLoading(null);
    }
  }, [token, sending, actionLoading]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // --- Error States ---

  if (error === "expired") {
    return (
      <div className="patient-chat-page">
        <div className="patient-chat-container">
          <div className="chat-header">
            <h1 className="chat-title">Explify</h1>
          </div>
          <div className="chat-error">
            <div className="chat-error-icon">&#128337;</div>
            <h2>This chat link has expired</h2>
            <p>
              For your privacy, chat links expire after a set period.
              Please contact your care team if you need a new link or
              have further questions about your results.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error === "not_found") {
    return (
      <div className="patient-chat-page">
        <div className="patient-chat-container">
          <div className="chat-header">
            <h1 className="chat-title">Explify</h1>
          </div>
          <div className="chat-error">
            <div className="chat-error-icon">&#128533;</div>
            <h2>Chat not found</h2>
            <p>
              This chat link doesn't seem to be valid. Please check the
              link or contact your care team for assistance.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="patient-chat-page">
        <div className="patient-chat-container">
          <div className="chat-loading">Loading your chat...</div>
        </div>
      </div>
    );
  }

  const isLoading = sending || !!actionLoading;

  // --- Main Chat UI ---

  return (
    <div className="patient-chat-page">
      <div className={`patient-chat-container${widthMode === "wide" ? " chat-wide" : widthMode === "narrow" ? " chat-narrow" : ""}`}>
        <div className="chat-header">
          <h1 className="chat-title">Explify</h1>
          <span className="chat-test-type">{session.test_type_display}</span>
          <span className="chat-header-spacer" />
          <button
            className="chat-width-toggle"
            onClick={() => setWidthMode((m) => m === "default" ? "wide" : m === "wide" ? "narrow" : "default")}
            title={widthMode === "default" ? "Expand" : widthMode === "wide" ? "Compact" : "Default width"}
            aria-label="Toggle chat width"
          >
            {widthMode === "wide" ? "\u2194" : widthMode === "narrow" ? "\u2195" : "\u21D4"}
          </button>
        </div>

        <div className="chat-body">
          {/* Collapsible explanation summary */}
          <div className="chat-summary-section">
            <button
              className="chat-summary-toggle"
              onClick={() => setShowSummary(!showSummary)}
              aria-expanded={showSummary}
            >
              <span>Your Results Summary</span>
              <span className="toggle-icon">{showSummary ? "\u25B2" : "\u25BC"}</span>
            </button>
            {showSummary && (
              <div className="chat-summary-content">
                {splitParagraphs(cleanMarkdown(session.explanation_summary)).map((p, i) =>
                  renderFormattedLine(p, i)
                )}
                <div className="chat-action-buttons">
                  <button
                    className="chat-action-btn"
                    onClick={() => handleAction("simplify")}
                    disabled={isLoading}
                  >
                    {actionLoading === "simplify" ? "Simplifying..." : "Simplify"}
                  </button>
                  <button
                    className="chat-action-btn"
                    onClick={() => handleAction("detail")}
                    disabled={isLoading}
                  >
                    {actionLoading === "detail" ? "Generating..." : "More Detail"}
                  </button>
                  <button
                    className="chat-action-btn"
                    onClick={() => handleAction("key-findings")}
                    disabled={isLoading}
                  >
                    {actionLoading === "key-findings" ? "Loading..." : "Key Findings"}
                  </button>
                  <button
                    className="chat-action-btn"
                    onClick={() => handleAction("measurements")}
                    disabled={isLoading}
                  >
                    {actionLoading === "measurements" ? "Loading..." : "Measurements"}
                  </button>
                  <button
                    className="chat-action-btn"
                    onClick={() => handleAction("questions")}
                    disabled={isLoading}
                  >
                    {actionLoading === "questions" ? "Loading..." : "Questions to Ask"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-welcome">
                <p>
                  Have questions about your results? Ask below and I'll help
                  explain them in more detail.
                </p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`chat-message chat-message--${msg.role}`}
              >
                <div className="chat-message-bubble">
                  {splitParagraphs(
                    msg.role === "assistant" ? cleanMarkdown(msg.content) : msg.content
                  ).map((p, j) =>
                    msg.role === "assistant" ? renderFormattedLine(p, j) : <p key={j}>{p}</p>
                  )}
                </div>
              </div>
            ))}
            {(sending || actionLoading) && (
              <div className="chat-message chat-message--assistant">
                <div className="chat-message-bubble chat-typing">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="chat-input-area">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, 500))}
            onKeyDown={handleKeyDown}
            placeholder="Type your question..."
            rows={1}
            maxLength={500}
            disabled={isLoading}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            aria-label="Send message"
          >
            &#9654;
          </button>
          <span className="chat-char-count">{input.length}/500</span>
        </div>

        <footer className="chat-footer">
          <p>
            This chat is powered by AI and is limited to explaining the results
            in your report. It cannot provide medical advice, diagnoses, or
            treatment recommendations. For medical concerns, please contact your
            care team directly.
          </p>
        </footer>
      </div>
    </div>
  );
}
