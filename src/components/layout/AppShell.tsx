import { useState, useEffect, useCallback, useRef } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { Sidebar } from "./Sidebar";
import { useSidecar } from "../../hooks/useSidecar";
import { sidecarApi } from "../../services/sidecarApi";
import { ConsentDialog } from "../shared/ConsentDialog";
import { OnboardingWizard } from "../onboarding/OnboardingWizard";
import "./AppShell.css";

export function AppShell() {
  const { isReady, error } = useSidecar();
  const navigate = useNavigate();
  const location = useLocation();
  const [consentChecked, setConsentChecked] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [showSetupBanner, setShowSetupBanner] = useState(false);
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState(false);
  const [updateAvailable, setUpdateAvailable] = useState<Update | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const prevPathRef = useRef(location.pathname);

  const checkSpecialty = useCallback(() => {
    if (!isReady || !consentGiven) return;
    sidecarApi
      .getSettings()
      .then((s) => {
        setShowSetupBanner(!s.specialty);
      })
      .catch(() => {});
  }, [isReady, consentGiven]);

  // Initial check when ready
  useEffect(() => {
    checkSpecialty();
  }, [checkSpecialty]);

  // Re-check after navigating away from settings (user may have saved)
  useEffect(() => {
    const prev = prevPathRef.current;
    prevPathRef.current = location.pathname;
    if (prev === "/settings" && location.pathname !== "/settings") {
      checkSpecialty();
    }
  }, [location.pathname, checkSpecialty]);

  useEffect(() => {
    if (!isReady) return;
    sidecarApi
      .getConsent()
      .then((res) => {
        setConsentGiven(res.consent_given);
        setConsentChecked(true);
      })
      .catch(() => {
        // Consent API failed — allow through gracefully
        setConsentGiven(true);
        setConsentChecked(true);
      });
  }, [isReady]);

  // Check onboarding status after consent is given
  useEffect(() => {
    if (!isReady || !consentGiven) return;
    sidecarApi
      .getOnboarding()
      .then((res) => {
        setOnboardingCompleted(res.onboarding_completed);
        setOnboardingChecked(true);
      })
      .catch(() => {
        setOnboardingCompleted(true);
        setOnboardingChecked(true);
      });
  }, [isReady, consentGiven]);

  // Silent update check on launch
  useEffect(() => {
    if (!isReady || !consentGiven) return;
    check().then((update) => {
      if (update?.available) setUpdateAvailable(update);
    }).catch(() => {});
  }, [isReady, consentGiven]);

  const handleUpdate = async () => {
    if (!updateAvailable) return;
    setIsUpdating(true);
    try {
      await updateAvailable.downloadAndInstall();
      await relaunch();
    } catch {
      setIsUpdating(false);
    }
  };

  const handleConsent = () => {
    sidecarApi.grantConsent().catch(() => {});
    setConsentGiven(true);
  };

  const handleOnboardingComplete = () => {
    sidecarApi.completeOnboarding().catch(() => {});
    setOnboardingCompleted(true);
  };

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-content">
        {error ? (
          <div className="sidecar-error">
            <h2>Connection Error</h2>
            <p>{error}</p>
          </div>
        ) : !isReady || !consentChecked ? (
          <div className="sidecar-loading">
            <p>Starting backend services...</p>
          </div>
        ) : !consentGiven ? (
          <ConsentDialog onConsent={handleConsent} />
        ) : !onboardingChecked ? (
          <div className="sidecar-loading">
            <p>Loading...</p>
          </div>
        ) : !onboardingCompleted ? (
          <OnboardingWizard onComplete={handleOnboardingComplete} />
        ) : (
          <>
            {updateAvailable && (
              <div className="setup-banner update-banner">
                <span>
                  A new version (v{updateAvailable.version}) is available.
                </span>
                <button
                  className="setup-banner-btn"
                  onClick={handleUpdate}
                  disabled={isUpdating}
                >
                  {isUpdating ? "Updating..." : "Update Now"}
                </button>
                <button
                  className="setup-banner-dismiss"
                  onClick={() => setUpdateAvailable(null)}
                  aria-label="Dismiss"
                >
                  &times;
                </button>
              </div>
            )}
            {showSetupBanner && (
              <div className="setup-banner">
                <span>Please configure your specialty in Settings.</span>
                <button
                  className="setup-banner-btn"
                  onClick={() => navigate("/settings")}
                >
                  Go to Settings
                </button>
                <button
                  className="setup-banner-dismiss"
                  onClick={() => setShowSetupBanner(false)}
                  aria-label="Dismiss"
                >
                  &times;
                </button>
              </div>
            )}
            <Outlet />
          </>
        )}
      </main>
    </div>
  );
}
