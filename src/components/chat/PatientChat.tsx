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

export function PatientChat() {
  const { token } = useParams<{ token: string }>();
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(true);
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
    if (!token || !input.trim() || sending) return;

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
  }, [token, input, sending]);

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

  // --- Main Chat UI ---

  return (
    <div className="patient-chat-page">
      <div className="patient-chat-container">
        <div className="chat-header">
          <h1 className="chat-title">Explify</h1>
          <span className="chat-test-type">{session.test_type_display}</span>
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
                {session.explanation_summary
                  .split("\n\n")
                  .filter(Boolean)
                  .map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
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
                  {msg.content.split("\n\n").filter(Boolean).map((p, j) => (
                    <p key={j}>{p}</p>
                  ))}
                </div>
              </div>
            ))}
            {sending && (
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
            disabled={sending}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || sending}
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
