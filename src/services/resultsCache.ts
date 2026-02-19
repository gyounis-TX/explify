/**
 * Module-level cache for ResultsScreen state.
 *
 * Follows the same pattern as ImportScreen's module-level cache:
 * state lives in the JS heap, survives React component unmount during
 * sidebar navigation, and is cleared on explicit "Back to Import" /
 * "Start Fresh" actions or on page refresh/tab close.
 *
 * PHI stays in JS heap only — never persisted to localStorage/sessionStorage.
 */

import type {
  ExplainResponse,
  ExtractionResult,
  LiteracyLevel,
} from "../types/sidecar";

export interface ResultsStateCache {
  currentResponse: ExplainResponse | null;
  shortCommentText: string | null;
  longExplanationResponse: ExplainResponse | null;
  smsText: string | null;
  toneSlider: number;
  detailSlider: number;
  selectedLiteracy: LiteracyLevel;
  commentMode: "long" | "short" | "sms";
  isEditing: boolean;
  editedSummary: string;
  editedFindings: { finding: string; explanation: string }[];
  isDirty: boolean;
  historyId: string | number | null;
  isLiked: boolean;
  selectedTemplateId: string | number | undefined;
  combinedSummary: string | null;
  extractionResult: ExtractionResult | null;
  fromHistory: boolean;
  clinicalContext: string | undefined;
  quickReasons: string[] | undefined;
  isSpanish: boolean;
}

function freshCache(): ResultsStateCache {
  return {
    currentResponse: null,
    shortCommentText: null,
    longExplanationResponse: null,
    smsText: null,
    toneSlider: 3,
    detailSlider: 3,
    selectedLiteracy: "grade_8",
    commentMode: "short",
    isEditing: false,
    editedSummary: "",
    editedFindings: [],
    isDirty: false,
    historyId: null,
    isLiked: false,
    selectedTemplateId: undefined,
    combinedSummary: null,
    extractionResult: null,
    fromHistory: false,
    clinicalContext: undefined,
    quickReasons: undefined,
    isSpanish: false,
  };
}

let _cache: ResultsStateCache = freshCache();

export function getResultsCache(): ResultsStateCache {
  return _cache;
}

export function setResultsCache(state: ResultsStateCache): void {
  _cache = state;
}

export function clearResultsCache(): void {
  _cache = freshCache();
}
