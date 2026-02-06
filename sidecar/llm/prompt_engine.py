"""
Prompt construction for medical report explanation.

Builds a system prompt (role, rules, anti-hallucination constraints)
and a user prompt (parsed report data, reference ranges, glossary).

The LLM acts AS the physician in the specified specialty, producing
patient-facing communications that require no editing before sending.
"""

from __future__ import annotations

import re
from enum import Enum

from api.analysis_models import ParsedReport


def _extract_indication_from_report(report_text: str) -> str | None:
    """Extract indication/reason for study from report header.

    Many medical reports include an 'Indication:' or 'Reason for study:'
    line near the top. This function extracts that text so it can be used
    as clinical context when none is explicitly provided.
    """
    patterns = [
        r"Indication[s]?:\s*(.+?)(?:\n|$)",
        r"Reason for (?:study|exam|test|examination):\s*(.+?)(?:\n|$)",
        r"Clinical indication[s]?:\s*(.+?)(?:\n|$)",
        r"Reason for referral:\s*(.+?)(?:\n|$)",
        r"Clinical history:\s*(.+?)(?:\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, report_text, re.IGNORECASE)
        if match:
            indication = match.group(1).strip()
            # Skip if it's just "None" or empty
            if indication.lower() not in ("none", "n/a", "not provided", ""):
                return indication
    return None


# ---------------------------------------------------------------------------
# Medication Awareness
# ---------------------------------------------------------------------------

# Common medications and their effects on test interpretation
_MEDICATION_EFFECTS: dict[str, list[str]] = {
    # Cardiac medications
    "beta_blockers": [
        "Beta blockers (metoprolol, atenolol, carvedilol, bisoprolol, propranolol) "
        "lower heart rate and blunt exercise response. A 'low' heart rate is expected. "
        "Peak exercise HR may not reach target. Evaluate chronotropic response in context."
    ],
    "ace_arb": [
        "ACE inhibitors/ARBs (lisinopril, losartan, valsartan, olmesartan) can cause "
        "mild potassium elevation and creatinine increase (up to 30% is acceptable). "
        "A small creatinine rise does not indicate renal failure."
    ],
    "diuretics": [
        "Diuretics (furosemide, hydrochlorothiazide, spironolactone, chlorthalidone) "
        "can cause electrolyte changes: low potassium/magnesium (loop/thiazide) or "
        "high potassium (spironolactone). Also may elevate uric acid and glucose."
    ],
    "statins": [
        "Statins (atorvastatin, rosuvastatin, simvastatin, pravastatin) may cause "
        "mild transaminase elevation (ALT/AST). Up to 3x normal is generally acceptable. "
        "May also slightly elevate CK."
    ],
    "anticoagulants": [
        "Anticoagulants (warfarin, apixaban, rivaroxaban, dabigatran, enoxaparin) "
        "affect coagulation studies. INR is expected to be elevated on warfarin. "
        "Direct oral anticoagulants may affect factor Xa and thrombin time."
    ],
    "antiplatelets": [
        "Antiplatelets (aspirin, clopidogrel, prasugrel, ticagrelor) affect platelet "
        "function tests but not standard coagulation studies or platelet count."
    ],
    # Endocrine medications
    "thyroid_meds": [
        "Thyroid medications (levothyroxine, methimazole, PTU) directly affect thyroid "
        "labs. TSH may take 6-8 weeks to equilibrate after dose changes. Interpret "
        "thyroid panels in context of medication timing."
    ],
    "diabetes_meds": [
        "Diabetes medications: Metformin can rarely cause lactic acidosis and B12 "
        "deficiency. SGLT2 inhibitors (empagliflozin, dapagliflozin) cause glycosuria "
        "and may affect kidney function tests. GLP-1 agonists may slow gastric emptying."
    ],
    "steroids": [
        "Corticosteroids (prednisone, dexamethasone, hydrocortisone) cause glucose "
        "elevation, electrolyte changes, and may suppress adrenal function. They can "
        "also cause leukocytosis (elevated WBC) without infection."
    ],
    # Other common medications
    "nsaids": [
        "NSAIDs (ibuprofen, naproxen, meloxicam, celecoxib) can affect renal function "
        "(elevated creatinine, reduced eGFR), cause fluid retention, and may affect "
        "blood pressure. Can also cause GI bleeding affecting hemoglobin."
    ],
    "proton_pump_inhibitors": [
        "PPIs (omeprazole, pantoprazole, esomeprazole) can cause low magnesium, B12 "
        "deficiency with long-term use, and may affect iron absorption."
    ],
    "antidepressants": [
        "SSRIs/SNRIs may affect platelet function and sodium levels (SIADH causing "
        "hyponatremia). QTc prolongation can occur with certain antidepressants."
    ],
}

# Medication name patterns for extraction
_MEDICATION_PATTERNS: dict[str, list[str]] = {
    "beta_blockers": [
        r"\b(?:metoprolol|atenolol|carvedilol|bisoprolol|propranolol|nadolol|"
        r"nebivolol|labetalol|lopressor|toprol|coreg)\b"
    ],
    "ace_arb": [
        r"\b(?:lisinopril|enalapril|ramipril|benazepril|captopril|"
        r"losartan|valsartan|olmesartan|irbesartan|telmisartan|candesartan|"
        r"prinivil|zestril|diovan|cozaar|benicar)\b"
    ],
    "diuretics": [
        r"\b(?:furosemide|lasix|hydrochlorothiazide|hctz|spironolactone|"
        r"chlorthalidone|bumetanide|metolazone|torsemide|aldactone)\b"
    ],
    "statins": [
        r"\b(?:atorvastatin|rosuvastatin|simvastatin|pravastatin|lovastatin|"
        r"pitavastatin|lipitor|crestor|zocor)\b"
    ],
    "anticoagulants": [
        r"\b(?:warfarin|coumadin|apixaban|eliquis|rivaroxaban|xarelto|"
        r"dabigatran|pradaxa|enoxaparin|lovenox|heparin)\b"
    ],
    "antiplatelets": [
        r"\b(?:aspirin|clopidogrel|plavix|prasugrel|effient|ticagrelor|brilinta)\b"
    ],
    "thyroid_meds": [
        r"\b(?:levothyroxine|synthroid|methimazole|tapazole|propylthiouracil|ptu|"
        r"liothyronine|cytomel|armour thyroid)\b"
    ],
    "diabetes_meds": [
        r"\b(?:metformin|glucophage|glipizide|glyburide|glimepiride|"
        r"empagliflozin|jardiance|dapagliflozin|farxiga|canagliflozin|invokana|"
        r"semaglutide|ozempic|wegovy|liraglutide|victoza|dulaglutide|trulicity|"
        r"sitagliptin|januvia|insulin)\b"
    ],
    "steroids": [
        r"\b(?:prednisone|prednisolone|dexamethasone|methylprednisolone|"
        r"hydrocortisone|cortisone|medrol)\b"
    ],
    "nsaids": [
        r"\b(?:ibuprofen|advil|motrin|naproxen|aleve|meloxicam|mobic|"
        r"celecoxib|celebrex|diclofenac|indomethacin|ketorolac)\b"
    ],
    "proton_pump_inhibitors": [
        r"\b(?:omeprazole|prilosec|pantoprazole|protonix|esomeprazole|nexium|"
        r"lansoprazole|prevacid|rabeprazole)\b"
    ],
    "antidepressants": [
        r"\b(?:sertraline|zoloft|fluoxetine|prozac|escitalopram|lexapro|"
        r"citalopram|celexa|paroxetine|paxil|venlafaxine|effexor|"
        r"duloxetine|cymbalta|bupropion|wellbutrin|trazodone)\b"
    ],
}


def _extract_medications_from_context(clinical_context: str) -> list[str]:
    """Extract medication classes detected in clinical context.

    Returns a list of medication class names (e.g., 'beta_blockers', 'statins')
    that were found in the clinical context text.
    """
    if not clinical_context:
        return []

    detected_classes: list[str] = []
    text_lower = clinical_context.lower()

    for med_class, patterns in _MEDICATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                detected_classes.append(med_class)
                break  # Only count each class once

    return detected_classes


def _build_medication_guidance(detected_classes: list[str]) -> str:
    """Build medication-specific interpretation guidance for detected medications."""
    if not detected_classes:
        return ""

    guidance_parts = [
        "\n## Medication Considerations",
        "The following medications were detected in the clinical context. "
        "Consider their effects when interpreting test results:\n",
    ]

    for med_class in detected_classes:
        effects = _MEDICATION_EFFECTS.get(med_class, [])
        for effect in effects:
            guidance_parts.append(f"- {effect}")

    return "\n".join(guidance_parts)


# ---------------------------------------------------------------------------
# Condition-Aware Interpretation
# ---------------------------------------------------------------------------

# Chronic conditions and their interpretation adjustments
_CONDITION_GUIDANCE: dict[str, str] = {
    "diabetes": (
        "DIABETES: A1C target is typically <7% but may be relaxed to <8% in elderly "
        "or those with comorbidities. Fasting glucose 100-125 is prediabetic; ≥126 is "
        "diabetic. For established diabetics, focus on control trend rather than "
        "single values. Kidney function monitoring is essential."
    ),
    "ckd": (
        "CHRONIC KIDNEY DISEASE: Baseline creatinine and eGFR are already reduced. "
        "Small creatinine changes are expected. Focus on stability rather than absolute "
        "values. Potassium and phosphorus monitoring important. Anemia (low Hgb) is "
        "expected in CKD stages 3-5. Drug dosing often adjusted for renal function."
    ),
    "heart_failure": (
        "HEART FAILURE: BNP/NT-proBNP may be chronically elevated. Focus on trend "
        "from baseline rather than absolute values. Fluid status affects many labs. "
        "Renal function may fluctuate with diuretic therapy. Low sodium can occur "
        "with fluid overload or diuretic use."
    ),
    "hypertension": (
        "HYPERTENSION: Monitor for target organ damage (kidney function, cardiac "
        "changes). Electrolytes may be affected by antihypertensive medications. "
        "LVH on echo is a sign of longstanding HTN."
    ),
    "atrial_fibrillation": (
        "ATRIAL FIBRILLATION: Irregular heart rate expected. If on anticoagulation, "
        "coagulation studies will be affected. LA enlargement is common and expected. "
        "Rate control is the primary goal for most patients."
    ),
    "copd": (
        "COPD: Baseline PFTs show obstructive pattern. Chronic CO2 retention may "
        "affect baseline labs. Pulmonary hypertension may develop. Polycythemia "
        "(elevated Hgb/Hct) can occur as compensation for chronic hypoxia."
    ),
    "cirrhosis": (
        "CIRRHOSIS/LIVER DISEASE: Baseline liver enzymes may be abnormal. Coagulation "
        "may be impaired (elevated INR without anticoagulation). Low albumin and "
        "platelet count are expected. Interpret creatinine cautiously as muscle mass "
        "is often reduced."
    ),
    "hypothyroidism": (
        "HYPOTHYROIDISM: If on replacement therapy, TSH should be normal. Untreated "
        "or undertreated hypothyroidism can cause elevated cholesterol, low sodium, "
        "and anemia. Weight and energy changes affect other parameters."
    ),
    "hyperthyroidism": (
        "HYPERTHYROIDISM: Can cause elevated liver enzymes, low cholesterol, "
        "tachycardia, atrial fibrillation, and bone loss. Monitor for improvement "
        "with treatment."
    ),
    "anemia": (
        "CHRONIC ANEMIA: Baseline Hgb is already low. Focus on stability and trend. "
        "Identify type (iron deficiency, B12, chronic disease) for targeted "
        "interpretation. Compensatory changes may be present."
    ),
    "obesity": (
        "OBESITY: Metabolic syndrome components (glucose, lipids, blood pressure) "
        "are common. Fatty liver may cause mild transaminase elevation. Sleep apnea "
        "may cause pulmonary hypertension and polycythemia."
    ),
    "cancer": (
        "ACTIVE MALIGNANCY: Many lab abnormalities can occur. Anemia of chronic "
        "disease is common. Chemotherapy affects counts and organ function. "
        "Tumor markers should be interpreted in clinical context."
    ),
    "autoimmune": (
        "AUTOIMMUNE DISEASE: Chronic inflammation affects multiple lab values. "
        "Anemia of chronic disease, elevated inflammatory markers expected. "
        "Immunosuppressive medications have their own effects."
    ),
}

# Condition detection patterns
_CONDITION_PATTERNS: dict[str, list[str]] = {
    "diabetes": [
        r"\b(?:diabet(?:es|ic)|t2dm|t1dm|dm2|dm1|iddm|niddm|a1c|hba1c|"
        r"type\s*[12]\s*diabet|insulin[- ]?dependent)\b"
    ],
    "ckd": [
        r"\b(?:ckd|chronic\s*kidney|renal\s*(?:failure|insufficiency|disease)|"
        r"esrd|end[- ]?stage\s*renal|dialysis|gfr\s*(?:stage|<)|nephropathy)\b"
    ],
    "heart_failure": [
        r"\b(?:chf|hfref|hfpef|heart\s*failure|systolic\s*dysfunction|"
        r"diastolic\s*dysfunction|cardiomyopathy|reduced\s*ef|low\s*ef|"
        r"lvef\s*(?:<|reduced)|congestive)\b"
    ],
    "hypertension": [
        r"\b(?:htn|hypertension|high\s*blood\s*pressure|elevated\s*bp|"
        r"essential\s*hypertension)\b"
    ],
    "atrial_fibrillation": [
        r"\b(?:afib|a[- ]?fib|atrial\s*fibrillation|atrial\s*flutter|"
        r"af(?:ib)?(?:\s|$)|paroxysmal\s*af)\b"
    ],
    "copd": [
        r"\b(?:copd|chronic\s*obstructive|emphysema|chronic\s*bronchitis|"
        r"gold\s*stage|obstructive\s*lung\s*disease)\b"
    ],
    "cirrhosis": [
        r"\b(?:cirrhosis|liver\s*(?:disease|failure|fibrosis)|hepatic\s*"
        r"(?:disease|failure|encephalopathy)|nash|nafld|alcoholic\s*liver|"
        r"portal\s*hypertension|esophageal\s*varices|ascites)\b"
    ],
    "hypothyroidism": [
        r"\b(?:hypothyroid|hashimoto|low\s*thyroid|underactive\s*thyroid|"
        r"thyroid\s*replacement|levothyroxine|synthroid)\b"
    ],
    "hyperthyroidism": [
        r"\b(?:hyperthyroid|graves|overactive\s*thyroid|thyrotoxicosis|"
        r"high\s*thyroid)\b"
    ],
    "anemia": [
        r"\b(?:anemia|anaemia|low\s*(?:hgb|hemoglobin|hematocrit)|"
        r"iron\s*deficiency|b12\s*deficiency|folate\s*deficiency)\b"
    ],
    "obesity": [
        r"\b(?:obesity|obese|morbid(?:ly)?\s*obese|bmi\s*(?:>|over)\s*30|"
        r"metabolic\s*syndrome|bariatric)\b"
    ],
    "cancer": [
        r"\b(?:cancer|malignancy|carcinoma|lymphoma|leukemia|melanoma|"
        r"oncology|chemotherapy|radiation\s*therapy|tumor|metasta)\b"
    ],
    "autoimmune": [
        r"\b(?:lupus|sle|rheumatoid\s*arthritis|ra\b|psoriatic\s*arthritis|"
        r"sjogren|autoimmune|inflammatory\s*arthritis|vasculitis|"
        r"scleroderma|myasthenia)\b"
    ],
}


def _extract_conditions_from_context(clinical_context: str) -> list[str]:
    """Extract chronic conditions detected in clinical context."""
    if not clinical_context:
        return []

    detected: list[str] = []
    text_lower = clinical_context.lower()

    for condition, patterns in _CONDITION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                detected.append(condition)
                break

    return detected


def _build_condition_guidance(detected_conditions: list[str]) -> str:
    """Build condition-specific interpretation guidance."""
    if not detected_conditions:
        return ""

    parts = [
        "\n## Chronic Condition Considerations",
        "The following conditions were detected. Adjust interpretation accordingly:\n",
    ]

    for condition in detected_conditions:
        guidance = _CONDITION_GUIDANCE.get(condition)
        if guidance:
            parts.append(f"- {guidance}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Chief Complaint Extraction
# ---------------------------------------------------------------------------

_CHIEF_COMPLAINT_PATTERNS = [
    r"(?:chief\s*complaint|cc|presenting\s*complaint)[:=]\s*(.+?)(?:\n|$)",
    r"(?:presents?\s*(?:with|for)|complaining\s*of|c/o)[:=]?\s*(.+?)(?:\n|\.)",
    r"(?:reason\s*for\s*visit|rfv)[:=]\s*(.+?)(?:\n|$)",
    r"(?:hpi|history\s*of\s*present\s*illness)[:=]?\s*(.+?)(?:\n|\.)",
]

_SYMPTOM_FINDING_CORRELATIONS: dict[str, list[str]] = {
    "chest_pain": [
        "Chest pain workup: Cardiac enzymes (troponin), EKG findings, and echo "
        "function are key. Address whether findings support or exclude acute "
        "coronary syndrome, pericarditis, or musculoskeletal cause."
    ],
    "shortness_of_breath": [
        "Dyspnea workup: Evaluate cardiac function (EF, filling pressures), "
        "pulmonary findings, and oxygenation. BNP elevation suggests cardiac cause. "
        "Address whether findings point to cardiac vs pulmonary etiology."
    ],
    "fatigue": [
        "Fatigue workup: Check for anemia (Hgb), thyroid dysfunction (TSH), "
        "diabetes (glucose/A1C), and cardiac function. Iron studies and B12 "
        "may be relevant. Address which findings may explain the symptom."
    ],
    "palpitations": [
        "Palpitations workup: Rhythm assessment is key. Check for arrhythmias, "
        "thyroid dysfunction, anemia, and structural heart disease. Electrolytes "
        "(K, Mg) can contribute. Address whether cause was identified."
    ],
    "syncope": [
        "Syncope workup: Evaluate for arrhythmia, structural heart disease "
        "(AS, HCM, RVOT obstruction), and orthostatic causes. EKG intervals "
        "(QT) and echo findings are critical. Address identified vs unexplained."
    ],
    "edema": [
        "Edema workup: Evaluate cardiac function (EF, right heart), renal "
        "function, liver function (albumin), and venous studies. BNP helps "
        "distinguish cardiac from other causes."
    ],
    "dizziness": [
        "Dizziness workup: Distinguish cardiac (arrhythmia, AS) from neurologic "
        "or vestibular causes. Check blood pressure, heart rhythm, and consider "
        "anemia or metabolic causes."
    ],
    "weight_changes": [
        "Weight change workup: Evaluate thyroid function, glucose metabolism, "
        "fluid status, and nutritional markers. Unintentional weight loss "
        "warrants malignancy consideration."
    ],
}

_SYMPTOM_PATTERNS: dict[str, list[str]] = {
    "chest_pain": [r"\b(?:chest\s*pain|angina|cp\b|substernal|precordial)\b"],
    "shortness_of_breath": [
        r"\b(?:shortness\s*of\s*breath|dyspnea|sob\b|breathless|"
        r"difficulty\s*breathing|doe\b|pnd\b|orthopnea)\b"
    ],
    "fatigue": [r"\b(?:fatigue|tired|exhausted|malaise|weakness|lethargy)\b"],
    "palpitations": [r"\b(?:palpitation|racing\s*heart|heart\s*flutter|skipped\s*beat)\b"],
    "syncope": [r"\b(?:syncope|faint|passed\s*out|loss\s*of\s*consciousness|loc\b)\b"],
    "edema": [r"\b(?:edema|swelling|swollen\s*(?:leg|ankle|feet)|fluid\s*retention)\b"],
    "dizziness": [r"\b(?:dizz(?:y|iness)|lightheaded|vertigo|presyncope)\b"],
    "weight_changes": [
        r"\b(?:weight\s*(?:loss|gain)|losing\s*weight|gaining\s*weight|"
        r"unintentional\s*weight)\b"
    ],
}


def _extract_chief_complaint(clinical_context: str) -> str | None:
    """Extract the chief complaint from clinical context."""
    if not clinical_context:
        return None

    for pattern in _CHIEF_COMPLAINT_PATTERNS:
        match = re.search(pattern, clinical_context, re.IGNORECASE)
        if match:
            complaint = match.group(1).strip()
            if len(complaint) > 3 and complaint.lower() not in ("none", "n/a"):
                return complaint

    return None


def _extract_symptoms(clinical_context: str) -> list[str]:
    """Extract symptom categories from clinical context."""
    if not clinical_context:
        return []

    detected: list[str] = []
    text_lower = clinical_context.lower()

    for symptom, patterns in _SYMPTOM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                detected.append(symptom)
                break

    return detected


def _build_chief_complaint_guidance(
    chief_complaint: str | None,
    detected_symptoms: list[str],
) -> str:
    """Build guidance for addressing the chief complaint."""
    parts: list[str] = []

    if chief_complaint:
        parts.append("\n## Chief Complaint Correlation")
        parts.append(f'The patient presented with: "{chief_complaint}"')
        parts.append(
            "\nCRITICAL: You MUST explicitly address whether the test findings:\n"
            "- SUPPORT a cause related to this complaint\n"
            "- ARGUE AGAINST a cause related to this complaint\n"
            "- Are INCONCLUSIVE for explaining this complaint\n"
            "Do not simply describe findings — tie them to the clinical question."
        )

    if detected_symptoms:
        if not parts:
            parts.append("\n## Symptom Correlation")
        else:
            parts.append("\n### Symptom-Specific Guidance")

        for symptom in detected_symptoms:
            correlations = _SYMPTOM_FINDING_CORRELATIONS.get(symptom, [])
            for correlation in correlations:
                parts.append(f"- {correlation}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Enhanced Lab Pattern Recognition
# ---------------------------------------------------------------------------

_LAB_PATTERN_GUIDANCE: dict[str, str] = {
    "dka": (
        "DIABETIC KETOACIDOSIS PATTERN: High glucose (often >250) + metabolic acidosis "
        "(low bicarb, low pH) + positive ketones + anion gap elevation. This is a "
        "medical emergency requiring immediate attention."
    ),
    "hhs": (
        "HYPEROSMOLAR HYPERGLYCEMIC STATE: Very high glucose (often >600) + high "
        "osmolality + minimal or no ketones. More common in T2DM. Severe dehydration "
        "is typical."
    ),
    "hepatorenal": (
        "HEPATORENAL PATTERN: Liver dysfunction (elevated bili, low albumin, abnormal "
        "INR) combined with acute kidney injury (rising creatinine) suggests "
        "hepatorenal syndrome. This indicates severe liver disease."
    ),
    "tumor_lysis": (
        "TUMOR LYSIS PATTERN: Elevated uric acid + elevated potassium + elevated "
        "phosphorus + low calcium. Can occur spontaneously in aggressive malignancies "
        "or after chemotherapy. Requires urgent management."
    ),
    "sepsis": (
        "SEPSIS/INFECTION PATTERN: Elevated WBC (or very low WBC) + elevated lactate + "
        "bandemia + organ dysfunction markers. Procalcitonin elevation supports "
        "bacterial infection. Clinical context is essential."
    ),
    "hemolysis": (
        "HEMOLYSIS PATTERN: Low haptoglobin + elevated LDH + elevated indirect "
        "bilirubin + reticulocytosis + anemia. Suggests red blood cell destruction. "
        "Direct Coombs helps distinguish immune vs non-immune causes."
    ),
    "rhabdomyolysis": (
        "RHABDOMYOLYSIS PATTERN: Markedly elevated CK (often >10,000) + elevated "
        "myoglobin + acute kidney injury + dark urine. Muscle breakdown releasing "
        "contents into blood. Hydration is critical."
    ),
    "siadh": (
        "SIADH PATTERN: Low sodium (hyponatremia) + low serum osmolality + "
        "inappropriately concentrated urine (high urine osmolality) + euvolemia. "
        "Common with certain medications, malignancies, and CNS disorders."
    ),
    "adrenal_insufficiency": (
        "ADRENAL INSUFFICIENCY PATTERN: Low cortisol (especially AM) + low sodium + "
        "high potassium + low glucose + eosinophilia. May see hyperpigmentation "
        "clinically. Requires cortisol replacement."
    ),
    "thyroid_storm": (
        "THYROID STORM PATTERN: Very low TSH + very high T4/T3 + tachycardia + "
        "fever + altered mental status + elevated liver enzymes. This is a "
        "medical emergency requiring immediate treatment."
    ),
    "myxedema": (
        "MYXEDEMA PATTERN: Very high TSH + very low T4 + hypothermia + bradycardia + "
        "altered mental status + hyponatremia. Severe hypothyroidism requiring "
        "urgent thyroid replacement."
    ),
    "dic": (
        "DIC PATTERN: Low platelets + prolonged PT/INR + prolonged PTT + low "
        "fibrinogen + elevated D-dimer + schistocytes on smear. Indicates "
        "consumptive coagulopathy, often with underlying sepsis or malignancy."
    ),
    "ttp_hus": (
        "TTP/HUS PATTERN: Microangiopathic hemolytic anemia (low Hgb, schistocytes, "
        "elevated LDH) + thrombocytopenia + acute kidney injury ± neurologic symptoms "
        "± fever. ADAMTS13 activity helps distinguish. Urgent hematology consult needed."
    ),
    "pancreatitis": (
        "PANCREATITIS PATTERN: Elevated lipase (>3x normal) ± elevated amylase + "
        "abdominal pain. Triglycerides >1000 can cause pancreatitis. Check calcium "
        "as hypocalcemia can occur."
    ),
    "alcoholic_hepatitis": (
        "ALCOHOLIC HEPATITIS PATTERN: AST:ALT ratio >2:1 + elevated bilirubin + "
        "history of alcohol use. GGT often markedly elevated. MCV may be elevated. "
        "Maddrey score helps assess severity."
    ),
    "drug_induced_liver": (
        "DRUG-INDUCED LIVER INJURY: Elevated transaminases (often >10x normal) with "
        "temporal relationship to new medication. Check acetaminophen level. Pattern "
        "may be hepatocellular, cholestatic, or mixed."
    ),
    "heart_failure_decompensation": (
        "DECOMPENSATED HEART FAILURE: Elevated BNP/NT-proBNP (often >3x baseline) + "
        "possible prerenal azotemia (elevated BUN:Cr ratio) + possible hyponatremia. "
        "Troponin may be mildly elevated from demand ischemia."
    ),
    "acute_coronary_syndrome": (
        "ACUTE CORONARY SYNDROME PATTERN: Elevated troponin (rising pattern) + "
        "clinical symptoms + EKG changes. Even small troponin elevations are "
        "significant. Trend is important — check serial values."
    ),
    "pulmonary_embolism": (
        "PULMONARY EMBOLISM PATTERN: Elevated D-dimer + hypoxia + tachycardia + "
        "possible troponin/BNP elevation (right heart strain). D-dimer has high "
        "negative predictive value; elevated D-dimer needs imaging confirmation."
    ),
}


def _detect_lab_patterns(clinical_context: str, measurements: list) -> list[str]:
    """Detect complex lab patterns that should be highlighted.

    This checks for keywords in clinical context that suggest these patterns
    may be relevant. Actual pattern detection from lab values would require
    the measurement values themselves.
    """
    if not clinical_context:
        return []

    detected: list[str] = []
    text_lower = clinical_context.lower()

    # Pattern keywords to look for in clinical context
    pattern_keywords: dict[str, list[str]] = {
        "dka": ["dka", "diabetic ketoacidosis", "ketoacidosis"],
        "hhs": ["hhs", "hyperosmolar", "hyperglycemic state"],
        "hepatorenal": ["hepatorenal", "liver failure.*kidney", "cirrhosis.*aki"],
        "tumor_lysis": ["tumor lysis", "tls", "chemotherapy"],
        "sepsis": ["sepsis", "septic", "bacteremia", "infection"],
        "hemolysis": ["hemolysis", "hemolytic", "haptoglobin"],
        "rhabdomyolysis": ["rhabdo", "rhabdomyolysis", "crush", "elevated ck"],
        "siadh": ["siadh", "hyponatremia", "inappropriate adh"],
        "adrenal_insufficiency": ["adrenal insufficiency", "addison", "hypoadrenal"],
        "thyroid_storm": ["thyroid storm", "thyrotoxic crisis"],
        "myxedema": ["myxedema", "severe hypothyroid"],
        "dic": ["dic", "disseminated intravascular", "consumptive coagulopathy"],
        "ttp_hus": ["ttp", "hus", "thrombotic thrombocytopenic", "hemolytic uremic"],
        "pancreatitis": ["pancreatitis", "elevated lipase"],
        "alcoholic_hepatitis": ["alcoholic hepatitis", "alcohol.*liver"],
        "heart_failure_decompensation": ["chf exacerbation", "decompensated", "volume overload"],
        "acute_coronary_syndrome": ["acs", "nstemi", "stemi", "mi", "heart attack", "troponin"],
        "pulmonary_embolism": ["pe", "pulmonary embolism", "dvt", "clot"],
    }

    for pattern, keywords in pattern_keywords.items():
        for keyword in keywords:
            if re.search(keyword, text_lower):
                detected.append(pattern)
                break

    return detected


def _build_lab_pattern_guidance(detected_patterns: list[str]) -> str:
    """Build guidance for detected lab patterns."""
    if not detected_patterns:
        return ""

    parts = [
        "\n## Clinical Pattern Recognition",
        "The following clinical patterns may be relevant based on the context:\n",
    ]

    for pattern in detected_patterns:
        guidance = _LAB_PATTERN_GUIDANCE.get(pattern)
        if guidance:
            parts.append(f"- {guidance}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Analogy Library for Patient Understanding
# ---------------------------------------------------------------------------

_ANALOGY_LIBRARY = """
## Analogy Guidelines for Patient Understanding

When explaining measurements and findings, use relatable comparisons to help patients understand:

### Size Comparisons (mm/cm)
- 1-2mm: grain of rice, pinhead
- 3-4mm: peppercorn, small pea
- 5-6mm: pencil eraser, blueberry
- 10mm (1cm): fingertip, marble, peanut
- 2cm: grape, cherry
- 3cm: walnut, ping pong ball
- 5cm: lime, golf ball

### Cardiac Function (Ejection Fraction)
- 55-70%: "Your heart is pumping strongly and efficiently"
- 40-54%: "Your heart is pumping but not at full strength — like an engine running on fewer cylinders"
- <40%: "Your heart is working harder than it should to pump blood"

### Lab Value Analogies
- **Hemoglobin**: "Carries oxygen in your blood — like cargo trucks delivering oxygen to your body"
- **Cholesterol**: "LDL is like delivery trucks dropping packages in your arteries; HDL is like cleanup trucks removing them"
- **Creatinine/eGFR**: "Measures how well your kidneys filter waste — like checking how well a coffee filter works"
- **A1C**: "A 3-month average of your blood sugar — a snapshot over time, not just today"
- **TSH**: "The signal your brain sends to control your thyroid — high means your thyroid is underactive, low means overactive"

### Severity Context
- **Trace/trivial**: "So small it's barely detectable"
- **Mild**: "A small change — typically not concerning on its own"
- **Moderate**: "Noticeable but usually manageable"
- **Severe**: "Significant enough to need attention"

### Prevalence for Reassurance
When appropriate, provide context like:
- "Thyroid nodules are found in about 50% of people over 60"
- "Small lung nodules appear in about 1 in 4 chest CTs"
- "Trace valve leakage is seen in most healthy hearts"

### Usage Rules
1. Always pair numbers with analogies: "6mm — about the size of a pencil eraser"
2. Use functional analogies for percentages: "pumping at 55% efficiency"
3. Provide risk context when available: "less than 1% chance of being concerning"
4. Connect to daily life: "This explains why you might feel tired"
"""


class LiteracyLevel(str, Enum):
    GRADE_4 = "grade_4"
    GRADE_6 = "grade_6"
    GRADE_8 = "grade_8"
    GRADE_12 = "grade_12"
    CLINICAL = "clinical"


_LITERACY_DESCRIPTIONS: dict[LiteracyLevel, str] = {
    LiteracyLevel.GRADE_4: (
        "4th-grade level. Very simple words, short sentences. "
        "No medical jargon — use everyday analogies. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.GRADE_6: (
        "6th-grade level. Simple, clear language. Short sentences. "
        "Briefly define any medical term you must use. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.GRADE_8: (
        "8th-grade level. Clear language with brief definitions of "
        "technical terms. Moderate sentence complexity is acceptable. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.GRADE_12: (
        "12th-grade / college level. Natural adult language with medical "
        "terms introduced in context and briefly explained. "
        "The clinical interpretation structure stays the same."
    ),
    LiteracyLevel.CLINICAL: (
        "Physician-level. Standard medical terminology allowed. "
        "Be precise and concise. Still patient-facing in tone. "
        "The clinical interpretation structure stays the same."
    ),
}


_TONE_DESCRIPTIONS: dict[int, str] = {
    1: (
        "Be direct and clinical about all findings, including abnormal ones. "
        "Do not sugarcoat or minimize concerning results. State facts plainly."
    ),
    2: (
        "Be matter-of-fact and straightforward. State findings clearly "
        "without adding extra reassurance. Keep the tone professional."
    ),
    3: (
        "Balance clinical precision with empathy. Acknowledge concerning "
        "findings while providing appropriate context. Use a calm, "
        "neutral tone."
    ),
    4: (
        "Emphasize positive and normal findings. Frame concerns gently "
        "with reassuring context. Use warm, supportive language."
    ),
    5: (
        "Lead with good news and normal findings. Be warm, empathetic, "
        "and comforting throughout. Minimize alarm for abnormal findings "
        "while still being accurate."
    ),
}

_DETAIL_DESCRIPTIONS: dict[int, str] = {
    1: (
        "Be extremely brief. Provide only the most essential information. "
        "1-2 sentences per section. Omit background and context."
    ),
    2: (
        "Be concise. Cover key points only with short explanations. "
        "2-3 sentences per section. Minimal background detail."
    ),
    3: (
        "Provide a standard level of detail. 3-5 sentences per section. "
        "Include enough context to understand each finding."
    ),
    4: (
        "Be thorough. Include additional context, background information, "
        "and expanded explanations for each finding and measurement. "
        "4-6 sentences per section."
    ),
    5: (
        "Be very comprehensive. Provide detailed explanations with full "
        "clinical context for every finding. Include background on what "
        "each measurement means and why it matters. 5-8 sentences per section."
    ),
}

# ---------------------------------------------------------------------------
# Core Identity — the LLM IS the physician
# ---------------------------------------------------------------------------

_PHYSICIAN_IDENTITY = """\
## YOUR IDENTITY

You are a clinical communicator in {specialty}. You are writing a message
that will be sent directly to a patient about their test results.

- In first-person mode, you ARE the physician — writing as yourself to your
  own patient.
- In third-person mode, you are a member of the care team (e.g., a nurse)
  writing on behalf of the named physician to the patient.

In either mode you write with the clinical authority and interpretive judgment
of a {specialty} specialist. The message must sound exactly like something the
physician or care team would write — natural, authoritative, and requiring NO
editing before the patient receives it.

You are NOT an AI assistant. You are NOT summarizing a report for review.
You are producing a finished communication from physician to patient.

"""

# ---------------------------------------------------------------------------
# Clinical Voice Rule
# ---------------------------------------------------------------------------

_CLINICAL_VOICE_RULE = """\
## CLINICAL VOICE — INTERPRET, DON'T NARRATE OR RECITE

Your message must sound like what a {specialty} specialist would write to a
patient after reviewing their results. Apply the clinical judgment, priorities,
and interpretive lens of a {specialty} specialist. Highlight what you as a
specialist would consider most significant, and de-emphasize what you would
consider incidental or clinically unimportant.

Core Principle: Interpret, don't narrate. Don't recite.
The patient already has a copy of their results. They can see the numbers.
Your job is NOT to walk them through each value — it is to EXPLAIN what the
results mean for THEM, in plain language, with clinical context.

- BAD (recitation): "Your LVEF was measured at 55%. Your LV end-diastolic
  diameter was 4.8 cm. Your left atrial volume index was 28 mL/m²."
- BAD (narrative): "The echocardiogram was performed and showed that the
  left ventricle was measured at 55%."
- GOOD (interpretive): "Your heart's pumping strength is normal, and the
  chambers are a healthy size — overall, your heart is working well."

For every finding, answer the patient's implicit question:
"What does this mean for me?"

Do NOT simply list measurements and values the patient can already read on
their report. Instead, synthesize findings into meaningful clinical statements
that help the patient understand their health.

"""

_INTERPRETATION_STRUCTURE = """\
## Required Interpretation Structure

Organize the overall_summary into these sections IN ORDER, each as its own
paragraph separated by a blank line (\\n\\n). Use the section labels as
mental structure — do NOT print the labels as headers in the output.

Remember: the patient already has their results. Do not recite values they
can already read. Synthesize findings into clinical meaning.

## Core Purpose: "Why This Report Matters"

Every interpretation must answer: "Why does this report matter to ME?"
The patient wants to know:
- Am I okay? Is something wrong?
- What does this mean for my daily life?
- Do I need to worry or change anything?
- Does this explain my symptoms?

Frame findings in terms of their real-world impact, not just medical status.
A "normal ejection fraction" means nothing to patients — "your heart is
pumping blood effectively" connects to their life.

1. BOTTOM LINE — 1-2 sentences stating what matters most and whether the
   findings are overall reassuring or concerning. Lead with the answer to
   "Am I okay?" before any details.

2. WHAT IS REASSURING — Synthesize normal or stable findings into a
   meaningful clinical statement. Group related normal findings together
   rather than listing each individually. For example, instead of listing
   every normal chamber size, say "Your heart chambers are all a normal
   size and your heart is pumping well."

   Connect to real life: "This means your heart is doing its job well and
   supporting your daily activities."

3. WHAT IS WORTH DISCUSSING — Abnormal or noteworthy findings, prioritized
   by clinical significance. Explain what each finding means for the
   patient, not just what the value is. Use softened, non-conclusive
   language scaled to severity:
   - Mild: "are worth mentioning", "is something to be aware of"
   - Moderate: "warrants discussion", "is something we should discuss"
   - Severe: "needs to be discussed", "is important to address"
   NEVER use definitive alarm language like "needs attention", "requires
   immediate action", or "is dangerous". The physician will determine
   urgency and next steps.
   a. More significant findings first, then less significant.
   b. Mild STENOSIS is clinically noteworthy — include with context.
   c. Mild REGURGITATION is very common and usually insignificant — mention
      only briefly in passing (e.g. "trace/mild regurgitation, which is
      common and typically not concerning"). Do NOT elevate it as an
      important finding.
   d. Only comment on valvular stenosis or regurgitation if the report
      specifically names and grades it (e.g. "trace mitral regurgitation",
      "mild aortic regurgitation"). A blanket exclusion such as "no
      significant valvular regurgitation" or "no significant stenosis" means
      nothing was found — do NOT interpret it as trace or mild disease.

4. HOW THIS RELATES TO YOUR SYMPTOMS — Tie findings directly to the
   patient's complaint or clinical context when provided. If no clinical
   context was given, omit this section.

5. WHAT THIS MEANS FOR YOU — A brief closing that summarizes the practical
   takeaway. What can the patient expect? What should they feel confident
   about? This reduces follow-up questions and improves understanding.

"""

_HIGH_ANXIETY_MODE = """\
## HIGH ANXIETY PATIENT MODE — ACTIVE

This patient has been flagged as high-anxiety. Your response must prioritize
emotional reassurance while remaining medically accurate.

### Communication Goals for Anxious Patients:
- Reduce worry and prevent panic
- Minimize follow-up clarification messages
- Improve understanding without causing alarm
- Build confidence in their health status

### Required Adjustments:

1. LEAD WITH REASSURANCE
   - Open with the most reassuring finding first
   - Use phrases like "The good news is...", "Reassuringly,...", "I'm pleased to report..."
   - Front-load positive information before any caveats

2. AVOID ALARMING LANGUAGE — Never use:
   - "abnormal", "concerning", "worrying", "troubling"
   - "needs attention", "requires action", "monitor closely"
   - "elevated risk", "increased chance", "higher likelihood"
   - Medical jargon without immediate, gentle explanation

   Instead use:
   - "slightly different from typical" instead of "abnormal"
   - "worth a conversation" instead of "concerning"
   - "something we noticed" instead of "finding"
   - "on the higher/lower side" instead of "elevated/decreased"

3. CONTEXTUALIZE ALL FINDINGS
   - For ANY non-normal finding, immediately explain how common it is
   - "This is something we see frequently and is usually not serious"
   - "Many people have this and live completely normal, active lives"
   - Provide perspective: "While this is technically outside the normal range..."

4. EMPHASIZE WHAT IS WORKING WELL
   - Spend more time on normal findings
   - Be explicit about what is NOT wrong
   - "Your heart is pumping strongly", "Your kidney function is excellent"

5. END ON A POSITIVE NOTE
   - Final paragraph must be reassuring
   - Reinforce that the physician is available for questions
   - Express confidence in the patient's health trajectory

6. SIMPLIFY LANGUAGE
   - Use the simplest possible terms
   - Explain everything as if to someone with no medical background
   - Avoid numbers when possible; use descriptive language instead

"""

_TONE_RULES = """\
## Tone Rules
- Speak directly to the patient ("you," "your heart").
- Calm, confident, and clinically grounded.
- Reassuring when appropriate, but never dismissive.
- Never alarmist. Never use definitive alarm language.
- Never speculative beyond the report.
- Use hedging language where clinically appropriate: "may," "appears to,"
  "could suggest," "seems to indicate."
- For abnormal findings, use softened language: "warrants discussion,"
  "worth mentioning," "something to discuss," "something to be aware of."
- AVOID conclusive/alarming phrasing: "needs attention," "requires action,"
  "is dangerous," "is critical," "proves," "confirms," "definitely."

"""

_NO_RECOMMENDATIONS_RULE = """\
## CRITICAL: NO TREATMENT SUGGESTIONS OR HYPOTHETICAL ACTIONS

NEVER include:
- Suggestions of what the doctor may or may not recommend (e.g. "your doctor
  may recommend further testing", "we may need to adjust your medication")
- Hypothetical treatment plans or next steps
- Suggestions about future bloodwork, imaging, or procedures
- Phrases like "your doctor may want to...", "we will need to...",
  "this may require...", "additional testing may be needed"
- ANY forward-looking medical action items

You are providing an INTERPRETATION of findings, not a treatment plan.
The physician using this tool will add their own specific recommendations
separately. Your job is to explain WHAT the results show and WHAT they mean,
not to suggest what should be done about them.

If the user has explicitly included specific next steps in their input,
you may include ONLY those exact next steps — do not embellish, expand,
or add your own.

"""

_SAFETY_RULES = """\
## Safety & Scope Rules
1. ONLY use data that appears in the report provided. NEVER invent, guess,
   or assume measurements, findings, or diagnoses not explicitly stated.
2. For each measurement, the app has already classified it against reference
   ranges. You MUST use the status provided (normal, mildly_abnormal, etc.)
   — do NOT re-classify.
3. When explaining a measurement, state the patient's value, the normal
   range, and interpret what the status means clinically.
4. If a measurement has status "undetermined", say the value was noted but
   cannot be classified without more context.
5. Do NOT mention the patient by name or include any PHI.
6. Do NOT introduce diagnoses not supported by the source report.
7. Do NOT provide medication advice or treatment recommendations.
8. Call the explain_report tool with your response. Do not produce any
   output outside of this tool call.
9. When prior values are provided, briefly note the trend. Don't
   over-interpret small fluctuations within normal range.
10. DATES — When comparing dates (e.g. current exam vs. prior study),
   always consider the FULL date including the YEAR. "1/31/2025" to
   "01/12/2026" is approximately one year apart, NOT two weeks.
   Calculate the actual elapsed time using years, months, and days.
   State the time interval accurately (e.g. "approximately one year
   ago", "about 11 months prior").

"""

_CLINICAL_DOMAIN_KNOWLEDGE_CARDIAC = """\
## Clinical Domain Knowledge — Cardiac

Apply these cardiac-specific interpretation rules:

- HYPERTROPHIC CARDIOMYOPATHY (HCM): A supra-normal or hyperdynamic ejection
  fraction (e.g. LVEF > 65-70%) is NOT reassuring in HCM. It may reflect
  hypercontractility from a thickened, stiff ventricle. Do NOT describe it as
  "strong" or "better than normal." Instead, note the EF value neutrally and
  explain that in the context of HCM, an elevated EF can be part of the
  disease pattern rather than a sign of good health.

- DIASTOLIC FUNCTION GRADING: When E/A ratio, E/e', and TR velocity are
  provided, synthesize them into a diastolic function assessment:
  - Grade I (impaired relaxation): E/A < 0.8, low e', normal LA
  - Grade II (pseudonormal): E/A 0.8-2.0, elevated E/e' > 14, enlarged LA
  - Grade III (restrictive): E/A > 2.0, E/e' > 14, dilated LA
  Explain what the grade means clinically, not just the individual numbers.

- LV WALL THICKNESS: IVSd or LVPWd > 1.1 cm suggests left ventricular
  hypertrophy (LVH). When both are elevated, note concentric hypertrophy.
  If only one wall is thick, note asymmetric hypertrophy.

- VALVULAR SEVERITY: When aortic valve area (AVA) is present, classify
  stenosis: mild (> 1.5 cm2), moderate (1.0-1.5 cm2), severe (< 1.0 cm2).
  Pair with peak velocity and mean gradient for concordance assessment.

- PULMONARY HYPERTENSION: RVSP > 35 mmHg suggests elevated pulmonary
  pressures. Pair with RV size and TR velocity for a complete picture.

"""

_CLINICAL_DOMAIN_KNOWLEDGE_LABS = """\
## Clinical Domain Knowledge — Laboratory Medicine

Apply these lab pattern interpretation rules:

- IRON DEFICIENCY PATTERN: When low Iron (FE) + low Ferritin (FERR) + high TIBC
  appear together, this constellation suggests iron deficiency. Do not interpret
  each value in isolation — synthesize them into a single clinical statement
  about iron stores.

- THYROID PATTERNS:
  - High TSH + low FT4 = primary hypothyroidism pattern
  - Low TSH + high FT4 = hyperthyroidism pattern
  - High TSH + normal FT4 = subclinical hypothyroidism
  - Low TSH + normal FT4 = subclinical hyperthyroidism
  Describe the pattern holistically, not as isolated lab values.

- CKD STAGING (based on eGFR):
  - Stage 1: eGFR >= 90 (normal function, but other kidney markers abnormal)
  - Stage 2: eGFR 60-89 (mildly decreased)
  - Stage 3a: eGFR 45-59 (mild-to-moderate)
  - Stage 3b: eGFR 30-44 (moderate-to-severe)
  - Stage 4: eGFR 15-29 (severe)
  - Stage 5: eGFR < 15 (kidney failure)
  When eGFR is abnormal, pair it with Creatinine and BUN for a kidney function
  narrative rather than listing each separately.

- DIABETES / GLUCOSE METABOLISM:
  - A1C 5.7-6.4% = prediabetic range
  - A1C >= 6.5% = diabetic range
  - A1C > 8% = poorly controlled diabetes
  When both Glucose and A1C are present, synthesize them together. A1C reflects
  3-month average; fasting glucose reflects acute status.

- LIVER PANEL: When multiple liver enzymes (AST, ALT, ALP, Bilirubin) are
  abnormal, describe the hepatic pattern rather than listing each value.
  AST/ALT ratio > 2 may suggest alcoholic liver disease.

- ANEMIA CLASSIFICATION: Use MCV to classify anemia type:
  - Low MCV (< 80) = microcytic (iron deficiency, thalassemia)
  - Normal MCV (80-100) = normocytic (chronic disease, acute blood loss)
  - High MCV (> 100) = macrocytic (B12/folate deficiency)
  Group RBC, HGB, HCT, and MCV together when interpreting.

- LIPID RISK: Synthesize total cholesterol, LDL, HDL, and triglycerides
  together. High LDL + low HDL is a more concerning pattern than either alone.
  Triglycerides > 500 is a separate risk for pancreatitis.

"""

_CLINICAL_DOMAIN_KNOWLEDGE_IMAGING = """\
## Clinical Domain Knowledge — Imaging

Apply these imaging-specific interpretation rules:

- ANATOMICAL ORGANIZATION: Group findings by anatomical region rather than
  listing them in report order. For chest CT: lungs first, then mediastinum,
  then bones/soft tissue. For abdominal imaging: solid organs, then hollow
  viscera, then vasculature, then musculoskeletal.

- INCIDENTAL FINDINGS: Common incidentalomas (simple renal cysts, small
  hepatic cysts, small pulmonary nodules < 6mm in low-risk patients) should
  be mentioned but contextualized as typically benign and common.

- LUNG NODULE RISK STRATIFICATION: Fleischner criteria context:
  - < 6mm in low-risk patient: typically no follow-up needed
  - 6-8mm: may warrant short-interval follow-up
  - > 8mm or growing: more concerning, warrants attention
  Do NOT specify exact follow-up schedules — that is the physician's decision.

- LESION SIZE CONTEXT: Always provide size context when discussing lesions.
  A 3mm lesion is very different from a 3cm lesion. Use analogies appropriate
  to the literacy level (e.g., "about the size of a grain of rice" vs.
  "approximately 3 millimeters").

"""

_CLINICAL_DOMAIN_KNOWLEDGE_EKG = """\
## Clinical Domain Knowledge — EKG/ECG

Apply this interpretation structure for EKG/ECG reports:

1. RHYTHM — Sinus rhythm vs. arrhythmia. If atrial fibrillation, note it
   prominently. If sinus rhythm, confirm it is normal.
2. RATE — Bradycardia (< 60), normal (60-100), tachycardia (> 100).
   Context: trained athletes may normally be bradycardic.
3. INTERVALS — PR interval (normal 0.12-0.20s), QRS duration (normal < 0.12s),
   QTc interval (normal < 440ms male, < 460ms female). Prolonged QTc is
   clinically significant.
4. AXIS — Normal, left axis deviation, right axis deviation. Brief context
   on what deviation may suggest.
5. ST/T WAVE CHANGES — ST elevation, ST depression, T-wave inversions.
   These are often the most clinically important findings.

"""

_CLINICAL_DOMAIN_KNOWLEDGE_PFT = """\
## Clinical Domain Knowledge — Pulmonary Function Tests

Apply this interpretation structure:

- OBSTRUCTIVE PATTERN: FEV1/FVC ratio < 0.70 (or below lower limit of normal).
  Classify severity by FEV1 % predicted: mild (>= 70%), moderate (50-69%),
  severe (35-49%), very severe (< 35%). Common in COPD, asthma.

- RESTRICTIVE PATTERN: FVC reduced with normal or elevated FEV1/FVC ratio.
  Confirm with total lung capacity (TLC) if available. Common in
  interstitial lung disease, chest wall disorders.

- MIXED PATTERN: Both obstructive and restrictive features present.
  FEV1/FVC ratio reduced AND FVC reduced disproportionately.

- DLCO: Reduced DLCO suggests impaired gas exchange (emphysema, interstitial
  disease, pulmonary vascular disease). Normal DLCO with obstruction suggests
  asthma over emphysema.

- BRONCHODILATOR RESPONSE: Significant response (>= 12% AND >= 200mL
  improvement in FEV1) suggests reversible obstruction (asthma pattern).

"""

# Default domain knowledge for backwards compatibility
_CLINICAL_DOMAIN_KNOWLEDGE = _CLINICAL_DOMAIN_KNOWLEDGE_CARDIAC


def _select_domain_knowledge(prompt_context: dict) -> str:
    """Select appropriate domain knowledge block based on test type/category."""
    test_type = prompt_context.get("test_type", "")
    category = prompt_context.get("category", "")
    interpretation_rules = prompt_context.get("interpretation_rules", "")

    # Select based on test type first, then category
    if test_type in ("lab_results", "blood_lab_results"):
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_LABS
    elif test_type in ("ekg", "ecg"):
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_EKG
    elif test_type == "pft":
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_PFT
    elif category == "lab":
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_LABS
    elif category in ("imaging_ct", "imaging_mri", "imaging_xray", "imaging_ultrasound"):
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_IMAGING
    elif category in ("cardiac", "vascular"):
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_CARDIAC
    elif category == "neurophysiology":
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_EKG  # Similar structure for EEG/EMG
    elif category == "pulmonary":
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_PFT
    else:
        domain = _CLINICAL_DOMAIN_KNOWLEDGE_CARDIAC  # Default

    # Append any handler-provided interpretation rules
    if interpretation_rules:
        domain = domain + f"\n{interpretation_rules}\n"

    return domain

_CLINICAL_CONTEXT_RULE = """\
## Clinical Context Integration

When clinical context is provided — either explicitly by the user OR
extracted from report sections such as INDICATION, REASON FOR TEST,
CLINICAL HISTORY, or CONCLUSION:
- You MUST connect at least one finding to the clinical context.
- Tie findings directly to the clinical context by explaining how the
  results relate to the patient's symptoms or reason for testing.
- Use phrasing like "Given that this test was ordered for [reason]..."
  or "These findings help explain your [symptom]..."
- Synthesize indication and conclusion data with the structured
  measurements to provide a clinically coherent interpretation.
- This applies to BOTH long-form and short comment outputs.
- If no clinical context was provided or extracted, skip this requirement.

"""

_INTERPRETATION_QUALITY_RULE = """\
## Interpretation Quality — Never Restate Without Meaning

CRITICAL: Never simply restate measurements without interpretation.
The patient can already see the numbers on their report. Your job is to
explain what those numbers MEAN for THEM.

BAD: "The left atrium measures 4.3 cm."
GOOD: "The left atrium is mildly enlarged at 4.3 cm (normal <4.0 cm), which
can occur with high blood pressure or heart valve issues."

BAD: "Your hemoglobin is 10.2 g/dL."
GOOD: "Your hemoglobin is mildly low at 10.2 (normal 12-16 for women), which
explains why you may feel more tired than usual."

Every measurement mentioned must include:
- What the value means (normal, abnormal, borderline)
- Clinical significance in plain language
- Relevance to the patient's context if provided

"""

_ZERO_EDIT_GOAL = """\
## OUTPUT QUALITY GOAL

The output must require ZERO editing before being sent to the patient.
It should sound exactly like the physician wrote it themselves. This means:
- Natural, conversational clinical voice — not robotic or template-like
- Consistent with the physician's prior approved outputs (liked/copied examples)
- Faithful to the teaching points and style preferences provided
- No placeholder language, no hedging about things the physician would state
  with confidence
- The physician should be able to copy this text and send it directly

"""


class PromptEngine:
    """Constructs system and user prompts for report explanation."""

    @staticmethod
    def _short_comment_sections(
        include_key_findings: bool, include_measurements: bool,
    ) -> str:
        n = 1
        lines: list[str] = []
        lines.append(
            f"{n}. Condensed clinical interpretation. Start with LV function, "
            f"then most significant findings by severity. Separate topics with "
            f"line breaks. 2-4 sentences. Mild regurgitation is NOT a key finding."
        )
        n += 1
        if include_key_findings:
            lines.append(
                f"{n}. Bullet list of clinically significant findings (key findings). "
                f"Severe/moderate first. Do NOT list mild regurgitation. 2-4 items."
            )
            n += 1
        if include_measurements:
            lines.append(
                f"{n}. Bullet list of key measurements with brief "
                f"interpretation. 2-4 items."
            )
            n += 1
        lines.append(
            f"{n}. Next steps — only if the user prompt includes explicit next steps. "
            f"List each as a bullet. If none provided, skip entirely. "
            f"Do NOT invent or suggest next steps on your own."
        )
        return "\n".join(lines)

    def build_system_prompt(
        self,
        literacy_level: LiteracyLevel,
        prompt_context: dict,
        tone_preference: int = 3,
        detail_preference: int = 3,
        physician_name: str | None = None,
        short_comment: bool = False,
        explanation_voice: str = "third_person",
        name_drop: bool = True,
        short_comment_char_limit: int | None = 1000,
        include_key_findings: bool = True,
        include_measurements: bool = True,
        patient_age: int | None = None,
        patient_gender: str | None = None,
        sms_summary: bool = False,
        sms_summary_char_limit: int = 300,
        high_anxiety_mode: bool = False,
        use_analogies: bool = True,
    ) -> str:
        """Build the system prompt with role, rules, and constraints.

        Args:
            high_anxiety_mode: If True, applies special guidance for anxious patients
                that emphasizes reassurance and avoids alarming language.
            use_analogies: If True, includes the analogy library for patient-friendly
                size and value comparisons.
        """
        specialty = prompt_context.get("specialty", "general medicine")

        if sms_summary:
            target = int(sms_summary_char_limit * 0.9)
            hard_limit = sms_summary_char_limit
            return (
                f"You are a clinical communicator writing an ultra-condensed "
                f"SMS-length summary of lab/test results for a patient. "
                f"Write as the physician or care team for a {specialty} practice.\n\n"
                f"## Rules\n"
                f"- 2-3 sentences MAX. Plain text only — no markdown, no bullets, "
                f"no headers, no emojis.\n"
                f"- Target {target} characters; NEVER exceed {hard_limit} characters.\n"
                f"- Lead with the most important finding. Mention key abnormalities.\n"
                f"- Use simple, patient-friendly language.\n"
                f"- NEVER suggest treatments, future testing, or hypothetical actions.\n"
                f"- ONLY use data from the report. Never invent findings.\n"
                f"- Use the provided status (normal, mildly_abnormal, etc.) — "
                f"do NOT reclassify.\n"
                f"- Do NOT mention the patient by name.\n"
                f"- Call the explain_report tool with your response.\n"
            )

        demographics_section = ""
        if patient_age is not None or patient_gender is not None:
            parts: list[str] = []
            guidance_parts: list[str] = []

            if patient_age is not None:
                parts.append(f"Age: {patient_age}")
                if patient_age >= 80:
                    guidance_parts.append(
                        "Very elderly patient (80+): Expect some age-related changes. "
                        "Mild LVH, diastolic dysfunction grade I, and mild valve "
                        "calcification are common. Focus on clinically actionable findings. "
                        "eGFR decline is expected; creatinine-based estimates may "
                        "underestimate true function due to reduced muscle mass."
                    )
                elif patient_age >= 65:
                    guidance_parts.append(
                        "Geriatric patient (65+): Mildly abnormal values may be more "
                        "clinically significant. Pay particular attention to renal function, "
                        "electrolytes, cardiac findings, and fall risk indicators. "
                        "Diastolic dysfunction grade I is common at this age."
                    )
                elif patient_age >= 40:
                    guidance_parts.append(
                        "Middle-aged adult: Cardiovascular risk factors become more relevant. "
                        "Lipid panel, A1C, and blood pressure context are important. "
                        "Mention if findings warrant lifestyle discussion."
                    )
                elif patient_age < 18:
                    guidance_parts.append(
                        "Pediatric patient: Adult reference ranges may not apply. "
                        "Note that some values differ significantly in children. "
                        "Heart rate and blood pressure norms are age-dependent."
                    )
                elif patient_age < 40:
                    guidance_parts.append(
                        "Young adult: Abnormal findings are less expected and may warrant "
                        "closer attention. Consider family history implications."
                    )

            if patient_gender is not None:
                parts.append(f"Sex: {patient_gender}")
                gender_lower = patient_gender.lower()
                if gender_lower in ("female", "f"):
                    guidance_parts.append(
                        "Female patient: Use female-specific reference ranges — "
                        "hemoglobin (12.0-16.0), hematocrit (35.5-44.9%), creatinine "
                        "(0.6-1.1), ferritin (12-150), LVEF (≥54%), LVIDd (3.8-5.2 cm). "
                        "Ferritin < 30 may indicate iron deficiency even if within range. "
                        "HDL target ≥ 50. QTc prolongation threshold: > 460 ms."
                    )
                elif gender_lower in ("male", "m"):
                    guidance_parts.append(
                        "Male patient: Use male-specific reference ranges — "
                        "hemoglobin (13.5-17.5), hematocrit (38.3-48.6%), creatinine "
                        "(0.7-1.3), ferritin (12-300), LVEF (≥52%), LVIDd (4.2-5.8 cm). "
                        "HDL target ≥ 40. QTc prolongation threshold: > 450 ms."
                    )

            # Combined age+sex guidance
            if patient_age is not None and patient_gender is not None:
                gender_lower = patient_gender.lower() if patient_gender else ""
                if gender_lower in ("female", "f") and patient_age >= 50:
                    guidance_parts.append(
                        "Post-menopausal female: Cardiovascular risk approaches male levels. "
                        "Bone density may be relevant if DEXA. Thyroid screening is common."
                    )
                elif gender_lower in ("male", "m") and patient_age >= 50:
                    guidance_parts.append(
                        "Male 50+: Prostate markers (if present) need age context. "
                        "Cardiovascular risk assessment is particularly important."
                    )

            guidance_text = "\n".join(f"- {g}" for g in guidance_parts) if guidance_parts else (
                "Use age-appropriate reference ranges and clinical context "
                "when interpreting results."
            )
            demographics_section = (
                f"## Patient Demographics\n"
                f"{', '.join(parts)}.\n\n"
                f"**Interpretation guidance based on demographics:**\n"
                f"{guidance_text}\n\n"
            )

        physician_section = ""
        if explanation_voice == "first_person":
            physician_section = (
                "## Physician Voice — First Person\n"
                "You ARE the physician. Write in first person. "
                "Use first-person language: \"I have reviewed your results\", "
                "\"In my assessment\". "
                "NEVER use third-person references like \"your doctor\" or "
                "\"your physician\".\n\n"
            )
        elif physician_name:
            attribution = ""
            if name_drop:
                attribution = (
                    f" Include at least one explicit attribution such as "
                    f"\"{physician_name} has reviewed your results\"."
                )
            physician_section = (
                f"## Physician Voice — Third Person (Care Team)\n"
                f"You are writing on behalf of the physician. "
                f"When referring to the physician, use \"{physician_name}\" "
                f"instead of generic phrases like \"your doctor\", \"your physician\", "
                f"or \"your healthcare provider\". For example, write "
                f"\"{physician_name} reviewed...\" instead of "
                f"\"Your doctor reviewed...\".{attribution}\n"
                f"The clinical interpretation voice and quality standard are "
                f"identical to first-person mode — the only difference is "
                f"attribution.\n\n"
            )

        if short_comment:
            if short_comment_char_limit is not None:
                target = int(short_comment_char_limit * 0.9)
                hard_limit = short_comment_char_limit
                length_constraint = (
                    f"- Target maximum {target} characters; NEVER exceed {hard_limit} characters.\n"
                    f"- Keep line width narrow (short lines, not long paragraphs).\n"
                )
                length_rule = (
                    f"10. Keep the entire overall_summary under {hard_limit} characters."
                )
            else:
                length_constraint = (
                    "- No strict character limit, but keep the comment concise and focused.\n"
                    "- Keep line width narrow (short lines, not long paragraphs).\n"
                )
                length_rule = (
                    "10. Keep the overall_summary concise but cover all relevant findings."
                )

            return (
                f"You are a clinical communicator writing a condensed "
                f"results comment to a patient. Write as the physician or care team "
                f"for a {specialty} practice.\n\n"
                f"{demographics_section}"
                f"## Rules\n"
                f"- Interpret findings — explain what they MEAN, don't recite values.\n"
                f"- NEVER suggest treatments, future testing, or hypothetical actions.\n"
                f"- Use softened language for abnormal findings: \"warrants discussion\", "
                f"\"worth mentioning\", \"something to discuss\". Avoid \"needs attention\".\n"
                f"- ONLY use data from the report. Never invent findings.\n"
                f"- Use the provided status (normal, mildly_abnormal, etc.) — do NOT reclassify.\n"
                f"- Do NOT mention the patient by name.\n"
                f"- If clinical context is provided, connect findings to it.\n\n"
                f"{physician_section}"
                f"## Output Constraints\n"
                f"{length_constraint}"
                f"- Plain text ONLY — no markdown, no emojis, no rich text.\n\n"
                f"## Formatting\n"
                f"- Do NOT include any titles or section headers. No ALL-CAPS headings.\n"
                f"- Separate sections with one blank line only.\n"
                f"- Bullet items: \"- \" (hyphen space).\n\n"
                f"## Required Sections\n"
                f"{self._short_comment_sections(include_key_findings, include_measurements)}\n"
                f"## Literacy: {_LITERACY_DESCRIPTIONS[literacy_level]}\n\n"
                f"{length_rule}"
            )

        literacy_desc = _LITERACY_DESCRIPTIONS[literacy_level]
        guidelines = prompt_context.get("guidelines", "standard clinical guidelines")
        explanation_style = prompt_context.get("explanation_style", "")
        tone = prompt_context.get("tone", "")
        test_type_hint = prompt_context.get("test_type_hint", "")

        tone_section = f"## Template Tone\n{tone}\n\n" if tone else ""
        test_type_hint_section = (
            f"## Report Type\n"
            f"The user describes this report as: \"{test_type_hint}\". "
            f"Use this as context when interpreting the report. "
            f"Extract and explain relevant measurements, findings, and "
            f"conclusions based on this report type.\n\n"
        ) if test_type_hint else ""

        # Override tone to maximum reassuring if high anxiety mode is active
        effective_tone = 5 if high_anxiety_mode else tone_preference
        tone_pref = _TONE_DESCRIPTIONS.get(effective_tone, _TONE_DESCRIPTIONS[3])
        detail_pref = _DETAIL_DESCRIPTIONS.get(detail_preference, _DETAIL_DESCRIPTIONS[3])

        style_section = (
            f"## Explanation Style\n{explanation_style}\n\n" if explanation_style else ""
        )

        # Include high anxiety mode guidance if active
        anxiety_section = _HIGH_ANXIETY_MODE if high_anxiety_mode else ""

        # Include analogy library if enabled
        analogy_section = _ANALOGY_LIBRARY if use_analogies else ""

        return (
            f"{_PHYSICIAN_IDENTITY.format(specialty=specialty)}"
            f"{demographics_section}"
            f"{test_type_hint_section}"
            f"{_CLINICAL_VOICE_RULE.format(specialty=specialty)}"
            f"{_NO_RECOMMENDATIONS_RULE}"
            f"{_CLINICAL_CONTEXT_RULE}"
            f"{_INTERPRETATION_QUALITY_RULE}"
            f"{_select_domain_knowledge(prompt_context)}"
            f"{_INTERPRETATION_STRUCTURE}"
            f"{anxiety_section}"
            f"{analogy_section}"
            f"## Literacy Level\n{literacy_desc}\n\n"
            f"## Clinical Guidelines\n"
            f"Base your interpretations on: {guidelines}\n\n"
            f"{style_section}"
            f"{tone_section}"
            f"## Tone Preference\n{tone_pref}\n\n"
            f"## Detail Level\n{detail_pref}\n\n"
            f"{physician_section}"
            f"{_TONE_RULES}"
            f"{_ZERO_EDIT_GOAL}"
            f"{_SAFETY_RULES}"
            f"## Validation Rule\n"
            f"If the output reads like a neutral summary, report recap, or "
            f"contains treatment suggestions or hypothetical next steps, "
            f"regenerate.\n"
        )

    def build_user_prompt(
        self,
        parsed_report: ParsedReport,
        reference_ranges: dict,
        glossary: dict[str, str],
        scrubbed_text: str,
        clinical_context: str | None = None,
        template_instructions: str | None = None,
        closing_text: str | None = None,
        refinement_instruction: str | None = None,
        liked_examples: list[dict] | None = None,
        next_steps: list[str] | None = None,
        teaching_points: list[dict] | None = None,
        short_comment: bool = False,
        prior_results: list[dict] | None = None,
        recent_edits: list[dict] | None = None,
        patient_age: int | None = None,
        patient_gender: str | None = None,
        quick_reasons: list[str] | None = None,
    ) -> str:
        """Build the user prompt with report data, ranges, and glossary.

        When *short_comment* is True the raw report text is omitted (the
        structured parsed data is sufficient) and the glossary is trimmed to
        keep total token count well under typical rate limits.

        Args:
            prior_results: Optional list of prior test results for trend comparison.
                Each dict has 'date' (ISO date str) and 'measurements' (list of
                {abbreviation, value, unit, status}).
            recent_edits: Optional list of structural metadata from recent doctor edits.
                Each dict has 'length_change_pct', 'paragraph_change', 'shorter', 'longer'.
        """
        sections: list[str] = []

        # 1. Report text (scrubbed) — normally skipped because the structured
        #    parsed data is sufficient. However, for unknown test types (no
        #    handler), the parsed report is empty, so include the raw text so
        #    the LLM can interpret the report directly.
        has_structured_data = bool(
            parsed_report.measurements or parsed_report.sections or parsed_report.findings
        )
        if not has_structured_data and scrubbed_text:
            sections.append("## Full Report Text (PHI Scrubbed)")
            sections.append(scrubbed_text)

        # 1b. Clinical context (if provided, or extracted from report indication)
        effective_context = clinical_context
        if not effective_context and scrubbed_text:
            # Try to extract indication from the report itself
            indication = _extract_indication_from_report(scrubbed_text)
            if indication:
                effective_context = f"Indication for test: {indication}"

        if effective_context:
            sections.append("\n## Clinical Context")
            sections.append(f"{effective_context}")
            sections.append(
                "\n**Instructions for using clinical context:**\n"
                "- This may be a full office note containing HPI, PMH, and medications — extract all relevant information\n"
                "- Identify the chief complaint or reason for this test\n"
                "- Prioritize findings relevant to the clinical question\n"
                "- Specifically address whether results support, argue against, or are inconclusive for the suspected condition\n"
                "- Note findings particularly relevant to the patient's history or medications\n"
                "- If medications affect interpretation (e.g., beta blockers → controlled heart rate, diuretics → electrolytes), mention this"
            )

            # Extract and add medication-specific guidance
            detected_meds = _extract_medications_from_context(effective_context)
            if detected_meds:
                med_guidance = _build_medication_guidance(detected_meds)
                if med_guidance:
                    sections.append(med_guidance)

            # Extract and add chronic condition guidance
            detected_conditions = _extract_conditions_from_context(effective_context)
            if detected_conditions:
                condition_guidance = _build_condition_guidance(detected_conditions)
                if condition_guidance:
                    sections.append(condition_guidance)

            # Extract chief complaint and symptoms for correlation
            chief_complaint = _extract_chief_complaint(effective_context)
            detected_symptoms = _extract_symptoms(effective_context)
            if chief_complaint or detected_symptoms:
                cc_guidance = _build_chief_complaint_guidance(chief_complaint, detected_symptoms)
                if cc_guidance:
                    sections.append(cc_guidance)

            # Detect relevant lab patterns
            detected_patterns = _detect_lab_patterns(
                effective_context,
                parsed_report.measurements if parsed_report else [],
            )
            if detected_patterns:
                pattern_guidance = _build_lab_pattern_guidance(detected_patterns)
                if pattern_guidance:
                    sections.append(pattern_guidance)

        # 1c. Quick reasons (structured clinical indicators from settings)
        if quick_reasons:
            sections.append("\n## Primary Clinical Indications")
            sections.append(
                "The physician selected the following primary reasons for this test. "
                "These are the KEY clinical questions that MUST be addressed in the interpretation:\n"
            )
            for reason in quick_reasons:
                sections.append(f"- **{reason}**")
            sections.append(
                "\n**Priority:** Address each of these indications explicitly. "
                "State whether findings support, argue against, or are inconclusive for each concern. "
                "If a finding is particularly relevant to one of these indications, highlight that connection."
            )

        # 1d. Patient demographics (for interpretation context)
        if patient_age is not None or patient_gender is not None:
            demo_parts: list[str] = []
            if patient_age is not None:
                demo_parts.append(f"Age: {patient_age}")
            if patient_gender is not None:
                demo_parts.append(f"Sex: {patient_gender}")
            sections.append("\n## Patient Demographics")
            sections.append(", ".join(demo_parts))
            sections.append(
                "Use these demographics to apply appropriate reference ranges and "
                "tailor the interpretation to this patient's age and sex."
            )

        # 1d. Next steps to include (if provided)
        if next_steps and any(s != "No comment" for s in next_steps):
            sections.append("\n## Specific Next Steps to Include")
            sections.append(
                "Include ONLY these exact next steps as stated. Do not expand, "
                "embellish, or add additional recommendations:"
            )
            for step in next_steps:
                if step != "No comment":
                    sections.append(f"- {step}")

        # 1e. Template instructions (if provided)
        if template_instructions:
            sections.append("\n## Structure Instructions")
            sections.append(template_instructions)
        if closing_text:
            sections.append("\n## Closing Text")
            sections.append(
                f"End the overall_summary with the following closing text:\n{closing_text}"
            )

        # 1f. Preferred output style from liked/copied examples
        # NOTE: We only inject structural metadata (length, paragraph count, etc.)
        # — never prior clinical content — to avoid priming the LLM with
        # diagnoses from unrelated patients.
        if liked_examples:
            sections.append("\n## Preferred Output Style")
            sections.append(
                "The physician has approved outputs with the following structural characteristics.\n"
                "Match this structure, length, and level of detail using ONLY the data\n"
                "from the current report."
            )

            # Collect stylistic patterns from all examples
            all_openings: list[str] = []
            all_transitions: list[str] = []
            all_closings: list[str] = []
            all_softening: list[str] = []

            for idx, example in enumerate(liked_examples, 1):
                sections.append(f"\n### Style Reference {idx}")
                sections.append(
                    f"- Summary length: ~{example.get('approx_char_length', 'unknown')} characters"
                )
                sections.append(
                    f"- Paragraphs: {example.get('paragraph_count', 'unknown')}"
                )
                sections.append(
                    f"- Approximate sentences: {example.get('approx_sentence_count', 'unknown')}"
                )
                num_findings = example.get("num_key_findings", 0)
                sections.append(f"- Number of key findings reported: {num_findings}")

                # Collect stylistic patterns
                patterns = example.get("stylistic_patterns", {})
                if patterns:
                    all_openings.extend(patterns.get("openings", []))
                    all_transitions.extend(patterns.get("transitions", []))
                    all_closings.extend(patterns.get("closings", []))
                    all_softening.extend(patterns.get("softening", []))

            # Add learned terminology patterns if any were found
            if any([all_openings, all_transitions, all_closings, all_softening]):
                sections.append("\n### Practice Terminology Preferences")
                sections.append(
                    "The physician prefers these communication patterns. "
                    "Use similar phrasing where appropriate:"
                )
                if all_openings:
                    unique = list(dict.fromkeys(all_openings))[:3]
                    quoted = [f'"{p}"' for p in unique]
                    sections.append(f"- Opening phrases: {', '.join(quoted)}")
                if all_transitions:
                    unique = list(dict.fromkeys(all_transitions))[:4]
                    quoted = [f'"{p}"' for p in unique]
                    sections.append(f"- Transition phrases: {', '.join(quoted)}")
                if all_softening:
                    unique = list(dict.fromkeys(all_softening))[:3]
                    quoted = [f'"{p}"' for p in unique]
                    sections.append(f"- Softening language: {', '.join(quoted)}")
                if all_closings:
                    unique = list(dict.fromkeys(all_closings))[:2]
                    quoted = [f'"{p}"' for p in unique]
                    sections.append(f"- Closing phrases: {', '.join(quoted)}")

        # 1g. Teaching points (personalized instructions)
        if teaching_points:
            sections.append("\n## Teaching Points")
            sections.append(
                "The physician has provided the following personalized instructions.\n"
                "These reflect their clinical style and preferences. Follow them closely\n"
                "so the output matches how this physician communicates:"
            )
            for tp in teaching_points:
                source = tp.get("source", "own")
                if source == "own":
                    sections.append(f"- {tp['text']}")
                else:
                    sections.append(f"- [From {source}] {tp['text']}")

        # 1h. Doctor editing patterns (learned from recent edits)
        if recent_edits and not short_comment:
            # Analyze patterns in the edits
            shorter_count = sum(1 for e in recent_edits if e.get("shorter"))
            longer_count = sum(1 for e in recent_edits if e.get("longer"))
            avg_length_change = sum(e.get("length_change_pct", 0) for e in recent_edits) / len(recent_edits)
            avg_para_change = sum(e.get("paragraph_change", 0) for e in recent_edits) / len(recent_edits)

            guidance: list[str] = []
            if shorter_count > longer_count and avg_length_change < -10:
                guidance.append(
                    f"The physician tends to shorten output by ~{abs(int(avg_length_change))}%. "
                    f"Be more concise than the default output."
                )
            elif longer_count > shorter_count and avg_length_change > 10:
                guidance.append(
                    f"The physician tends to expand output by ~{int(avg_length_change)}%. "
                    f"Provide more detail than the default output."
                )

            if avg_para_change < -0.5:
                guidance.append(
                    "The physician prefers fewer paragraphs. Combine related points."
                )
            elif avg_para_change > 0.5:
                guidance.append(
                    "The physician prefers more paragraphs for separation. "
                    "Break up content into shorter paragraphs."
                )

            if guidance:
                sections.append("\n## Doctor Editing Patterns")
                sections.append(
                    "Based on the physician's recent edits, adjust the output style:"
                )
                for g in guidance:
                    sections.append(f"- {g}")

        # 2. Parsed measurements with reference ranges
        sections.append("\n## Parsed Measurements")
        critical_values_found: list[str] = []
        if parsed_report.measurements:
            for m in parsed_report.measurements:
                ref_info = ""
                if m.abbreviation in reference_ranges:
                    rr = reference_ranges[m.abbreviation]
                    parts: list[str] = []
                    if rr.get("normal_min") is not None:
                        parts.append(f"min={rr['normal_min']}")
                    if rr.get("normal_max") is not None:
                        parts.append(f"max={rr['normal_max']}")
                    if parts:
                        ref_info = (
                            f" | Normal range: {', '.join(parts)} "
                            f"{rr.get('unit', '')}"
                        )

                prior_info = ""
                if m.prior_values:
                    prior_parts = [
                        f"{pv.time_label}: {pv.value} {m.unit}"
                        for pv in m.prior_values
                    ]
                    prior_info = " | " + " | ".join(prior_parts)

                # Flag critical/panic values prominently
                critical_flag = ""
                if m.status.value == "critical":
                    critical_flag = " *** CRITICAL/PANIC VALUE ***"
                    critical_values_found.append(f"{m.name} ({m.abbreviation}): {m.value} {m.unit}")

                sections.append(
                    f"- {m.name} ({m.abbreviation}): {m.value} {m.unit} "
                    f"[status: {m.status.value}]{critical_flag}{prior_info}{ref_info}"
                )

        # Add critical value warning if any found
        if critical_values_found:
            sections.insert(
                sections.index("\n## Parsed Measurements") + 1,
                "\n### CRITICAL VALUES DETECTED\n"
                "The following values are at CRITICAL/PANIC levels. "
                "These require immediate clinical attention and must be prominently "
                "addressed in your interpretation. Explain the clinical significance "
                "and urgency:\n" + "\n".join(f"- {cv}" for cv in critical_values_found)
            )
        else:
            sections.append(
                "No measurements were pre-extracted by the parser. "
                "You MUST identify and interpret all clinically relevant "
                "measurements, values, and findings directly from the report text above. "
                "Extract key values (e.g., percentages, dimensions, velocities, pressures, "
                "lab values) and explain what they mean for the patient."
            )

        # 2b. Prior results for trend comparison (if available)
        if prior_results and not short_comment:
            sections.append("\n## Prior Results (for trend comparison)")
            sections.append(
                "When a current measurement has a corresponding prior value, "
                "briefly note the trend (stable, improved, worsened). "
                "Do not over-interpret small fluctuations within normal range."
            )
            for prior in prior_results:
                date = prior.get("date", "Unknown date")
                measurements = prior.get("measurements", [])
                if measurements:
                    sections.append(f"\n### {date}")
                    for m in measurements[:10]:  # Limit to avoid token bloat
                        abbrev = m.get("abbreviation", "")
                        value = m.get("value", "")
                        unit = m.get("unit", "")
                        status = m.get("status", "")
                        sections.append(f"- {abbrev}: {value} {unit} [{status}]")

        # 3. Findings
        if parsed_report.findings:
            sections.append("\n## Report Findings/Conclusions")
            for f in parsed_report.findings:
                sections.append(f"- {f}")

        # 4. Sections — include clinical context sections (indication, reason,
        #    findings, conclusions) to give the LLM richer context for interpretation
        if parsed_report.sections:
            for s in parsed_report.sections:
                name_lower = s.name.lower()
                if any(kw in name_lower for kw in (
                    "finding", "conclusion", "impression",
                    "indication", "reason", "clinical history",
                    "history", "referral",
                )):
                    sections.append(f"\n## {s.name}")
                    sections.append(s.content)

        # 5. Glossary — only include terms referenced in measurements/findings
        #    for short comment; full glossary for long-form
        if short_comment:
            # Build set of abbreviations and finding keywords for filtering
            relevant_terms: set[str] = set()
            for m in (parsed_report.measurements or []):
                relevant_terms.add(m.abbreviation.upper())
                for word in m.name.split():
                    if len(word) > 3:
                        relevant_terms.add(word.upper())
            filtered_glossary = {
                term: defn for term, defn in glossary.items()
                if term.upper() in relevant_terms
            }
            if filtered_glossary:
                sections.append(
                    "\n## Glossary (use these definitions when explaining terms)"
                )
                for term, definition in filtered_glossary.items():
                    sections.append(f"- **{term}**: {definition}")
        else:
            sections.append(
                "\n## Glossary (use these definitions when explaining terms)"
            )
            for term, definition in glossary.items():
                sections.append(f"- **{term}**: {definition}")

        # 6. Refinement instruction (if provided)
        if refinement_instruction:
            sections.append("\n## Refinement Instruction")
            sections.append(refinement_instruction)

        # 7. Instructions
        sections.append(
            "\n## Instructions\n"
            "Using ONLY the data above, write a clinical interpretation as "
            "the physician, ready to send directly to the patient. Call the "
            "explain_report tool with your response. Include all measurements "
            "listed above. Do not add measurements, findings, or treatment "
            "recommendations not present in the data."
        )

        return "\n".join(sections)
