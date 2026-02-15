import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import "./Toast.css";

type ToastType = "success" | "error" | "info" | "undo";

interface ToastMessage {
  id: number;
  type: ToastType;
  message: string;
  onUndo?: () => void;
  duration: number;
  createdAt: number;
}

interface ToastContextValue {
  showToast: (type: "success" | "error" | "info", message: string) => void;
  showUndoToast: (message: string, onUndo: () => void, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: number) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((type: "success" | "error" | "info", message: string) => {
    const id = nextId++;
    const duration = type === "error" ? 8000 : 4000;
    setToasts((prev) => [...prev, { id, type, message, duration, createdAt: Date.now() }]);
    const timer = setTimeout(() => {
      timersRef.current.delete(id);
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
    timersRef.current.set(id, timer);
  }, []);

  const showUndoToast = useCallback((message: string, onUndo: () => void, duration = 5000) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, type: "undo" as const, message, onUndo, duration, createdAt: Date.now() }]);
    const timer = setTimeout(() => {
      timersRef.current.delete(id);
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
    timersRef.current.set(id, timer);
  }, []);

  // Global Cmd+Z / Ctrl+Z handler — triggers the most recent undo toast
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "z" && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        // Don't intercept if user is typing in an input/textarea
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement)?.isContentEditable) {
          return;
        }
        const undoToast = [...toasts].reverse().find((t) => t.type === "undo" && t.onUndo);
        if (undoToast) {
          e.preventDefault();
          undoToast.onUndo!();
          removeToast(undoToast.id);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toasts, removeToast]);

  return (
    <ToastContext.Provider value={{ showToast, showUndoToast }}>
      {children}
      <div className="toast-container" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <ToastItem
            key={toast.id}
            toast={toast}
            onDismiss={() => removeToast(toast.id)}
            onUndo={() => {
              if (toast.onUndo) toast.onUndo();
              removeToast(toast.id);
            }}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({
  toast,
  onDismiss,
  onUndo,
}: {
  toast: ToastMessage;
  onDismiss: () => void;
  onUndo: () => void;
}) {
  const [remainingMs, setRemainingMs] = useState(toast.duration);

  useEffect(() => {
    if (toast.type !== "undo") return;
    const interval = setInterval(() => {
      const elapsed = Date.now() - toast.createdAt;
      const remaining = Math.max(0, toast.duration - elapsed);
      setRemainingMs(remaining);
      if (remaining <= 0) clearInterval(interval);
    }, 100);
    return () => clearInterval(interval);
  }, [toast]);

  if (toast.type === "undo") {
    const progress = remainingMs / toast.duration;
    return (
      <div className="toast toast--undo" role="alert">
        <span className="toast-undo-message">{toast.message}</span>
        <button className="toast-undo-btn" onClick={onUndo}>
          Undo <kbd className="toast-undo-kbd">{navigator.platform?.includes("Mac") ? "\u2318" : "Ctrl+"}Z</kbd>
        </button>
        <div className="toast-undo-progress">
          <div
            className="toast-undo-progress-bar"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`toast toast--${toast.type}`}
      role={toast.type === "error" ? "alert" : "status"}
      onClick={onDismiss}
    >
      {toast.message}
    </div>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
