export interface HealthResponse {
  status: string;
}

export type PageType = "text" | "scanned" | "mixed";
export type InputMode = "pdf" | "text";

export interface PageDetection {
  page_number: number;
  page_type: PageType;
  char_count: number;
  confidence: number;
}

export interface DetectionResult {
  overall_type: PageType;
  total_pages: number;
  pages: PageDetection[];
}

export interface ExtractedTable {
  page_number: number;
  table_index: number;
  headers: string[];
  rows: string[][];
}

export interface PageExtractionResult {
  page_number: number;
  text: string;
  extraction_method: string;
  confidence: number;
  char_count: number;
}

export interface ExtractionResult {
  input_mode: InputMode;
  full_text: string;
  pages: PageExtractionResult[];
  tables: ExtractedTable[];
  detection: DetectionResult | null;
  total_pages: number;
  total_chars: number;
  filename: string | null;
  warnings: string[];
}

export interface ExtractionError {
  detail: string;
}

// --- Phase 3: Analysis Types ---

export type SeverityStatus =
  | "normal"
  | "mildly_abnormal"
  | "moderately_abnormal"
  | "severely_abnormal"
  | "undetermined";

export type AbnormalityDirection = "normal" | "above_normal" | "below_normal";

export interface ParsedMeasurement {
  name: string;
  abbreviation: string;
  value: number;
  unit: string;
  status: SeverityStatus;
  direction: AbnormalityDirection;
  reference_range: string | null;
  raw_text: string;
  page_number: number | null;
}

export interface ReportSection {
  name: string;
  content: string;
  page_number: number | null;
}

export interface ParsedReport {
  test_type: string;
  test_type_display: string;
  detection_confidence: number;
  measurements: ParsedMeasurement[];
  sections: ReportSection[];
  findings: string[];
  warnings: string[];
}

export interface TestTypeInfo {
  test_type_id: string;
  display_name: string;
  keywords: string[];
}

export interface DetectTypeResponse {
  test_type: string | null;
  confidence: number;
  available_types: TestTypeInfo[];
}

export interface ParseRequest {
  extraction_result: ExtractionResult;
  test_type?: string;
}

// --- Phase 4: LLM Explanation Types ---

export type LLMProvider = "claude" | "openai";
export type LiteracyLevel = "grade_4" | "grade_6" | "grade_8" | "clinical";

export interface MeasurementExplanation {
  abbreviation: string;
  value: number;
  unit: string;
  status: SeverityStatus;
  plain_language: string;
}

export interface FindingExplanation {
  finding: string;
  severity: "normal" | "mild" | "moderate" | "severe" | "informational";
  explanation: string;
}

export interface ExplanationResult {
  overall_summary: string;
  measurements: MeasurementExplanation[];
  key_findings: FindingExplanation[];
  questions_for_doctor: string[];
  disclaimer: string;
}

export interface ExplainRequest {
  extraction_result: ExtractionResult;
  test_type?: string;
  literacy_level?: LiteracyLevel;
  provider?: LLMProvider;
  api_key?: string;
}

export interface ExplainResponse {
  explanation: ExplanationResult;
  parsed_report: ParsedReport;
  validation_warnings: string[];
  phi_categories_found: string[];
  model_used: string;
  input_tokens: number;
  output_tokens: number;
}

export interface GlossaryResponse {
  test_type: string;
  glossary: Record<string, string>;
}

export interface AppSettings {
  llm_provider: LLMProvider;
  claude_api_key: string | null;
  openai_api_key: string | null;
  claude_model: string | null;
  openai_model: string | null;
  literacy_level: LiteracyLevel;
}

export interface SettingsUpdate {
  llm_provider?: LLMProvider;
  claude_api_key?: string;
  openai_api_key?: string;
  claude_model?: string;
  openai_model?: string;
  literacy_level?: LiteracyLevel;
}
