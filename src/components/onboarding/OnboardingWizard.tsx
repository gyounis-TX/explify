import { useState } from "react";
import "./OnboardingWizard.css";

interface OnboardingWizardProps {
  onComplete: () => void;
}

const steps = [
  {
    title: "Welcome to Explify",
    body: "Explify helps physicians generate clear, patient-friendly explanations of medical reports. Everything runs locally on your device for maximum privacy.",
  },
  {
    title: "Import Reports",
    body: "Upload PDF, image, or text files of medical reports. Explify extracts the content and detects the test type automatically.",
  },
  {
    title: "AI-Powered Explanations",
    body: "Get plain-language explanations of medical reports powered by Claude or OpenAI. Patient-identifying information is scrubbed before being sent to the AI provider. You can add clinical context when importing a report to refine the explanation for each patient.",
  },
  {
    title: "History, Templates & Letters",
    body: "All your generated explanations are saved in History. Create reusable Templates for consistent output, and generate patient Letters from free-text input.",
  },
  {
    title: "Customize Your Settings",
    body: "Set your specialty, preferred tone, detail level, and more in Settings. You can also provide Teaching Points to instruct the AI how to analyze data in your own style. Your preferences are synced across devices when signed in.",
  },
];

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState(0);
  const isLast = step === steps.length - 1;

  const handleNext = () => {
    if (isLast) {
      onComplete();
    } else {
      setStep((s) => s + 1);
    }
  };

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-card">
        <h2 className="onboarding-title">{steps[step].title}</h2>
        <p className="onboarding-body">{steps[step].body}</p>

        <div className="onboarding-dots">
          {steps.map((_, i) => (
            <span
              key={i}
              className={`onboarding-dot ${i === step ? "onboarding-dot--active" : ""}`}
            />
          ))}
        </div>

        <div className="onboarding-actions">
          <button className="onboarding-skip" onClick={onComplete}>
            Skip
          </button>
          <button className="onboarding-next" onClick={handleNext}>
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
