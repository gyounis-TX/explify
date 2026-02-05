import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { sidecarApi } from "../../services/sidecarApi";
import { logUsage } from "../../services/usageTracker";
import { useToast } from "../shared/Toast";
import type { ExtractionResult, ExplainResponse } from "../../types/sidecar";
import "./ProcessingScreen.css";

type ProcessingStep = "detecting" | "parsing" | "explaining" | "done" | "error";

interface StepInfo {
  id: ProcessingStep;
  label: string;
  description: string;
}

const STEPS: StepInfo[] = [
  {
    id: "detecting",
    label: "Detecting Report Type",
    description: "Identifying the type of medical test...",
  },
  {
    id: "parsing",
    label: "Parsing Report",
    description: "Extracting measurements and findings...",
  },
  {
    id: "explaining",
    label: "Generating Explanation",
    description: "Creating a plain-language explanation...",
  },
];

interface CategorizedError {
  category: string;
  title: string;
  message: string;
  suggestion: string;
}

function categorizeError(errorMessage: string): CategorizedError {
  const lower = errorMessage.toLowerCase();

  if (lower.includes("api key") || lower.includes("no api key") || lower.includes("authentication")) {
    return {
      category: "auth",
      title: "API Key Required",
      message: errorMessage,
      suggestion: "Please add your API key in Settings.",
    };
  }

  if (lower.includes("rate limit") || lower.includes("quota") || lower.includes("429")) {
    return {
      category: "quota",
      title: "Rate Limit Reached",
      message: errorMessage,
      suggestion: "Please wait a moment and try again.",
    };
  }

  if (lower.includes("timeout") || lower.includes("timed out")) {
    return {
      category: "timeout",
      title: "Request Timed Out",
      message: errorMessage,
      suggestion: "The AI service is slow. Please try again.",
    };
  }

  if (lower.includes("network") || lower.includes("fetch") || lower.includes("connection")) {
    return {
      category: "network",
      title: "Network Error",
      message: errorMessage,
      suggestion: "Check your internet connection and try again.",
    };
  }

  if (lower.includes("parse") || lower.includes("validation") || lower.includes("invalid")) {
    return {
      category: "parse",
      title: "Processing Error",
      message: errorMessage,
      suggestion: "The report format may not be supported. Try a different file.",
    };
  }

  return {
    category: "unknown",
    title: "Processing Failed",
    message: errorMessage,
    suggestion: "Please try again or import a different report.",
  };
}

export function ProcessingScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const locationState = location.state as {
    extractionResult?: ExtractionResult;
    templateId?: number;
    sharedTemplateSyncId?: string;
    clinicalContext?: string;
    testType?: string;
  } | null;
  const extractionResult = locationState?.extractionResult;
  const templateId = locationState?.templateId;
  const sharedTemplateSyncId = locationState?.sharedTemplateSyncId;
  const clinicalContext = locationState?.clinicalContext;
  const testType = locationState?.testType;

  const { showToast } = useToast();
  const [currentStep, setCurrentStep] =
    useState<ProcessingStep>("detecting");
  const [error, setError] = useState<CategorizedError | null>(null);
  const [deepAnalysis, setDeepAnalysis] = useState(false);

  const runPipeline = useCallback(async () => {
    if (!extractionResult) {
      setError(categorizeError("No extraction result found. Please import a report first."));
      setCurrentStep("error");
      return;
    }

    try {
      // Single step: the explain endpoint handles detect + parse + LLM internally
      setCurrentStep("explaining");
      const response: ExplainResponse = await sidecarApi.explainReport({
        extraction_result: extractionResult,
        test_type: testType,
        template_id: templateId,
        shared_template_sync_id: sharedTemplateSyncId,
        clinical_context: clinicalContext,
        short_comment: true,
        deep_analysis: deepAnalysis || undefined,
      });

      logUsage({
        model_used: response.model_used,
        input_tokens: response.input_tokens,
        output_tokens: response.output_tokens,
        request_type: "explain",
        deep_analysis: deepAnalysis,
      });

      // Save to history
      sidecarApi
        .saveHistory({
          test_type: response.parsed_report.test_type,
          test_type_display: response.parsed_report.test_type_display,
          filename: extractionResult.filename ?? null,
          summary: response.explanation.overall_summary.slice(0, 200),
          full_response: response,
        })
        .catch(() => {
          showToast("error", "Analysis complete but failed to save to history.");
        });

      // Done - navigate to results immediately
      setCurrentStep("done");
      navigate("/results", {
        state: {
          explainResponse: response,
          extractionResult,
          templateId,
          clinicalContext,
        },
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Processing failed.";
      setError(categorizeError(msg));
      setCurrentStep("error");
    }
  }, [extractionResult, templateId, sharedTemplateSyncId, clinicalContext, testType, deepAnalysis, navigate, showToast]);

  useEffect(() => {
    runPipeline();
  }, [runPipeline]);

  const currentStepIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="processing-screen">
      <header className="processing-header">
        <h2 className="processing-title">Analyzing Report</h2>
        <label className="deep-analysis-toggle">
          <input
            type="checkbox"
            checked={deepAnalysis}
            onChange={(e) => setDeepAnalysis(e.target.checked)}
          />
          <span className="deep-analysis-label">Deep Analysis</span>
          <span className="deep-analysis-subtext">For complex cases only</span>
        </label>
      </header>

      <div className="processing-steps">
        {STEPS.map((step, index) => {
          const isActive = step.id === currentStep;
          const isComplete =
            currentStepIndex > index || currentStep === "done";
          const isPending =
            currentStepIndex < index && currentStep !== "error";

          return (
            <div
              key={step.id}
              className={`processing-step ${
                isActive
                  ? "processing-step--active"
                  : isComplete
                    ? "processing-step--complete"
                    : isPending
                      ? "processing-step--pending"
                      : "processing-step--pending"
              }`}
            >
              <div className="step-indicator">
                {isComplete ? (
                  <span className="step-check">&#10003;</span>
                ) : isActive ? (
                  <div className="step-spinner" />
                ) : (
                  <span className="step-number">{index + 1}</span>
                )}
              </div>
              <div className="step-content">
                <span className="step-label">{step.label}</span>
                {isActive && (
                  <span className="step-description">
                    {step.description}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {currentStep === "error" && error && (
        <div className="processing-error">
          <p className="error-title">{error.title}</p>
          <p className="error-message">{error.message}</p>
          <p className="error-suggestion">{error.suggestion}</p>
          <div className="error-actions">
            {error.category === "auth" ? (
              <button
                className="retry-btn"
                onClick={() => navigate("/settings")}
              >
                Go to Settings
              </button>
            ) : (
              <>
                {["network", "timeout", "quota"].includes(error.category) && (
                  <button
                    className="retry-btn"
                    onClick={() => {
                      setError(null);
                      setCurrentStep("detecting");
                      runPipeline();
                    }}
                  >
                    Retry
                  </button>
                )}
                <button
                  className="retry-btn"
                  onClick={() => navigate("/")}
                >
                  Back to Import
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {currentStep === "done" && (
        <div className="processing-complete">
          <p>Redirecting to results...</p>
        </div>
      )}
    </div>
  );
}
