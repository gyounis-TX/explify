"""
Measurement extraction for blood lab reports.

Uses a dual strategy:
1. Table-first: parse structured tables from PDF extraction (more reliable).
2. Regex fallback: pattern-match from raw text for OCR/pasted reports.

Each analyte is defined with known names/aliases, a standard abbreviation,
expected unit, regex patterns, and sanity bounds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from api.models import ExtractedTable, PageExtractionResult


@dataclass
class PriorValueRaw:
    value: float
    time_label: str


@dataclass
class RawMeasurement:
    name: str
    abbreviation: str
    value: float
    unit: str
    raw_text: str
    page_number: Optional[int] = None
    prior_values: list[PriorValueRaw] = field(default_factory=list)


@dataclass
class MeasurementDef:
    """Definition of a lab analyte to extract."""

    name: str
    abbreviation: str
    unit: str
    patterns: list[str]
    # Known names/aliases used for table row matching (case-insensitive)
    table_aliases: list[str] = field(default_factory=list)
    value_min: float = 0.0
    value_max: float = 99999.0


_NUM = r"(?P<value>\d+\.?\d*)"
_SEP = r"[\s:=]+\s*"


MEASUREMENT_DEFS: list[MeasurementDef] = [
    # ===== Comprehensive Metabolic Panel (CMP) =====
    MeasurementDef(
        name="Glucose",
        abbreviation="GLU",
        unit="mg/dL",
        table_aliases=["glucose", "glu", "fasting glucose", "blood glucose"],
        patterns=[
            rf"(?i)(?:fasting\s+)?glucose{_SEP}{_NUM}\s*(?:mg\/dL|mg\/dl)?",
            rf"(?i)\bGLU\b{_SEP}{_NUM}\s*(?:mg\/dL|mg\/dl)?",
        ],
        value_min=10.0,
        value_max=900.0,
    ),
    MeasurementDef(
        name="BUN",
        abbreviation="BUN",
        unit="mg/dL",
        table_aliases=["bun", "blood urea nitrogen", "urea nitrogen"],
        patterns=[
            rf"(?i)\bBUN\b{_SEP}{_NUM}\s*(?:mg\/dL|mg\/dl)?",
            rf"(?i)blood\s+urea\s+nitrogen{_SEP}{_NUM}\s*(?:mg\/dL)?",
            rf"(?i)urea\s+nitrogen{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=1.0,
        value_max=150.0,
    ),
    MeasurementDef(
        name="Creatinine",
        abbreviation="CREAT",
        unit="mg/dL",
        table_aliases=["creatinine", "creat", "serum creatinine"],
        patterns=[
            rf"(?i)creatinine{_SEP}{_NUM}\s*(?:mg\/dL|mg\/dl)?",
            rf"(?i)\bCREAT\b{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=0.1,
        value_max=20.0,
    ),
    MeasurementDef(
        name="eGFR",
        abbreviation="EGFR",
        unit="mL/min/1.73m2",
        table_aliases=["egfr", "gfr", "estimated gfr", "est. gfr",
                        "estimated glomerular filtration rate"],
        patterns=[
            rf"(?i)e?GFR{_SEP}{_NUM}\s*(?:mL\/min)?",
            rf"(?i)glomerular\s+filtration\s+rate{_SEP}{_NUM}",
        ],
        value_min=1.0,
        value_max=200.0,
    ),
    MeasurementDef(
        name="Sodium",
        abbreviation="NA",
        unit="mEq/L",
        table_aliases=["sodium", "na"],
        patterns=[
            rf"(?i)sodium{_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
            rf"(?i)\bNa\b{_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
        ],
        value_min=100.0,
        value_max=180.0,
    ),
    MeasurementDef(
        name="Potassium",
        abbreviation="K",
        unit="mEq/L",
        table_aliases=["potassium", "k"],
        patterns=[
            rf"(?i)potassium{_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
            rf"(?i)\bK\b{_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
        ],
        value_min=1.5,
        value_max=9.0,
    ),
    MeasurementDef(
        name="Chloride",
        abbreviation="CL",
        unit="mEq/L",
        table_aliases=["chloride", "cl"],
        patterns=[
            rf"(?i)chloride{_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
            rf"(?i)\bCl\b{_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
        ],
        value_min=70.0,
        value_max=140.0,
    ),
    MeasurementDef(
        name="CO2/Bicarbonate",
        abbreviation="CO2",
        unit="mEq/L",
        table_aliases=["co2", "carbon dioxide", "bicarbonate", "bicarb", "hco3"],
        patterns=[
            rf"(?i)(?:CO2|carbon\s+dioxide|bicarbonate|bicarb|HCO3){_SEP}{_NUM}\s*(?:mEq\/L|mmol\/L)?",
        ],
        value_min=5.0,
        value_max=50.0,
    ),
    MeasurementDef(
        name="Calcium",
        abbreviation="CA",
        unit="mg/dL",
        table_aliases=["calcium", "ca", "total calcium"],
        patterns=[
            rf"(?i)(?:total\s+)?calcium{_SEP}{_NUM}\s*(?:mg\/dL)?",
            rf"(?i)\bCa\b{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=4.0,
        value_max=18.0,
    ),
    MeasurementDef(
        name="Total Protein",
        abbreviation="TP",
        unit="g/dL",
        table_aliases=["total protein", "protein, total", "tp"],
        patterns=[
            rf"(?i)total\s+protein{_SEP}{_NUM}\s*(?:g\/dL|g\/dl)?",
            rf"(?i)\bTP\b{_SEP}{_NUM}\s*(?:g\/dL)?",
        ],
        value_min=2.0,
        value_max=15.0,
    ),
    MeasurementDef(
        name="Albumin",
        abbreviation="ALB",
        unit="g/dL",
        table_aliases=["albumin", "alb"],
        patterns=[
            rf"(?i)albumin{_SEP}{_NUM}\s*(?:g\/dL|g\/dl)?",
            rf"(?i)\bALB\b{_SEP}{_NUM}\s*(?:g\/dL)?",
        ],
        value_min=1.0,
        value_max=8.0,
    ),
    MeasurementDef(
        name="Total Bilirubin",
        abbreviation="TBILI",
        unit="mg/dL",
        table_aliases=["total bilirubin", "bilirubin, total", "bilirubin total",
                        "t. bilirubin", "tbili", "t. bili", "t bili"],
        patterns=[
            rf"(?i)(?:total\s+)?bilirubin{_SEP}{_NUM}\s*(?:mg\/dL)?",
            rf"(?i)\bTBILI?\b{_SEP}{_NUM}\s*(?:mg\/dL)?",
            rf"(?i)T\.?\s*Bili{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=0.0,
        value_max=30.0,
    ),
    MeasurementDef(
        name="AST",
        abbreviation="AST",
        unit="U/L",
        table_aliases=["ast", "sgot", "aspartate aminotransferase",
                        "ast (sgot)"],
        patterns=[
            rf"(?i)\bAST\b{_SEP}{_NUM}\s*(?:U\/L|u\/l|IU\/L)?",
            rf"(?i)\bSGOT\b{_SEP}{_NUM}\s*(?:U\/L)?",
            rf"(?i)aspartate\s+aminotransferase{_SEP}{_NUM}",
        ],
        value_min=1.0,
        value_max=5000.0,
    ),
    MeasurementDef(
        name="ALT",
        abbreviation="ALT",
        unit="U/L",
        table_aliases=["alt", "sgpt", "alanine aminotransferase",
                        "alt (sgpt)"],
        patterns=[
            rf"(?i)\bALT\b{_SEP}{_NUM}\s*(?:U\/L|u\/l|IU\/L)?",
            rf"(?i)\bSGPT\b{_SEP}{_NUM}\s*(?:U\/L)?",
            rf"(?i)alanine\s+aminotransferase{_SEP}{_NUM}",
        ],
        value_min=1.0,
        value_max=5000.0,
    ),
    MeasurementDef(
        name="Alkaline Phosphatase",
        abbreviation="ALP",
        unit="U/L",
        table_aliases=["alkaline phosphatase", "alk phos", "alk. phos.",
                        "alp", "alkp"],
        patterns=[
            rf"(?i)(?:alkaline\s+phosphatase|alk\.?\s*phos\.?|ALP|ALKP){_SEP}{_NUM}\s*(?:U\/L|u\/l|IU\/L)?",
        ],
        value_min=1.0,
        value_max=2000.0,
    ),

    # ===== Complete Blood Count (CBC) =====
    MeasurementDef(
        name="WBC",
        abbreviation="WBC",
        unit="K/uL",
        table_aliases=["wbc", "white blood cell count", "white blood cells",
                        "leukocytes", "leucocytes", "tlc",
                        "total leucocyte count", "total leukocyte count"],
        patterns=[
            rf"(?i)\bWBC\b{_SEP}{_NUM}\s*(?:K\/uL|k\/ul|x10[³\^]3\/uL|10\*3\/uL)?",
            rf"(?i)white\s+blood\s+cell(?:s)?(?:\s+count)?{_SEP}{_NUM}",
        ],
        value_min=0.1,
        value_max=100.0,
    ),
    # TLC — Indian labs report WBC as absolute count in /cumm (e.g., 13100)
    # Treated as a separate def so value bounds can differ; maps to same
    # reference abbreviation WBC after dividing by 1000 in post-processing.
    MeasurementDef(
        name="WBC",
        abbreviation="WBC_CUMM",
        unit="/cumm",
        table_aliases=["tlc", "total leucocyte count", "total leukocyte count"],
        patterns=[
            rf"(?i)\bTLC\b(?:\s*\(.*?\))?{_SEP}{_NUM}\s*(?:\/\s*cumm|\/\s*cu\s*mm)",
            rf"(?i)total\s+le[u]?cocyte\s+count{_SEP}{_NUM}\s*(?:\/\s*cumm|\/\s*cu\s*mm)?",
        ],
        value_min=100.0,
        value_max=100000.0,
    ),
    MeasurementDef(
        name="RBC",
        abbreviation="RBC",
        unit="M/uL",
        table_aliases=["rbc", "red blood cell count", "red blood cells",
                        "erythrocytes"],
        patterns=[
            rf"(?i)\bRBC\b{_SEP}{_NUM}\s*(?:M\/uL|m\/ul|x10[⁶\^]6\/uL|10\*6\/uL|mill\/\s*cumm)?",
            rf"(?i)red\s+blood\s+cell(?:s)?(?:\s+count)?{_SEP}{_NUM}",
        ],
        value_min=1.0,
        value_max=10.0,
    ),
    MeasurementDef(
        name="Hemoglobin",
        abbreviation="HGB",
        unit="g/dL",
        table_aliases=["hemoglobin", "haemoglobin", "hgb", "hb"],
        patterns=[
            rf"(?i)ha?emoglobin{_SEP}{_NUM}\s*(?:g\/dL|g\/dl|gm\/\s*dl)?",
            rf"(?i)\bHGB\b{_SEP}{_NUM}\s*(?:g\/dL|gm\/\s*dl)?",
            rf"(?i)\bHb\b{_SEP}{_NUM}\s*(?:g\/dL|gm\/\s*dl)?",
        ],
        value_min=3.0,
        value_max=25.0,
    ),
    MeasurementDef(
        name="Hematocrit",
        abbreviation="HCT",
        unit="%",
        table_aliases=["hematocrit", "haematocrit", "hct", "pcv",
                        "pcv/haematocrit", "pcv/hematocrit",
                        "packed cell volume"],
        patterns=[
            rf"(?i)ha?ematocrit{_SEP}{_NUM}\s*%?",
            rf"(?i)\bHCT\b{_SEP}{_NUM}\s*%?",
            rf"(?i)\bPCV\b(?:\/ha?ematocrit)?{_SEP}{_NUM}\s*%?",
            rf"(?i)packed\s+cell\s+volume{_SEP}{_NUM}\s*%?",
        ],
        value_min=10.0,
        value_max=75.0,
    ),
    MeasurementDef(
        name="MCV",
        abbreviation="MCV",
        unit="fL",
        table_aliases=["mcv", "mean corpuscular volume"],
        patterns=[
            rf"(?i)\bMCV\b{_SEP}{_NUM}\s*(?:fL|fl)?",
            rf"(?i)mean\s+corpuscular\s+volume{_SEP}{_NUM}",
        ],
        value_min=40.0,
        value_max=150.0,
    ),
    MeasurementDef(
        name="MCH",
        abbreviation="MCH",
        unit="pg",
        table_aliases=["mch", "mean corpuscular hemoglobin"],
        patterns=[
            rf"(?i)\bMCH\b(?!C){_SEP}{_NUM}\s*(?:pg)?",
            rf"(?i)mean\s+corpuscular\s+hemoglobin(?!\s+conc){_SEP}{_NUM}",
        ],
        value_min=10.0,
        value_max=55.0,
    ),
    MeasurementDef(
        name="MCHC",
        abbreviation="MCHC",
        unit="g/dL",
        table_aliases=["mchc", "mean corpuscular hemoglobin concentration"],
        patterns=[
            rf"(?i)\bMCHC\b{_SEP}{_NUM}\s*(?:g\/dL|g\/dl|%)?",
            rf"(?i)mean\s+corpuscular\s+hemoglobin\s+conc(?:entration)?{_SEP}{_NUM}",
        ],
        value_min=20.0,
        value_max=45.0,
    ),
    MeasurementDef(
        name="RDW",
        abbreviation="RDW",
        unit="%",
        table_aliases=["rdw", "red cell distribution width", "rdw-cv"],
        patterns=[
            rf"(?i)\bRDW\b(?:-CV)?{_SEP}{_NUM}\s*%?",
            rf"(?i)red\s+cell\s+distribution\s+width{_SEP}{_NUM}",
        ],
        value_min=5.0,
        value_max=35.0,
    ),
    MeasurementDef(
        name="Platelet Count",
        abbreviation="PLT",
        unit="K/uL",
        table_aliases=["platelet count", "platelets", "plt"],
        patterns=[
            rf"(?i)platelet(?:s)?(?:\s+count)?{_SEP}{_NUM}\s*(?:K\/uL|k\/ul|x10[³\^]3\/uL|lakh\/\s*cumm|lac\/cumm)?",
            rf"(?i)\bPLT\b{_SEP}{_NUM}\s*(?:K\/uL|k\/ul|lakh\/\s*cumm)?",
        ],
        value_min=0.5,
        value_max=2000.0,
    ),
    MeasurementDef(
        name="MPV",
        abbreviation="MPV",
        unit="fL",
        table_aliases=["mpv", "mean platelet volume"],
        patterns=[
            rf"(?i)\bMPV\b{_SEP}{_NUM}\s*(?:fL|fl)?",
            rf"(?i)mean\s+platelet\s+volume{_SEP}{_NUM}",
        ],
        value_min=3.0,
        value_max=25.0,
    ),

    # ===== Lipid Panel =====
    MeasurementDef(
        name="Total Cholesterol",
        abbreviation="CHOL",
        unit="mg/dL",
        table_aliases=["total cholesterol", "cholesterol, total",
                        "cholesterol total", "cholesterol"],
        patterns=[
            rf"(?i)(?:total\s+)?cholesterol{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=50.0,
        value_max=500.0,
    ),
    MeasurementDef(
        name="HDL Cholesterol",
        abbreviation="HDL",
        unit="mg/dL",
        table_aliases=["hdl", "hdl cholesterol", "hdl-c", "hdl chol"],
        patterns=[
            rf"(?i)HDL(?:\s+cholesterol|\s+chol\.?|-C)?{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=10.0,
        value_max=150.0,
    ),
    MeasurementDef(
        name="LDL Cholesterol",
        abbreviation="LDL",
        unit="mg/dL",
        table_aliases=["ldl", "ldl cholesterol", "ldl-c", "ldl chol",
                        "ldl calculated", "ldl calc",
                        "ldl cholesterol calculated", "direct ldl",
                        "ldl direct", "ldl cholesterol direct"],
        patterns=[
            rf"(?i)(?:direct\s+)?LDL(?:\s+cholesterol)?(?:\s+(?:calc(?:ulated)?|direct))?(?:\s+chol\.?|-C)?{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=10.0,
        value_max=400.0,
    ),
    MeasurementDef(
        name="Triglycerides",
        abbreviation="TRIG",
        unit="mg/dL",
        table_aliases=["triglycerides", "trig", "triglyceride"],
        patterns=[
            rf"(?i)triglycerides?{_SEP}{_NUM}\s*(?:mg\/dL)?",
            rf"(?i)\bTRIG\b{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=10.0,
        value_max=2000.0,
    ),
    MeasurementDef(
        name="VLDL Cholesterol",
        abbreviation="VLDL",
        unit="mg/dL",
        table_aliases=["vldl", "vldl cholesterol", "vldl-c", "vldl chol"],
        patterns=[
            rf"(?i)VLDL(?:\s+cholesterol|\s+chol\.?|-C)?{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=1.0,
        value_max=200.0,
    ),

    # ===== Thyroid Panel =====
    MeasurementDef(
        name="TSH",
        abbreviation="TSH",
        unit="uIU/mL",
        table_aliases=["tsh", "thyroid stimulating hormone",
                        "thyrotropin"],
        patterns=[
            rf"(?i)\bTSH\b{_SEP}{_NUM}\s*(?:uIU\/mL|mIU\/L|uU\/mL)?",
            rf"(?i)thyroid\s+stimulating\s+hormone{_SEP}{_NUM}",
        ],
        value_min=0.001,
        value_max=100.0,
    ),
    MeasurementDef(
        name="Free T4",
        abbreviation="FT4",
        unit="ng/dL",
        table_aliases=["free t4", "ft4", "free thyroxine", "t4, free"],
        patterns=[
            rf"(?i)free\s+T4{_SEP}{_NUM}\s*(?:ng\/dL|ng\/dl)?",
            rf"(?i)\bFT4\b{_SEP}{_NUM}\s*(?:ng\/dL)?",
            rf"(?i)free\s+thyroxine{_SEP}{_NUM}",
        ],
        value_min=0.1,
        value_max=10.0,
    ),
    MeasurementDef(
        name="Free T3",
        abbreviation="FT3",
        unit="pg/mL",
        table_aliases=["free t3", "ft3", "free triiodothyronine", "t3, free"],
        patterns=[
            rf"(?i)free\s+T3{_SEP}{_NUM}\s*(?:pg\/mL|pg\/ml)?",
            rf"(?i)\bFT3\b{_SEP}{_NUM}\s*(?:pg\/mL)?",
            rf"(?i)free\s+triiodothyronine{_SEP}{_NUM}",
        ],
        value_min=0.5,
        value_max=20.0,
    ),
    MeasurementDef(
        name="Total T4",
        abbreviation="TT4",
        unit="ug/dL",
        table_aliases=["total t4", "t4, total", "t4 total", "thyroxine"],
        patterns=[
            rf"(?i)total\s+T4{_SEP}{_NUM}\s*(?:ug\/dL|mcg\/dL)?",
            rf"(?i)\bT4\b(?:\s*,?\s*total)?{_SEP}{_NUM}\s*(?:ug\/dL|mcg\/dL)?",
            rf"(?i)thyroxine{_SEP}{_NUM}\s*(?:ug\/dL|mcg\/dL)?",
        ],
        value_min=0.5,
        value_max=30.0,
    ),

    # ===== Iron Studies =====
    MeasurementDef(
        name="Iron",
        abbreviation="FE",
        unit="ug/dL",
        table_aliases=["iron", "serum iron", "fe", "iron, serum"],
        patterns=[
            rf"(?i)(?:serum\s+)?iron{_SEP}{_NUM}\s*(?:ug\/dL|mcg\/dL)?",
            rf"(?i)\bFe\b{_SEP}{_NUM}\s*(?:ug\/dL)?",
        ],
        value_min=5.0,
        value_max=500.0,
    ),
    MeasurementDef(
        name="TIBC",
        abbreviation="TIBC",
        unit="ug/dL",
        table_aliases=["tibc", "total iron binding capacity",
                        "iron binding capacity"],
        patterns=[
            rf"(?i)\bTIBC\b{_SEP}{_NUM}\s*(?:ug\/dL|mcg\/dL)?",
            rf"(?i)total\s+iron[\s-]+binding\s+capacity{_SEP}{_NUM}",
        ],
        value_min=50.0,
        value_max=800.0,
    ),
    MeasurementDef(
        name="Ferritin",
        abbreviation="FERR",
        unit="ng/mL",
        table_aliases=["ferritin"],
        patterns=[
            rf"(?i)ferritin{_SEP}{_NUM}\s*(?:ng\/mL|ng\/ml)?",
        ],
        value_min=1.0,
        value_max=5000.0,
    ),
    MeasurementDef(
        name="Transferrin Saturation",
        abbreviation="TSAT",
        unit="%",
        table_aliases=["transferrin saturation", "tsat", "iron saturation",
                        "transferrin sat", "% saturation"],
        patterns=[
            rf"(?i)transferrin\s+sat(?:uration)?{_SEP}{_NUM}\s*%?",
            rf"(?i)\bTSAT\b{_SEP}{_NUM}\s*%?",
            rf"(?i)iron\s+saturation{_SEP}{_NUM}\s*%?",
        ],
        value_min=1.0,
        value_max=100.0,
    ),

    # ===== HbA1c =====
    MeasurementDef(
        name="HbA1c",
        abbreviation="A1C",
        unit="%",
        table_aliases=["hba1c", "hemoglobin a1c", "a1c", "hgb a1c",
                        "glycated hemoglobin", "glycosylated hemoglobin"],
        patterns=[
            rf"(?i)(?:HbA1c|Hgb\s+A1c|hemoglobin\s+A1c|A1C){_SEP}{_NUM}\s*%?",
            rf"(?i)glyc(?:ated|osylated)\s+hemoglobin{_SEP}{_NUM}\s*%?",
        ],
        value_min=3.0,
        value_max=20.0,
    ),

    # ===== Urinalysis (numeric analytes) =====
    MeasurementDef(
        name="Urine pH",
        abbreviation="UA_PH",
        unit="",
        table_aliases=["ph", "urine ph"],
        patterns=[
            rf"(?i)(?:urine\s+)?pH{_SEP}{_NUM}",
        ],
        value_min=2.0,
        value_max=11.0,
    ),
    MeasurementDef(
        name="Specific Gravity",
        abbreviation="UA_SG",
        unit="",
        table_aliases=["specific gravity", "sp. gravity", "sp gravity",
                        "spec gravity", "sg"],
        patterns=[
            rf"(?i)(?:urine\s+)?(?:specific|sp\.?)\s+gravity{_SEP}{_NUM}",
        ],
        value_min=0.999,
        value_max=1.060,
    ),
    MeasurementDef(
        name="Urine Protein",
        abbreviation="UA_PROT",
        unit="mg/dL",
        table_aliases=["urine protein", "protein (urine)", "ua protein"],
        patterns=[
            rf"(?i)(?:urine|ua)\s+protein{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=0.0,
        value_max=1000.0,
    ),
    MeasurementDef(
        name="Urine Glucose",
        abbreviation="UA_GLU",
        unit="mg/dL",
        table_aliases=["urine glucose", "glucose (urine)", "ua glucose"],
        patterns=[
            rf"(?i)(?:urine|ua)\s+glucose{_SEP}{_NUM}\s*(?:mg\/dL)?",
        ],
        value_min=0.0,
        value_max=5000.0,
    ),
    MeasurementDef(
        name="Urine WBC",
        abbreviation="UA_WBC",
        unit="/HPF",
        table_aliases=["wbc (urine)", "urine wbc", "ua wbc"],
        patterns=[
            rf"(?i)(?:urine|ua)\s+WBC{_SEP}{_NUM}\s*(?:\/HPF|\/hpf)?",
        ],
        value_min=0.0,
        value_max=500.0,
    ),
    MeasurementDef(
        name="Urine RBC",
        abbreviation="UA_RBC",
        unit="/HPF",
        table_aliases=["rbc (urine)", "urine rbc", "ua rbc"],
        patterns=[
            rf"(?i)(?:urine|ua)\s+RBC{_SEP}{_NUM}\s*(?:\/HPF|\/hpf)?",
        ],
        value_min=0.0,
        value_max=500.0,
    ),
]

# Build a lookup: lowercase alias -> MeasurementDef
_ALIAS_LOOKUP: dict[str, MeasurementDef] = {}
for _mdef in MEASUREMENT_DEFS:
    for _alias in _mdef.table_aliases:
        _ALIAS_LOOKUP[_alias.lower()] = _mdef

# Header keywords that identify a lab-result table
_TABLE_HEADER_KEYWORDS = {"test", "result", "value", "units", "unit",
                          "reference", "range", "flag", "status", "analyte",
                          "component", "name"}


def _is_lab_table(headers: list[str]) -> bool:
    """Check if table headers look like a lab results table."""
    lower_headers = [h.lower().strip() for h in headers]
    matched = sum(1 for h in lower_headers
                  if any(kw in h for kw in _TABLE_HEADER_KEYWORDS))
    return matched >= 2


def _find_result_column(headers: list[str]) -> Optional[int]:
    """Find the column index that contains numeric results."""
    for i, h in enumerate(headers):
        hl = h.lower().strip()
        if hl in ("result", "value", "results", "values"):
            return i
    return None


# Patterns that identify a column header as a prior/historical value
_TEMPORAL_HEADER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)\d+\s*mo(?:nth)?s?\s*ago"),
    re.compile(r"(?i)\d+\s*yr?s?\s*ago"),
    re.compile(r"(?i)\d+\s*(?:week|wk)s?\s*ago"),
    re.compile(r"(?i)\d+\s*days?\s*ago"),
    re.compile(r"(?i)\bprevious\b"),
    re.compile(r"(?i)\bprior\b"),
    re.compile(r"(?i)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"),  # date formats
    re.compile(r"(?i)(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}"),
]


def _find_prior_columns(headers: list[str]) -> list[tuple[int, str]]:
    """Identify columns that contain prior/historical values.

    Returns a list of (column_index, time_label) tuples.
    """
    prior_cols: list[tuple[int, str]] = []
    for i, h in enumerate(headers):
        hl = h.strip()
        for pat in _TEMPORAL_HEADER_PATTERNS:
            if pat.search(hl):
                prior_cols.append((i, hl))
                break
    return prior_cols


def _match_row_to_analyte(row_name: str) -> Optional[MeasurementDef]:
    """Match a table row name to a known analyte definition."""
    normalized = row_name.lower().strip().rstrip(":")
    # Direct alias match
    if normalized in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[normalized]
    # Partial match: check if any alias is contained in the row name
    for alias, mdef in _ALIAS_LOOKUP.items():
        if alias in normalized:
            return mdef
    return None


def _extract_numeric(text: str) -> Optional[float]:
    """Extract first numeric value from a string."""
    m = re.search(r"(\d+\.?\d*)", text.strip())
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _extract_from_tables(
    tables: list[ExtractedTable],
) -> list[RawMeasurement]:
    """Extract measurements from structured PDF tables."""
    results: list[RawMeasurement] = []
    seen: set[str] = set()

    for table in tables:
        if not table.headers or not _is_lab_table(table.headers):
            continue

        result_col = _find_result_column(table.headers)
        prior_cols = _find_prior_columns(table.headers)
        prior_col_indices = {idx for idx, _ in prior_cols}

        for row in table.rows:
            if not row:
                continue
            row_name = row[0] if row else ""
            mdef = _match_row_to_analyte(row_name)
            if mdef is None or mdef.abbreviation in seen:
                continue

            # Try result column first, then scan all columns
            value: Optional[float] = None
            raw_text = " | ".join(row)

            if result_col is not None and result_col < len(row):
                value = _extract_numeric(row[result_col])
            if value is None:
                # Scan non-name, non-prior columns for a numeric value
                for i in range(1, len(row)):
                    if i in prior_col_indices:
                        continue
                    value = _extract_numeric(row[i])
                    if value is not None:
                        break

            if value is not None and mdef.value_min <= value <= mdef.value_max:
                # Extract prior values from temporal columns
                priors: list[PriorValueRaw] = []
                for col_idx, time_label in prior_cols:
                    if col_idx < len(row):
                        prior_val = _extract_numeric(row[col_idx])
                        if prior_val is not None and mdef.value_min <= prior_val <= mdef.value_max:
                            priors.append(PriorValueRaw(value=prior_val, time_label=time_label))

                results.append(
                    RawMeasurement(
                        name=mdef.name,
                        abbreviation=mdef.abbreviation,
                        value=value,
                        unit=mdef.unit,
                        raw_text=raw_text.strip(),
                        page_number=table.page_number,
                        prior_values=priors,
                    )
                )
                seen.add(mdef.abbreviation)

    return results


def _extract_from_text(
    full_text: str,
    pages: list[PageExtractionResult],
    seen: set[str],
) -> list[RawMeasurement]:
    """Extract measurements from raw text using regex patterns."""
    results: list[RawMeasurement] = []

    for mdef in MEASUREMENT_DEFS:
        if mdef.abbreviation in seen:
            continue

        for pattern in mdef.patterns:
            match = re.search(pattern, full_text)
            if match:
                try:
                    value = float(match.group("value"))
                except (ValueError, IndexError):
                    continue

                if not (mdef.value_min <= value <= mdef.value_max):
                    continue

                page_num = _find_page(match.group(), pages)
                results.append(
                    RawMeasurement(
                        name=mdef.name,
                        abbreviation=mdef.abbreviation,
                        value=value,
                        unit=mdef.unit,
                        raw_text=match.group().strip(),
                        page_number=page_num,
                    )
                )
                seen.add(mdef.abbreviation)
                break

    return results


def _find_page(
    snippet: str,
    pages: list[PageExtractionResult],
) -> Optional[int]:
    """Find which page contains the matched text snippet."""
    normalized = " ".join(snippet.split())
    for page in pages:
        page_normalized = " ".join(page.text.split())
        if normalized in page_normalized:
            return page.page_number
    return None


def _normalize_units(results: list[RawMeasurement]) -> list[RawMeasurement]:
    """Convert regional unit variants to standard units.

    - WBC_CUMM (/cumm absolute count) -> WBC (K/uL, divide by 1000)
    - PLT in Lakh/cumm -> PLT in K/uL (multiply by 100)
    """
    normalized: list[RawMeasurement] = []
    seen_canonical: set[str] = set()

    for m in results:
        if m.abbreviation == "WBC_CUMM":
            if "WBC" in seen_canonical:
                continue
            normalized.append(
                RawMeasurement(
                    name=m.name,
                    abbreviation="WBC",
                    value=round(m.value / 1000.0, 1),
                    unit="K/uL",
                    raw_text=m.raw_text,
                    page_number=m.page_number,
                )
            )
            seen_canonical.add("WBC")
        elif m.abbreviation == "WBC":
            if "WBC" in seen_canonical:
                continue
            normalized.append(m)
            seen_canonical.add("WBC")
        elif m.abbreviation == "PLT" and "lakh" in m.raw_text.lower():
            # Lakh/cumm: 1.89 Lakh = 189 K/uL
            normalized.append(
                RawMeasurement(
                    name=m.name,
                    abbreviation=m.abbreviation,
                    value=round(m.value * 100.0, 0),
                    unit="K/uL",
                    raw_text=m.raw_text,
                    page_number=m.page_number,
                )
            )
        else:
            normalized.append(m)

    return normalized


def extract_measurements(
    full_text: str,
    pages: list[PageExtractionResult],
    tables: list[ExtractedTable],
) -> list[RawMeasurement]:
    """Extract all recognized lab measurements using table-first, regex-fallback.

    1. Parse structured tables for analyte values (more reliable).
    2. Fall back to regex patterns on raw text for remaining analytes.
    3. Normalize regional unit variants to standard units.
    """
    # Strategy 1: table extraction
    table_results = _extract_from_tables(tables)

    # Track what was already found
    seen: set[str] = {m.abbreviation for m in table_results}

    # Strategy 2: regex fallback for remaining analytes
    text_results = _extract_from_text(full_text, pages, seen)

    combined = table_results + text_results

    # Strategy 3: normalize unit variants
    return _normalize_units(combined)
