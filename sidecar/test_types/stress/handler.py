from __future__ import annotations

import re

from api.models import ExtractionResult
from api.analysis_models import ParsedMeasurement, ParsedReport, ReportSection
from test_types.base import BaseTestType
from .glossary import STRESS_GLOSSARY
from .measurements import extract_measurements
from .reference_ranges import REFERENCE_RANGES, classify_measurement

# Lazy import to avoid circular dependency at module level
_pet_extractor = None
_pet_ref_ranges = None
_pet_glossary = None
_pet_get_cfc = None


def _load_pet():
    global _pet_extractor, _pet_ref_ranges, _pet_glossary, _pet_get_cfc
    if _pet_extractor is None:
        from test_types.extractors.cardiac_pet import (
            extract_cardiac_pet_measurements,
            CARDIAC_PET_REFERENCE_RANGES,
            CARDIAC_PET_GLOSSARY,
            get_cfc,
        )
        _pet_extractor = extract_cardiac_pet_measurements
        _pet_ref_ranges = CARDIAC_PET_REFERENCE_RANGES
        _pet_glossary = CARDIAC_PET_GLOSSARY
        _pet_get_cfc = get_cfc


# ---------------------------------------------------------------------------
# Subtype definitions
# ---------------------------------------------------------------------------
_SUBTYPES = {
    # (is_pharma, modality) -> (type_id, display_name)
    (False, "ecg"):   ("exercise_treadmill_test", "Exercise Treadmill Test"),
    (True,  "ecg"):   ("pharma_spect_stress", "Pharmacologic SPECT Nuclear Stress"),  # pharma without imaging → default to SPECT
    (True,  "spect"): ("pharma_spect_stress", "Pharmacologic SPECT Nuclear Stress"),
    (False, "spect"): ("exercise_spect_stress", "Exercise SPECT Nuclear Stress"),
    (True,  "pet"):   ("pharma_pet_stress", "Pharmacologic PET/PET-CT Stress"),
    (False, "pet"):   ("exercise_pet_stress", "Exercise PET/PET-CT Stress"),
    (False, "echo"):  ("exercise_stress_echo", "Exercise Stress Echocardiogram"),
    (True,  "echo"):  ("pharma_stress_echo", "Pharmacologic Stress Echocardiogram"),
}

# Pharmacologic agents (vasodilators + dobutamine)
_PHARMA_AGENTS = [
    "lexiscan", "regadenoson", "adenosine", "dipyridamole",
    "persantine", "dobutamine",
    "pharmacologic stress test", "pharmacological stress test",
    "pharmacologic stress was", "pharmacological stress was",
    "pharmacologic stress protocol",
]

# Modality keyword sets (checked in priority order: PET > SPECT > Echo > ECG)
_PET_KEYWORDS = [
    "pet/ct", "pet-ct", "pet ct", "rb-82", "rubidium",
    "n-13", "ammonia pet", "positron emission", "cardiac pet",
    "cardiac positron emission tomography", "positron emission tomography",
    "myocardial blood flow", "mbf", "coronary flow reserve", "cfr",
    "positron", "n-13 ammonia",
]

_SPECT_KEYWORDS = [
    "spect", "sestamibi", "technetium", "tc-99m", "myoview",
    "cardiolite", "thallium", "nuclear stress", "myocardial perfusion imaging",
    "nuclear cardiology", "mpi",
]

_ECHO_KEYWORDS = [
    "stress echo", "stress echocardiogram", "dobutamine echo",
    "dobutamine stress echo", "exercise echo", "bicycle stress",
    "wall motion at stress", "exercise echocardiogram",
    "treadmill echo", "dobutamine echocardiogram",
]

# ---------------------------------------------------------------------------
# PET prompt rule constants — V1 (current) and V2 (enhanced)
# ---------------------------------------------------------------------------

_PET_PHARMA_STYLE = (
    "This is a pharmacologic cardiac PET/PET-CT perfusion study. "
    "Follow the DECISION TREE in the interpretation rules strictly.\n"
    "At Clinical literacy: structured impression format. Use CFC "
    "category names directly (normal, mildly reduced, etc.).\n"
    "At Grade 12 literacy: explain CFC in context with brief definitions. "
    "Explain what coronary flow capacity means before stating the result.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library for "
    "CFC, MBF, and CFR. Use very simple language.\n"
    "ALWAYS: ischemia first, EF secondary, don't celebrate normal EF.\n"
    "IMPORTANT pharmacological stress rules:\n"
    "- Do NOT mention heart rate response to stress AT ALL.\n"
    "- Do NOT comment on target heart rate, predicted maximum "
    "heart rate, or % of max predicted heart rate.\n"
    "- Do NOT state that the heart rate response may limit "
    "interpretation of the EKG stress test."
)

_PET_PHARMA_RULES = (
    "CARDIAC PET/PET-CT INTERPRETATION — DECISION TREE:\n\n"
    "STEP 1 — ISCHEMIA CHECK (always first):\n"
    "  - Examine SSS, SDS, and perfusion images.\n"
    "  - SSS >= 4 OR SDS >= 2 → ischemia likely present. State location, extent, severity.\n"
    "  - SSS 0-3 AND SDS 0-1 → no significant ischemia. State this clearly.\n"
    "  - Fixed defects (SRS elevated, SDS low) → prior infarct/scar, not active ischemia.\n\n"
    "STEP 2 — FLOW ANALYSIS (after ischemia assessment):\n"
    "  - Report MFR/CFR (global and per-territory if available).\n"
    "  - Report stress MBF (global and per-territory if available).\n"
    "  - CFC (coronary flow capacity) — the composite of stress MBF + CFR.\n"
    "    If a pre-computed CFC grade is provided above, USE IT directly.\n"
    "    Do NOT re-classify CFC from raw MBF/CFR values — the pre-computed\n"
    "    grade is authoritative (extracted from the report or computed using\n"
    "    standardized thresholds). The classification framework for reference:\n"
    "    * Normal: stress MBF >= 2.0 AND CFR >= 2.0\n"
    "    * Mildly reduced: stress MBF 1.5-2.0 OR CFR 1.5-2.0\n"
    "    * Moderately reduced: stress MBF 1.0-1.5 OR CFR 1.0-1.5\n"
    "    * Severely reduced: stress MBF < 1.0 OR CFR < 1.0\n\n"
    "STEP 3 — INTEGRATION & RISK CATEGORIZATION:\n"
    "  a) Ischemia present + reduced CFC in same territory → epicardial CAD.\n"
    "     Do NOT label as microvascular disease.\n"
    "  b) No ischemia + globally reduced CFC (>= 2 territories) → may indicate\n"
    "     microvascular dysfunction. Use cautious language: 'may suggest',\n"
    "     'could be consistent with'. Do NOT diagnose definitively.\n"
    "  c) No ischemia + normal CFC → reassuring. State clearly.\n"
    "  d) No ischemia + isolated mildly reduced CFC in 1 territory → note\n"
    "     briefly without alarm. May be normal variant or technical.\n\n"
    "STEP 4 — SECONDARY FINDINGS:\n"
    "  - LVEF (mention after perfusion/flow, do NOT lead with it)\n"
    "  - TID ratio (if elevated, note as supporting evidence for ischemia)\n"
    "  - Wall motion abnormalities at stress (stunning = ischemia marker)\n\n"
    "GUARDRAILS:\n"
    "  - Do NOT label microvascular disease when perfusion defects are present\n"
    "  - Low MFR/CFR + perfusion defect = epicardial disease, not microvascular\n"
    "  - Globally reduced MFR/CFR without focal defects → 'may suggest' microvascular\n"
    "  - Do NOT over-alarm borderline values (mildly reduced CFC without other findings)\n"
    "  - Do NOT say 'we may need to make adjustments based on mild reductions'\n"
    "  - Pharmacologic stress: Do NOT mention heart rate response AT ALL\n"
    "  - LVEF above normal range: Do NOT flag, caution, or comment on an EF "
    "that is above the upper limit of normal. An EF of 70-80% is not clinically "
    "concerning on a stress PET and should simply be stated as normal. Do NOT "
    "use terms like 'above normal', 'supranormal', or 'hyperdynamic' for EF "
    "values in the 70-80% range. Just say the EF is normal.\n"
    "  - When CFC is mildly/minimally reduced diffusely (across multiple "
    "territories or globally), contextualize it: this is commonly seen "
    "with age, hypertension, diabetes, and other cardiac risk factors. "
    "Do NOT use vague phrases like 'something to be aware of' — instead "
    "explain WHY it's seen (risk factors, age) so the patient understands.\n"
    "  - Do NOT restate the clinical indications at the end of the explanation. "
    "The patient already knows why they had the test. Restating 'you came in "
    "with chest pain, high blood pressure...' adds no interpretive value. "
    "Instead, if findings correlate with a specific indication, weave that "
    "into the relevant finding (e.g., 'the reduced blood flow in this area "
    "could explain the chest pain you've been experiencing').\n\n"
    "ADMINISTRATIVE METADATA — DO NOT INCLUDE:\n"
    "  - Do NOT mention who interpreted/read/signed the study\n"
    "  - Do NOT mention the interpreting physician's name or signature\n"
    "  - Do NOT state whether prior studies are or are not available "
    "for comparison. If the report references a prior study, you may "
    "reference the comparison findings, but do NOT editorialize about "
    "the availability of prior studies"
)

_PET_EXERCISE_STYLE = (
    "This is an exercise cardiac PET/PET-CT perfusion study. "
    "Follow the DECISION TREE in the interpretation rules strictly.\n"
    "Also comment on exercise capacity (METs) and heart rate response.\n"
    "At Clinical literacy: structured impression format. Use CFC "
    "category names directly.\n"
    "At Grade 12 literacy: explain CFC in context with brief definitions.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library for "
    "CFC, MBF, and CFR. Use very simple language.\n"
    "ALWAYS: ischemia first, exercise capacity second, EF last."
)

_PET_EXERCISE_RULES = (
    "CARDIAC PET/PET-CT INTERPRETATION — DECISION TREE:\n\n"
    "STEP 1 — ISCHEMIA CHECK (always first):\n"
    "  - Examine SSS, SDS, and perfusion images.\n"
    "  - SSS >= 4 OR SDS >= 2 → ischemia likely present. State location, extent, severity.\n"
    "  - SSS 0-3 AND SDS 0-1 → no significant ischemia. State this clearly.\n"
    "  - Fixed defects (SRS elevated, SDS low) → prior infarct/scar, not active ischemia.\n\n"
    "STEP 2 — FLOW ANALYSIS (after ischemia assessment):\n"
    "  - Report MFR/CFR (global and per-territory if available).\n"
    "  - Report stress MBF (global and per-territory if available).\n"
    "  - CFC (coronary flow capacity) — the composite of stress MBF + CFR.\n"
    "    If a pre-computed CFC grade is provided above, USE IT directly.\n"
    "    Do NOT re-classify CFC from raw MBF/CFR values — the pre-computed\n"
    "    grade is authoritative (extracted from the report or computed using\n"
    "    standardized thresholds). The classification framework for reference:\n"
    "    * Normal: stress MBF >= 2.0 AND CFR >= 2.0\n"
    "    * Mildly reduced: stress MBF 1.5-2.0 OR CFR 1.5-2.0\n"
    "    * Moderately reduced: stress MBF 1.0-1.5 OR CFR 1.0-1.5\n"
    "    * Severely reduced: stress MBF < 1.0 OR CFR < 1.0\n\n"
    "STEP 3 — INTEGRATION & RISK CATEGORIZATION:\n"
    "  a) Ischemia present + reduced CFC in same territory → epicardial CAD.\n"
    "     Do NOT label as microvascular disease.\n"
    "  b) No ischemia + globally reduced CFC (>= 2 territories) → may indicate\n"
    "     microvascular dysfunction. Use cautious language: 'may suggest',\n"
    "     'could be consistent with'. Do NOT diagnose definitively.\n"
    "  c) No ischemia + normal CFC → reassuring. State clearly.\n"
    "  d) No ischemia + isolated mildly reduced CFC in 1 territory → note\n"
    "     briefly without alarm. May be normal variant or technical.\n\n"
    "STEP 4 — SECONDARY FINDINGS:\n"
    "  - Exercise capacity (METs) and heart rate response (% of max predicted)\n"
    "  - LVEF (mention after perfusion/flow, do NOT lead with it)\n"
    "  - TID ratio (if elevated, note as supporting evidence for ischemia)\n"
    "  - Wall motion abnormalities at stress (stunning = ischemia marker)\n\n"
    "GUARDRAILS:\n"
    "  - Do NOT label microvascular disease when perfusion defects are present\n"
    "  - Low MFR/CFR + perfusion defect = epicardial disease, not microvascular\n"
    "  - Globally reduced MFR/CFR without focal defects → 'may suggest' microvascular\n"
    "  - Do NOT over-alarm borderline values (mildly reduced CFC without other findings)\n"
    "  - Do NOT say 'we may need to make adjustments based on mild reductions'\n"
    "  - LVEF above normal range: Do NOT flag, caution, or comment on an EF "
    "that is above the upper limit of normal. An EF of 70-80% is not clinically "
    "concerning on a stress PET and should simply be stated as normal. Do NOT "
    "use terms like 'above normal', 'supranormal', or 'hyperdynamic' for EF "
    "values in the 70-80% range. Just say the EF is normal.\n"
    "  - When CFC is mildly/minimally reduced diffusely (across multiple "
    "territories or globally), contextualize it: this is commonly seen "
    "with age, hypertension, diabetes, and other cardiac risk factors. "
    "Do NOT use vague phrases like 'something to be aware of' — instead "
    "explain WHY it's seen (risk factors, age) so the patient understands.\n"
    "  - Do NOT restate the clinical indications at the end of the explanation. "
    "The patient already knows why they had the test. Restating 'you came in "
    "with chest pain, high blood pressure...' adds no interpretive value. "
    "Instead, if findings correlate with a specific indication, weave that "
    "into the relevant finding (e.g., 'the reduced blood flow in this area "
    "could explain the chest pain you've been experiencing').\n\n"
    "ADMINISTRATIVE METADATA — DO NOT INCLUDE:\n"
    "  - Do NOT mention who interpreted/read/signed the study\n"
    "  - Do NOT mention the interpreting physician's name or signature\n"
    "  - Do NOT state whether prior studies are or are not available "
    "for comparison. If the report references a prior study, you may "
    "reference the comparison findings, but do NOT editorialize about "
    "the availability of prior studies"
)


# ---------------------------------------------------------------------------
# Stress echo prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_STRESS_ECHO_EXERCISE_STYLE = (
    "This is an exercise stress echocardiogram.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format.\n"
    "At Grade 12 literacy: explain what each finding means in context.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Wall motion is the headline finding, not EF."
)

_STRESS_ECHO_EXERCISE_RULES = (
    "EXERCISE STRESS ECHOCARDIOGRAM — DECISION TREE:\n\n"
    "STEP 1 — WALL MOTION (primary focus):\n"
    "  - Compare rest vs peak stress wall motion segment by segment.\n"
    "  - New wall motion abnormalities at peak stress = inducible ischemia.\n"
    "    State location and map to coronary territory (anterior/septal -> LAD,\n"
    "    inferior -> RCA, lateral -> LCx).\n"
    "  - No new abnormalities = no inducible ischemia. State clearly.\n"
    "  - Fixed wall motion abnormalities (present at rest AND stress) =\n"
    "    prior infarct/scar, not active ischemia.\n\n"
    "STEP 2 — EF RESPONSE:\n"
    "  - Normal response: EF increases with exercise (>=5% increase typical).\n"
    "  - Failure to augment (EF unchanged or drops): concerning for\n"
    "    ischemia or cardiomyopathy, even without focal WMA.\n"
    "  - Do NOT lead with EF. Wall motion is the primary finding.\n\n"
    "STEP 3 — EXERCISE CAPACITY & HEMODYNAMICS:\n"
    "  - METs achieved: <5 METs = poor capacity, 5-7 moderate, 7-10 good,\n"
    "    >10 excellent.\n"
    "  - Heart rate response: achieved >=85% of max predicted (220-age) =\n"
    "    adequate test. Below 85% may limit sensitivity.\n"
    "  - Blood pressure response: normal rise with exercise. Hypotensive\n"
    "    response (drop in SBP) is an ominous sign.\n\n"
    "STEP 4 — VALVULAR CHANGES:\n"
    "  - Dynamic MR: mitral regurgitation that worsens with exercise is\n"
    "    significant — may explain exertional dyspnea.\n"
    "  - Gradient changes: aortic stenosis gradients at peak exercise\n"
    "    provide functional assessment.\n\n"
    "STEP 5 — SECONDARY FINDINGS:\n"
    "  - Rest echo findings (chamber sizes, diastolic function, baseline EF).\n"
    "  - ECG changes during exercise (ST depression — though echo\n"
    "    findings take precedence over ECG in stress echo).\n\n"
    "GUARDRAILS:\n"
    "  - LVEF above normal range: Do NOT flag. An EF of 65-75% is normal\n"
    "    on stress echo.\n"
    "  - Normal stress echo: Do NOT pad. 'No inducible ischemia, normal\n"
    "    exercise capacity, and normal heart function' is sufficient.\n"
    "  - Do NOT restate indications or mention who read the study.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)

_STRESS_ECHO_PHARMA_STYLE = (
    "This is a pharmacologic (dobutamine) stress echocardiogram.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format.\n"
    "At Grade 12 literacy: explain what each finding means in context.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Wall motion is the headline finding, not EF.\n"
    "IMPORTANT pharmacological stress rules:\n"
    "- Do NOT mention heart rate response to stress AT ALL.\n"
    "- Do NOT comment on target heart rate, predicted maximum "
    "heart rate, or % of max predicted heart rate.\n"
    "- Do NOT state that the heart rate response may limit "
    "interpretation of the EKG stress test."
)

_STRESS_ECHO_PHARMA_RULES = (
    "DOBUTAMINE STRESS ECHOCARDIOGRAM — DECISION TREE:\n\n"
    "STEP 1 — WALL MOTION (primary focus):\n"
    "  - Compare rest vs peak stress wall motion segment by segment.\n"
    "  - New wall motion abnormalities at peak stress = inducible ischemia.\n"
    "    State location and map to coronary territory (anterior/septal -> LAD,\n"
    "    inferior -> RCA, lateral -> LCx).\n"
    "  - No new abnormalities = no inducible ischemia. State clearly.\n"
    "  - Fixed wall motion abnormalities (present at rest AND stress) =\n"
    "    prior infarct/scar, not active ischemia.\n\n"
    "STEP 2 — EF RESPONSE:\n"
    "  - Normal response: EF increases with dobutamine (>=5% increase typical).\n"
    "  - Failure to augment (EF unchanged or drops): concerning for\n"
    "    ischemia or cardiomyopathy, even without focal WMA.\n"
    "  - Do NOT lead with EF. Wall motion is the primary finding.\n\n"
    "STEP 3 — VIABILITY ASSESSMENT:\n"
    "  - Biphasic response: improvement at low dose dobutamine, worsening at\n"
    "    high dose = viable but ischemic myocardium. This is a key finding\n"
    "    that may indicate benefit from revascularization.\n"
    "  - Low-dose improvement only (no high-dose worsening) = viable\n"
    "    myocardium without significant ischemia.\n"
    "  - No improvement at any dose = scar/non-viable myocardium.\n\n"
    "STEP 4 — VALVULAR CHANGES:\n"
    "  - Dynamic MR: mitral regurgitation that worsens with dobutamine is\n"
    "    significant.\n"
    "  - Gradient changes: aortic stenosis gradients at peak dobutamine\n"
    "    help distinguish true severe from pseudo-severe AS.\n\n"
    "STEP 5 — SECONDARY FINDINGS:\n"
    "  - Rest echo findings (chamber sizes, diastolic function, baseline EF).\n"
    "  - Do NOT discuss heart rate response to pharmacologic stress.\n\n"
    "GUARDRAILS:\n"
    "  - LVEF above normal range: Do NOT flag. An EF of 65-75% is normal\n"
    "    on stress echo.\n"
    "  - Pharmacologic stress: Do NOT mention heart rate response AT ALL.\n"
    "    Do NOT comment on target heart rate, predicted maximum heart rate,\n"
    "    or %% of max predicted heart rate.\n"
    "  - Normal stress echo: Do NOT pad. 'No inducible ischemia and normal\n"
    "    heart function' is sufficient.\n"
    "  - Do NOT restate indications or mention who read the study.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


# ---------------------------------------------------------------------------
# ETT (Exercise Treadmill Test) prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_ETT_STYLE = (
    "This is an exercise treadmill test (ETT) — ECG-only, no imaging.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format organized by system "
    "(exercise capacity -> HR response -> ECG changes -> BP response -> "
    "Duke score -> overall classification -> arrhythmias).\n"
    "At Grade 12 literacy: explain what each finding means in context. Define "
    "terms before using them (e.g., 'METs, which measure how hard your body "
    "was working during the test...').\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Exercise capacity (METs) is the most prognostic finding — "
    "lead with it. ECG changes are secondary."
)

_ETT_RULES = (
    "EXERCISE TREADMILL TEST — DECISION TREE:\n\n"
    "STEP 1 — EXERCISE CAPACITY (most prognostic):\n"
    "  - <5 METs = poor exercise capacity.\n"
    "  - 5-7 METs = moderate exercise capacity.\n"
    "  - 7-10 METs = good exercise capacity.\n"
    "  - >10 METs = excellent exercise capacity.\n"
    "  - Note duration, protocol (Bruce, modified Bruce), and stage reached.\n"
    "  - Exercise capacity is the single strongest predictor of outcomes.\n\n"
    "STEP 2 — HEART RATE RESPONSE:\n"
    "  - Max predicted HR = 220 - age.\n"
    "  - >=85%% of max predicted = adequate test (diagnostic).\n"
    "  - <85%% of max predicted = submaximal test (limited interpretation).\n"
    "  - Chronotropic incompetence: failure to reach 80%% of max predicted\n"
    "    despite adequate effort — abnormal finding.\n"
    "  - Heart rate recovery (HRR): drop <12 bpm in the first minute of\n"
    "    recovery = abnormal (associated with higher risk).\n\n"
    "STEP 3 — ECG / ST CHANGES:\n"
    "  - >=1 mm horizontal or downsloping ST depression = positive for\n"
    "    ischemia. Note leads, magnitude, and time of onset.\n"
    "  - Upsloping ST depression: less specific, may be normal variant.\n"
    "  - ST elevation in leads without Q waves = high-risk finding\n"
    "    (transmural ischemia).\n"
    "  - ST changes during recovery are more specific than during exercise.\n"
    "  - No ST changes = negative.\n\n"
    "STEP 4 — BP RESPONSE:\n"
    "  - Normal: systolic BP rises progressively with exercise.\n"
    "  - Hypotensive response: drop in SBP >10 mmHg from baseline = high-risk\n"
    "    finding (may suggest severe CAD or LM disease).\n"
    "  - Exaggerated response: SBP >250 mmHg — note but less prognostic.\n\n"
    "STEP 5 — DUKE TREADMILL SCORE (if calculable):\n"
    "  - DTS = exercise time (min) - 5 × (max ST deviation mm) -\n"
    "    4 × (angina index: 0=none, 1=non-limiting, 2=limiting).\n"
    "  - >=+5 = low risk (~0.25%% annual mortality).\n"
    "  - -10 to +4 = moderate risk (~1.25%% annual mortality).\n"
    "  - <-10 = high risk (~5%% annual mortality).\n\n"
    "STEP 6 — OVERALL CLASSIFICATION:\n"
    "  - Negative: adequate HR + no ST changes + no symptoms.\n"
    "  - Positive: adequate HR + significant ST changes.\n"
    "  - Equivocal: borderline ST changes or confounders (LVH, digoxin,\n"
    "    baseline ST abnormalities).\n"
    "  - Non-diagnostic: submaximal HR (<85%% predicted) regardless of\n"
    "    ST changes — CANNOT call it 'negative.'\n\n"
    "STEP 7 — ARRHYTHMIAS & SYMPTOMS:\n"
    "  - Exercise-induced PVCs: usually benign.\n"
    "  - Recovery PVCs (frequent PVCs in first minute of recovery): more\n"
    "    concerning, associated with higher risk.\n"
    "  - Exercise-induced chest pain: note if typical vs atypical angina.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Chest pain → ECG ST changes, Duke score, reproduction of symptoms.\n"
    "  - Dyspnea → exercise capacity (METs), BP response, chronotropic response.\n"
    "  - Palpitations → arrhythmias during exercise/recovery.\n"
    "  - Pre-operative clearance → overall exercise capacity and risk profile.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - Negative + >10 METs: <1%% annual cardiac event rate.\n"
    "  - Low-risk DTS (>=+5): ~0.25%% annual mortality.\n"
    "  - Moderate-risk DTS (-10 to +4): ~1.25%% annual mortality.\n\n"
    "GUARDRAILS:\n"
    "  - Negative + >10 METs: very reassuring. Keep explanation concise.\n"
    "  - Submaximal test: call it 'non-diagnostic,' NOT 'negative.' A\n"
    "    submaximal test cannot exclude ischemia.\n"
    "  - False positive context: women, LVH, digoxin, and baseline ST\n"
    "    abnormalities are common causes of false-positive ST changes.\n"
    "    Note these confounders if present.\n"
    "  - Exercise PVCs: Do NOT alarm. Common and usually benign unless\n"
    "    sustained or associated with symptoms.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)

# ---------------------------------------------------------------------------
# Pharmacologic SPECT prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_SPECT_PHARMA_STYLE = (
    "This is a pharmacologic SPECT nuclear stress test.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format.\n"
    "At Grade 12 literacy: explain what each finding means in context.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Ischemia/perfusion is the headline finding, not EF.\n"
    "IMPORTANT pharmacological stress rules:\n"
    "- Do NOT mention heart rate response to stress AT ALL.\n"
    "- Do NOT comment on target heart rate, predicted maximum "
    "heart rate, or %% of max predicted heart rate.\n"
    "- Do NOT state that the heart rate response may limit "
    "interpretation of the EKG stress test."
)

_SPECT_PHARMA_RULES = (
    "PHARMACOLOGIC SPECT NUCLEAR STRESS — DECISION TREE:\n\n"
    "STEP 1 — ISCHEMIA / PERFUSION (always first):\n"
    "  - Reversible defect = ischemia. State location (which coronary\n"
    "    territory — LAD, LCx, RCA), extent, and severity.\n"
    "  - Fixed defect = scar / prior infarct (not active ischemia).\n"
    "  - Partially reversible = mixed (some ischemia + some scar).\n"
    "  - Normal perfusion = no defects. State clearly: 'No ischemia.'\n\n"
    "STEP 2 — SEVERITY SCORING:\n"
    "  - SSS (summed stress score): 0-3 normal, 4-7 mild, 8-13 moderate,\n"
    "    >=14 severe.\n"
    "  - SDS (summed difference score): 0-1 none, 2-4 mild ischemia,\n"
    "    5-7 moderate, >=8 severe ischemia.\n"
    "  - SRS (summed rest score): quantifies scar amount.\n"
    "  - Use scores to quantify severity when available.\n\n"
    "STEP 3 — GATED FUNCTION (secondary — after perfusion):\n"
    "  - LVEF from gated SPECT. Do NOT lead with EF.\n"
    "  - Wall motion abnormalities at stress ('stunning') = ischemia marker.\n"
    "  - Post-stress EF drop compared to rest = significant ischemia.\n"
    "  - Mention EF briefly; do not celebrate or emphasize a normal EF.\n\n"
    "STEP 4 — TID AND OTHER MARKERS:\n"
    "  - TID (transient ischemic dilation) ratio >1.2: concerning for\n"
    "    multivessel or left main disease.\n"
    "  - Increased lung uptake (thallium): elevated pulmonary pressures.\n"
    "  - RV uptake: RV pressure overload.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Chest pain → perfusion defects (reversible = ischemia explaining pain).\n"
    "  - Dyspnea → EF assessment, TID ratio, wall motion.\n"
    "  - Risk stratification → SSS/SDS severity scoring.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - Normal perfusion: <1%% annual major cardiac event rate.\n"
    "  - Mild ischemia (SDS 2-4): ~1-2%% annual risk.\n"
    "  - Moderate-severe ischemia (SDS >=5): higher risk — important finding.\n\n"
    "GUARDRAILS:\n"
    "  - Normal perfusion: keep concise. 'No ischemia and normal heart\n"
    "    function' is sufficient.\n"
    "  - LVEF above normal range: Do NOT flag. An EF of 70-80%% is not\n"
    "    clinically concerning on SPECT — just say it is normal.\n"
    "  - Pharmacologic stress: Do NOT mention heart rate response AT ALL.\n"
    "    Do NOT comment on target heart rate, predicted maximum heart rate,\n"
    "    or %% of max predicted heart rate.\n"
    "  - Small fixed defect: may be attenuation artifact (breast, diaphragm).\n"
    "    Note possibility of artifact if the defect is small and in a\n"
    "    typical attenuation location.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)

# ---------------------------------------------------------------------------
# Exercise SPECT prompt rule constants — decision tree style
# ---------------------------------------------------------------------------

_SPECT_EXERCISE_STYLE = (
    "This is an exercise SPECT nuclear stress test.\n"
    "Follow the DECISION TREE in the interpretation rules strictly.\n\n"
    "At Clinical literacy: structured impression format.\n"
    "At Grade 12 literacy: explain what each finding means in context.\n"
    "At Grade 4-8 literacy: use analogies from the analogy library. Very "
    "simple language. Avoid all abbreviations.\n\n"
    "ALWAYS: Ischemia/perfusion is the headline finding, not EF. "
    "Also comment on exercise adequacy."
)

_SPECT_EXERCISE_RULES = (
    "EXERCISE SPECT NUCLEAR STRESS — DECISION TREE:\n\n"
    "STEP 1 — ISCHEMIA / PERFUSION (always first):\n"
    "  - Reversible defect = ischemia. State location (which coronary\n"
    "    territory — LAD, LCx, RCA), extent, and severity.\n"
    "  - Fixed defect = scar / prior infarct (not active ischemia).\n"
    "  - Partially reversible = mixed (some ischemia + some scar).\n"
    "  - Normal perfusion = no defects. State clearly: 'No ischemia.'\n\n"
    "STEP 2 — SEVERITY SCORING:\n"
    "  - SSS (summed stress score): 0-3 normal, 4-7 mild, 8-13 moderate,\n"
    "    >=14 severe.\n"
    "  - SDS (summed difference score): 0-1 none, 2-4 mild ischemia,\n"
    "    5-7 moderate, >=8 severe ischemia.\n"
    "  - SRS (summed rest score): quantifies scar amount.\n"
    "  - Use scores to quantify severity when available.\n\n"
    "STEP 3 — EXERCISE ADEQUACY:\n"
    "  - METs achieved: <5 poor, 5-7 moderate, 7-10 good, >10 excellent.\n"
    "  - Heart rate response: >=85%% of max predicted (220-age) = adequate.\n"
    "    <85%% = submaximal — clearly state this limitation.\n"
    "  - Heart rate recovery: drop <12 bpm in first minute = abnormal.\n"
    "  - BP response: normal rise; hypotensive drop is ominous.\n"
    "  - ECG ST changes: note but nuclear perfusion findings take precedence\n"
    "    over ECG changes in stress nuclear studies.\n\n"
    "STEP 4 — GATED FUNCTION (secondary — after perfusion):\n"
    "  - LVEF from gated SPECT. Do NOT lead with EF.\n"
    "  - Wall motion abnormalities at stress ('stunning') = ischemia marker.\n"
    "  - Post-stress EF drop compared to rest = significant ischemia.\n"
    "  - Mention EF briefly; do not celebrate or emphasize a normal EF.\n\n"
    "STEP 5 — TID AND OTHER MARKERS:\n"
    "  - TID (transient ischemic dilation) ratio >1.2: concerning for\n"
    "    multivessel or left main disease.\n"
    "  - Increased lung uptake (thallium): elevated pulmonary pressures.\n"
    "  - RV uptake: RV pressure overload.\n\n"
    "SYMPTOM BRIDGING:\n"
    "  - Chest pain → perfusion defects + ECG changes + symptom reproduction.\n"
    "  - Dyspnea → exercise capacity (METs) + EF + perfusion.\n"
    "  - Risk stratification → SSS/SDS + exercise capacity combined.\n"
    "  When the indication includes a symptom, explicitly connect the findings.\n\n"
    "RISK CONTEXT:\n"
    "  - Normal perfusion + good exercise (>10 METs): <0.5%% annual event rate.\n"
    "  - Normal perfusion + submaximal: still reassuring but note limitation.\n\n"
    "GUARDRAILS:\n"
    "  - Normal perfusion + good exercise: very reassuring. Keep concise.\n"
    "  - LVEF above normal range: Do NOT flag. An EF of 70-80%% is not\n"
    "    clinically concerning on SPECT — just say it is normal.\n"
    "  - Submaximal test (<85%% predicted): clearly state this limitation.\n"
    "    Perfusion findings still valid but sensitivity may be reduced.\n"
    "  - Small fixed defect: may be attenuation artifact (breast, diaphragm).\n"
    "    Note possibility of artifact if the defect is small and in a\n"
    "    typical attenuation location.\n"
    "  - Do NOT restate clinical indications at the end.\n"
    "  - Do NOT mention who interpreted/read/signed the study.\n"
    "  - Do NOT state whether prior studies are or are not available\n"
    "    for comparison."
)


class StressTestHandler(BaseTestType):

    @property
    def test_type_id(self) -> str:
        return "stress_test"

    @property
    def display_name(self) -> str:
        return "Stress Test"

    @property
    def keywords(self) -> list[str]:
        return [
            "stress test",
            "exercise stress",
            "treadmill test",
            "exercise tolerance test",
            "bruce protocol",
            "modified bruce",
            "exercise treadmill",
            "cardiac stress",
            "exercise ecg",
            "exercise ekg",
            "exercise electrocardiogram",
            "graded exercise test",
            "mets",
            "peak heart rate",
            "target heart rate",
            "st depression",
            "st segment",
            "duke treadmill",
            "chronotropic",
            "rate pressure product",
            "exercise capacity",
            # Nuclear / SPECT
            "nuclear stress",
            "myocardial perfusion",
            "spect",
            "sestamibi",
            # PET
            "cardiac pet",
            "cardiac positron emission tomography",
            "positron emission tomography",
            "pet/ct",
            "pet-ct",
            "rb-82",
            "rubidium",
            "mbf",
            "coronary flow reserve",
            # Pharmacologic
            "lexiscan",
            "regadenoson",
            "adenosine stress",
            "pharmacologic stress",
            # Echo
            "stress echocardiogram",
            "stress echo",
            "dobutamine stress",
            "dobutamine echo",
            "bicycle stress",
        ]

    @property
    def category(self) -> str:
        return "cardiac"

    # ------------------------------------------------------------------
    # Subtype resolution (used by registry.detect)
    # ------------------------------------------------------------------
    def resolve_subtype(self, extraction_result: ExtractionResult) -> tuple[str, str] | None:
        """Return the resolved stress subtype for this report."""
        return self._classify_subtype(extraction_result.full_text)

    # ------------------------------------------------------------------
    # Subtype classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_subtype(text: str) -> tuple[str, str]:
        """Determine the specific stress test subtype.

        Returns (type_id, display_name).
        """
        lower = text.lower()

        # Axis 1: pharmacologic vs exercise
        is_pharma = any(agent in lower for agent in _PHARMA_AGENTS)

        # Axis 2: imaging modality (priority: PET > SPECT > Echo > ECG-only)
        if any(kw in lower for kw in _PET_KEYWORDS):
            modality = "pet"
        elif any(kw in lower for kw in _SPECT_KEYWORDS):
            modality = "spect"
        elif any(kw in lower for kw in _ECHO_KEYWORDS):
            modality = "echo"
        else:
            modality = "ecg"

        # Special dobutamine rule: if dobutamine is detected AND echo
        # keywords are present → pharma_stress_echo. If dobutamine is
        # detected WITHOUT echo keywords, it's still pharmacologic but
        # modality depends on other imaging keywords.
        if "dobutamine" in lower and modality != "echo":
            # Dobutamine without echo keywords — still pharmacologic,
            # modality determined by other keywords above
            pass

        return _SUBTYPES[(is_pharma, modality)]

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, extraction_result: ExtractionResult) -> float:
        """Keyword-based detection with tiered scoring."""
        text = extraction_result.full_text.lower()

        strong_keywords = [
            "stress test",
            "exercise stress test",
            "exercise treadmill test",
            "exercise tolerance test",
            "treadmill stress",
            "cardiac stress test",
            "exercise stress echocardiogram",
            "bruce protocol",
            "modified bruce protocol",
            "graded exercise test",
            "exercise ecg",
            "exercise ekg",
            "exercise electrocardiogram",
            "treadmill exercise test",
            # Nuclear / SPECT
            "nuclear stress test",
            "myocardial perfusion imaging",
            "pharmacologic stress",
            # PET
            "cardiac pet",
            "cardiac positron emission tomography",
            "positron emission tomography",
            "myocardial blood flow",
            "coronary flow reserve",
            # Echo
            "stress echocardiogram",
            "dobutamine stress",
        ]
        moderate_keywords = [
            "mets achieved",
            "mets attained",
            "metabolic equivalents",
            "peak heart rate",
            "target heart rate",
            "max predicted heart rate",
            "mphr",
            "% predicted",
            "st depression",
            "st elevation",
            "st segment changes",
            "st changes",
            "duke treadmill score",
            "rate pressure product",
            "double product",
            "chronotropic",
            "exercise capacity",
            "exercise duration",
            "treadmill time",
            "exercise stage",
            "recovery phase",
            "peak exercise",
            # Nuclear / SPECT
            "spect",
            "sestamibi",
            "technetium",
            "tc-99m",
            "myoview",
            "thallium",
            # PET
            "pet/ct",
            "pet-ct",
            "rb-82",
            "rubidium",
            "positron",
            "positron emission tomography",
            "cardiac positron emission tomography",
            # Pharmacologic agents
            "lexiscan",
            "regadenoson",
            "adenosine",
            "dipyridamole",
            "dobutamine",
            # Echo
            "wall motion at stress",
            "bicycle stress",
            "stress echo",
        ]
        weak_keywords = [
            "treadmill",
            "bruce",
            "angina",
            "chest pain during exercise",
            "dyspnea on exertion",
            "exercise",
            "mets",
            "arrhythmia",
            "pvcs",
            "perfusion",
            "ischemia",
            "nuclear",
        ]

        strong_count = sum(1 for k in strong_keywords if k in text)
        moderate_count = sum(1 for k in moderate_keywords if k in text)
        weak_count = sum(1 for k in weak_keywords if k in text)

        if strong_count > 0:
            base = 0.7
        elif moderate_count >= 3:
            base = 0.4
        elif moderate_count >= 1:
            base = 0.2
        else:
            base = 0.0

        bonus = min(0.3, moderate_count * 0.05 + weak_count * 0.02)
        return min(1.0, base + bonus)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse(
        self,
        extraction_result: ExtractionResult,
        gender: str | None = None,
        age: int | None = None,
    ) -> ParsedReport:
        """Extract structured measurements, sections, and findings."""
        text = extraction_result.full_text
        warnings: list[str] = []

        subtype_id, subtype_display = self._classify_subtype(text)

        # Choose measurement extractor based on subtype
        parsed_measurements: list[ParsedMeasurement] = []
        if subtype_id in ("pharma_pet_stress", "exercise_pet_stress"):
            _load_pet()
            parsed_measurements = _pet_extractor(text, gender)
        else:
            # Use stress test measurements for treadmill/SPECT/echo subtypes
            raw_measurements = extract_measurements(text, extraction_result.pages)
            for m in raw_measurements:
                classification = classify_measurement(m.abbreviation, m.value)
                parsed_measurements.append(
                    ParsedMeasurement(
                        name=m.name,
                        abbreviation=m.abbreviation,
                        value=m.value,
                        unit=m.unit,
                        status=classification.status,
                        direction=classification.direction,
                        reference_range=classification.reference_range_str,
                        raw_text=m.raw_text,
                        page_number=m.page_number,
                    )
                )

        sections = self._extract_sections(text)
        findings = self._extract_findings(text)

        if not parsed_measurements:
            warnings.append(
                "No measurements could be extracted. "
                "The report format may not be supported."
            )

        detection_confidence = self.detect(extraction_result)

        return ParsedReport(
            test_type=subtype_id,
            test_type_display=subtype_display,
            detection_confidence=detection_confidence,
            measurements=parsed_measurements,
            sections=sections,
            findings=findings,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Reference ranges & glossary
    # ------------------------------------------------------------------
    def get_reference_ranges(self) -> dict:
        return {
            abbr: {
                "normal_min": rr.normal_min,
                "normal_max": rr.normal_max,
                "unit": rr.unit,
                "source": rr.source,
            }
            for abbr, rr in REFERENCE_RANGES.items()
        }

    def get_glossary(self) -> dict[str, str]:
        return STRESS_GLOSSARY

    # ------------------------------------------------------------------
    # Prompt context (subtype-specific)
    # ------------------------------------------------------------------
    def get_prompt_context(
        self,
        extraction_result: ExtractionResult | None = None,
    ) -> dict:
        text = extraction_result.full_text if extraction_result else ""
        subtype_id, _ = self._classify_subtype(text)

        base = {
            "specialty": "cardiology",
            "category": "cardiac",
            "guidelines": "ACC/AHA 2002 Guideline Update for Exercise Testing",
        }

        if subtype_id == "exercise_treadmill_test":
            base["test_type"] = "exercise_stress_test"
            base["explanation_style"] = _ETT_STYLE
            base["interpretation_rules"] = _ETT_RULES

        elif subtype_id == "pharma_spect_stress":
            base["test_type"] = "pharma_spect_stress"
            base["explanation_style"] = _SPECT_PHARMA_STYLE
            base["interpretation_rules"] = _SPECT_PHARMA_RULES

        elif subtype_id == "exercise_spect_stress":
            base["test_type"] = "exercise_spect_stress"
            base["explanation_style"] = _SPECT_EXERCISE_STYLE
            base["interpretation_rules"] = _SPECT_EXERCISE_RULES

        elif subtype_id == "pharma_pet_stress":
            base["test_type"] = "pharma_pet_stress"
            base["guidelines"] = "ASNC 2016 PET Myocardial Perfusion Imaging Guidelines"
            base["explanation_style"] = _PET_PHARMA_STYLE
            base["interpretation_rules"] = _PET_PHARMA_RULES
            self._inject_cfc(base, text, extraction_result)

        elif subtype_id == "exercise_pet_stress":
            base["test_type"] = "exercise_pet_stress"
            base["guidelines"] = "ASNC 2016 PET Myocardial Perfusion Imaging Guidelines"
            base["explanation_style"] = _PET_EXERCISE_STYLE
            base["interpretation_rules"] = _PET_EXERCISE_RULES
            self._inject_cfc(base, text, extraction_result)

        elif subtype_id == "exercise_stress_echo":
            base["test_type"] = "exercise_stress_echo"
            base["explanation_style"] = _STRESS_ECHO_EXERCISE_STYLE
            base["interpretation_rules"] = _STRESS_ECHO_EXERCISE_RULES

        elif subtype_id == "pharma_stress_echo":
            base["test_type"] = "pharma_stress_echo"
            base["explanation_style"] = _STRESS_ECHO_PHARMA_STYLE
            base["interpretation_rules"] = _STRESS_ECHO_PHARMA_RULES

        return base

    @staticmethod
    def _inject_cfc(base: dict, text: str, extraction_result: ExtractionResult | None) -> None:
        """Lazy-load CFC and inject into prompt context when V2 is active."""
        if not extraction_result:
            return
        _load_pet()
        parsed = _pet_extractor(text)
        cfc = _pet_get_cfc(text, parsed)
        if cfc:
            base["cfc_summary"] = cfc

    # ------------------------------------------------------------------
    # Section / findings extraction (unchanged)
    # ------------------------------------------------------------------
    def _extract_sections(self, text: str) -> list[ReportSection]:
        """Split report text into labeled sections."""
        section_headers = [
            r"INDICATION|REASON\s+FOR\s+(?:TEST|STUDY)",
            r"PROTOCOL|EXERCISE\s+PROTOCOL|PROCEDURE",
            r"BASELINE|RESTING|PRE[- ]?EXERCISE",
            r"EXERCISE\s+(?:DATA|RESPONSE|RESULTS|PHASE)",
            r"HEMODYNAMIC\s+(?:DATA|RESPONSE)",
            r"ECG\s+(?:FINDINGS|CHANGES|RESPONSE|INTERPRETATION)",
            r"EKG\s+(?:FINDINGS|CHANGES|RESPONSE|INTERPRETATION)",
            r"ELECTROCARDIOGRAPHIC\s+(?:FINDINGS|CHANGES|RESPONSE)",
            r"ST\s+(?:SEGMENT\s+)?(?:ANALYSIS|CHANGES)",
            r"SYMPTOMS|SYMPTOM\s+RESPONSE",
            r"ARRHYTHMIA|RHYTHM",
            r"RECOVERY|POST[- ]?EXERCISE",
            r"PERFUSION|PERFUSION\s+(?:FINDINGS|IMAGES|RESULTS)",
            r"GATED\s+(?:IMAGES|SPECT|DATA)",
            r"WALL\s+MOTION",
            r"STRESS\s+(?:IMAGES|DATA|RESULTS)",
            r"REST\s+(?:IMAGES|DATA|RESULTS)",
            r"FLOW\s+(?:DATA|QUANTIFICATION|RESERVE)",
            r"CONCLUSION|IMPRESSION|SUMMARY|INTERPRETATION|FINDINGS",
        ]

        combined = "|".join(f"({p})" for p in section_headers)
        header_re = re.compile(
            r"(?:^|\n)\s*(" + combined + r")\s*[:\-]?\s*",
            re.IGNORECASE | re.MULTILINE,
        )

        matches = list(header_re.finditer(text))
        sections: list[ReportSection] = []

        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_name = match.group(1).strip().rstrip(":-").strip()
            content = text[start:end].strip()
            if content:
                sections.append(
                    ReportSection(
                        name=section_name.upper(),
                        content=content,
                    )
                )

        return sections

    def _extract_findings(self, text: str) -> list[str]:
        """Extract conclusion/impression/interpretation lines."""
        findings: list[str] = []
        findings_re = re.compile(
            r"(?:CONCLUSION|IMPRESSION|SUMMARY|INTERPRETATION|FINDINGS)\s*[:\-]?\s*\n"
            r"([\s\S]*?)(?:\n\s*\n|\Z)",
            re.IGNORECASE,
        )
        for match in findings_re.finditer(text):
            block = match.group(1).strip()
            lines = re.split(r"\n\s*(?:\d+[\.\)]\s*|[-*]\s*)", block)
            for line in lines:
                line = line.strip()
                if line and len(line) > 10:
                    findings.append(line)

        return findings
