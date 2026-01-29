import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { sidecarApi } from "../../services/sidecarApi";
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

export function ProcessingScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const extractionResult = (
    location.state as { extractionResult?: ExtractionResult }
  )?.extractionResult;

  const [currentStep, setCurrentStep] =
    useState<ProcessingStep>("detecting");
  const [error, setError] = useState<string | null>(null);

  const runPipeline = useCallback(async () => {
    if (!extractionResult) {
      setError("No extraction result found. Please import a report first.");
      setCurrentStep("error");
      return;
    }

    try {
      // Step 1: Detect test type
      setCurrentStep("detecting");
      const detectResult =
        await sidecarApi.detectTestType(extractionResult);
      if (!detectResult.test_type) {
        throw new Error("Could not determine the report type.");
      }
      const testType = detectResult.test_type;

      // Step 2: Parse report (for progress display)
      setCurrentStep("parsing");
      await sidecarApi.parseReport(extractionResult, testType);

      // Step 3: Call LLM explain
      setCurrentStep("explaining");
      const response: ExplainResponse = await sidecarApi.explainReport({
        extraction_result: extractionResult,
        test_type: testType,
      });

      // Done - navigate to results
      setCurrentStep("done");
      setTimeout(() => {
        navigate("/results", {
          state: { explainResponse: response },
        });
      }, 600);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Processing failed.",
      );
      setCurrentStep("error");
    }
  }, [extractionResult, navigate]);

  useEffect(() => {
    runPipeline();
  }, [runPipeline]);

  const currentStepIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="processing-screen">
      <header className="processing-header">
        <h2 className="processing-title">Analyzing Report</h2>
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
          <p className="error-message">{error}</p>
          <button
            className="retry-btn"
            onClick={() => navigate("/")}
          >
            Back to Import
          </button>
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
