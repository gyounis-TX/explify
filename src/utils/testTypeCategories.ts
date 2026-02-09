import type { TestTypeInfo } from "../types/sidecar";

export const CATEGORY_LABELS: Record<string, string> = {
  cardiac: "Cardiac",
  interventional: "Interventional / Procedures",
  vascular: "Vascular",
  lab: "Laboratory",
  imaging_ct: "CT Scans",
  imaging_mri: "MRI",
  imaging_ultrasound: "Ultrasound",
  imaging_xray: "X-Ray / Radiography",
  pulmonary: "Pulmonary",
  neurophysiology: "Neurophysiology",
  endoscopy: "Endoscopy",
  pathology: "Pathology",
  allergy: "Allergy / Immunology",
  dermatology: "Dermatology",
};

export const CATEGORY_ORDER = [
  "cardiac", "interventional", "vascular", "lab",
  "imaging_ct", "imaging_mri", "imaging_ultrasound", "imaging_xray",
  "pulmonary", "neurophysiology", "endoscopy", "pathology",
  "allergy", "dermatology",
];

export function groupTypesByCategory(types: TestTypeInfo[]): [string, TestTypeInfo[]][] {
  const groups = new Map<string, TestTypeInfo[]>();
  for (const t of types) {
    const cat = t.category ?? "other";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat)!.push(t);
  }
  const result: [string, TestTypeInfo[]][] = [];
  for (const cat of CATEGORY_ORDER) {
    const items = groups.get(cat);
    if (items) {
      result.push([CATEGORY_LABELS[cat] ?? cat, items]);
      groups.delete(cat);
    }
  }
  for (const [cat, items] of groups) {
    const label = CATEGORY_LABELS[cat] ?? cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    result.push([label, items]);
  }
  return result;
}
