import { useState, useEffect, useRef } from "react";
import { sidecarApi } from "../../services/sidecarApi";
import { useToast } from "../shared/Toast";
import type { ExtractionResult } from "../../types/sidecar";
import "../shared/TypeModal.css";

interface InterpretModalProps {
  extractionResult: ExtractionResult;
  testType: string;
  testTypeDisplay: string;
  onClose: () => void;
}

export default function InterpretModal({
  extractionResult,
  testType,
  testTypeDisplay,
  onClose,
}: InterpretModalProps) {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [interpretation, setInterpretation] = useState("");
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();
  const abortRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await sidecarApi.interpretReport({
          extraction_result: extractionResult,
          test_type: testType,
        });
        if (cancelled || abortRef.current) return;
        setInterpretation(resp.interpretation);
        setStatus("success");
      } catch {
        if (cancelled || abortRef.current) return;
        setStatus("error");
      }
    })();
    return () => { cancelled = true; };
  }, [extractionResult, testType]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(interpretation);
      setCopied(true);
      showToast("success", "Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showToast("error", "Failed to copy to clipboard");
    }
  };

  return (
    <div className="type-modal-backdrop" onClick={onClose}>
      <div
        className="type-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 640, maxHeight: "80vh", display: "flex", flexDirection: "column" }}
      >
        <h3 className="type-modal-title">Clinical Interpretation</h3>
        <p className="type-modal-subtitle">
          {testTypeDisplay} — Doctor-to-doctor interpretation
        </p>

        {status === "loading" && (
          <div className="quick-normal-loading">
            <span className="quick-normal-spinner" />
            <span>Generating clinical interpretation...</span>
          </div>
        )}

        {status === "error" && (
          <div className="quick-normal-error">
            <p>Failed to generate interpretation.</p>
            <button className="quick-normal-btn quick-normal-btn--secondary" onClick={onClose}>
              Close
            </button>
          </div>
        )}

        {status === "success" && (
          <>
            <div
              className="quick-normal-result"
              style={{ overflowY: "auto", maxHeight: "55vh", whiteSpace: "pre-wrap" }}
            >
              <p className="quick-normal-text">{interpretation}</p>
            </div>
            <div className="type-modal-actions">
              <button className="quick-normal-btn quick-normal-btn--secondary" onClick={onClose}>
                Close
              </button>
              <button className="quick-normal-btn quick-normal-btn--primary" onClick={handleCopy}>
                {copied ? "Copied!" : "Copy to Clipboard"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
