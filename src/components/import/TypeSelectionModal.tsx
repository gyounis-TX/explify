import { useRef } from "react";
import type { DetectTypeResponse } from "../../types/sidecar";
import { groupTypesByCategory } from "../../utils/testTypeCategories";
import { useModalAccessibility } from "../../hooks/useModalAccessibility";
import "../shared/TypeModal.css";

interface TypeSelectionModalProps {
  detectionResult: DetectTypeResponse | null;
  detectionStatus: "unknown" | "detected" | "low_confidence";
  selectedType: string | null;
  customType: string;
  onSelectedTypeChange: (type: string | null) => void;
  onCustomTypeChange: (value: string) => void;
  onConfirm: (chosen: string | null) => void;
  onClose: () => void;
}

export function TypeSelectionModal({
  detectionResult,
  detectionStatus,
  selectedType,
  customType,
  onSelectedTypeChange,
  onCustomTypeChange,
  onConfirm,
  onClose,
}: TypeSelectionModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  useModalAccessibility(modalRef, onClose);

  return (
    <div className="type-modal-backdrop" onClick={onClose}>
      <div
        className="type-modal"
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="type-selection-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="type-modal-title" id="type-selection-modal-title">
          Select Report Type
        </h3>
        <p className="type-modal-subtitle">
          {detectionStatus === "low_confidence" && detectionResult
            ? `We detected this might be a ${
                detectionResult.available_types?.find(
                  (t) => t.test_type_id === detectionResult.test_type,
                )?.display_name ?? detectionResult.test_type
              } (${Math.round(detectionResult.confidence * 100)}% confidence). Please confirm or select the correct type.`
            : "Could not automatically identify the report type. Please select the correct type below."}
        </p>

        {detectionResult?.available_types &&
          detectionResult.available_types.length > 0 && (
            <div className="type-modal-categories">
              {groupTypesByCategory(detectionResult.available_types).map(
                ([label, types]) => (
                  <div key={label} className="type-modal-category">
                    <span className="type-modal-category-label">{label}</span>
                    <div className="type-modal-category-buttons">
                      {types.map((t) => (
                        <button
                          key={t.test_type_id}
                          className={`detection-type-btn${
                            selectedType === t.test_type_id && !customType
                              ? " detection-type-btn--active"
                              : ""
                          }`}
                          onClick={() => {
                            onSelectedTypeChange(t.test_type_id);
                            onCustomTypeChange("");
                          }}
                        >
                          {t.display_name}
                        </button>
                      ))}
                    </div>
                  </div>
                ),
              )}
            </div>
          )}

        <div className="type-modal-other">
          <label className="type-modal-other-label">Other:</label>
          <input
            type="text"
            className="type-modal-other-input"
            autoComplete="off"
            placeholder='e.g. "calcium score", "renal ultrasound"'
            value={customType}
            onChange={(e) => {
              onCustomTypeChange(e.target.value);
              if (e.target.value) onSelectedTypeChange(null);
            }}
          />
        </div>

        <div className="type-modal-actions">
          <button className="type-modal-cancel" onClick={onClose}>
            Cancel
          </button>
          <button
            className="type-modal-confirm"
            disabled={!selectedType && !customType.trim()}
            onClick={() => {
              const chosen = customType.trim() || selectedType;
              onConfirm(chosen);
            }}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
