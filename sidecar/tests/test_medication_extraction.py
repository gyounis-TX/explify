"""Integration tests for medication extraction from clinical context."""

import pytest
from llm.prompt_engine import (
    _extract_medications_from_context,
    _build_medication_guidance,
)


class TestMedicationExtraction:
    """Test medication class detection from clinical context."""

    def test_beta_blocker_metoprolol(self):
        """Test detection of metoprolol as beta blocker."""
        result = _extract_medications_from_context("Patient on metoprolol 25mg daily")
        assert "beta_blockers" in result

    def test_beta_blocker_carvedilol(self):
        """Test detection of carvedilol as beta blocker."""
        result = _extract_medications_from_context("Takes carvedilol 6.25mg BID")
        assert "beta_blockers" in result

    def test_ace_inhibitor_lisinopril(self):
        """Test detection of lisinopril as ACE inhibitor."""
        result = _extract_medications_from_context("Medications: lisinopril 10mg")
        assert "ace_arb" in result

    def test_arb_losartan(self):
        """Test detection of losartan as ARB."""
        result = _extract_medications_from_context("On losartan 50mg for HTN")
        assert "ace_arb" in result

    def test_statin_atorvastatin(self):
        """Test detection of atorvastatin as statin."""
        result = _extract_medications_from_context("Taking atorvastatin 40mg")
        assert "statins" in result

    def test_statin_brand_name(self):
        """Test detection of Lipitor (brand name for atorvastatin)."""
        result = _extract_medications_from_context("Currently on Lipitor 20mg")
        assert "statins" in result

    def test_diuretic_furosemide(self):
        """Test detection of furosemide as diuretic."""
        result = _extract_medications_from_context("Lasix 40mg daily")
        assert "diuretics" in result

    def test_anticoagulant_warfarin(self):
        """Test detection of warfarin as anticoagulant."""
        result = _extract_medications_from_context("On coumadin, INR monitoring")
        assert "anticoagulants" in result

    def test_anticoagulant_doac(self):
        """Test detection of apixaban (DOAC) as anticoagulant."""
        result = _extract_medications_from_context("Takes Eliquis 5mg BID for AFib")
        assert "anticoagulants" in result

    def test_antiplatelet_aspirin(self):
        """Test detection of aspirin as antiplatelet."""
        result = _extract_medications_from_context("Daily aspirin 81mg")
        assert "antiplatelets" in result

    def test_antiplatelet_plavix(self):
        """Test detection of Plavix as antiplatelet."""
        result = _extract_medications_from_context("On Plavix post-stent")
        assert "antiplatelets" in result

    def test_thyroid_med(self):
        """Test detection of levothyroxine."""
        result = _extract_medications_from_context("Synthroid 75mcg for hypothyroidism")
        assert "thyroid_meds" in result

    def test_diabetes_med_metformin(self):
        """Test detection of metformin."""
        result = _extract_medications_from_context("Metformin 1000mg BID")
        assert "diabetes_meds" in result

    def test_diabetes_med_sglt2(self):
        """Test detection of SGLT2 inhibitor."""
        result = _extract_medications_from_context("Recently started Jardiance")
        assert "diabetes_meds" in result

    def test_diabetes_med_glp1(self):
        """Test detection of GLP-1 agonist."""
        result = _extract_medications_from_context("Using Ozempic weekly for T2DM")
        assert "diabetes_meds" in result

    def test_steroid_prednisone(self):
        """Test detection of prednisone."""
        result = _extract_medications_from_context("Prednisone 10mg for RA flare")
        assert "steroids" in result

    def test_nsaid(self):
        """Test detection of NSAIDs."""
        result = _extract_medications_from_context("Takes ibuprofen PRN for pain")
        assert "nsaids" in result

    def test_ppi(self):
        """Test detection of PPI."""
        result = _extract_medications_from_context("Omeprazole 20mg daily for GERD")
        assert "proton_pump_inhibitors" in result

    def test_antidepressant_ssri(self):
        """Test detection of SSRI."""
        result = _extract_medications_from_context("Sertraline 50mg for depression")
        assert "antidepressants" in result

    def test_multiple_medications(self):
        """Test detection of multiple medication classes."""
        context = """
        PMH: HTN, HLD, T2DM, AFib
        Medications:
        - Metoprolol 50mg BID
        - Lisinopril 20mg daily
        - Atorvastatin 40mg HS
        - Metformin 1000mg BID
        - Eliquis 5mg BID
        """
        result = _extract_medications_from_context(context)
        assert "beta_blockers" in result
        assert "ace_arb" in result
        assert "statins" in result
        assert "diabetes_meds" in result
        assert "anticoagulants" in result

    def test_no_medications_found(self):
        """Test when no medications are in the context."""
        result = _extract_medications_from_context("Patient presents with chest pain")
        assert result == []

    def test_empty_context(self):
        """Test empty context returns empty list."""
        result = _extract_medications_from_context("")
        assert result == []

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        result = _extract_medications_from_context("METOPROLOL 25MG")
        assert "beta_blockers" in result


class TestMedicationGuidance:
    """Test medication guidance generation."""

    def test_guidance_for_beta_blockers(self):
        """Test guidance includes beta blocker info."""
        guidance = _build_medication_guidance(["beta_blockers"])
        assert "beta blockers" in guidance.lower()
        assert "heart rate" in guidance.lower()

    def test_guidance_for_statins(self):
        """Test guidance includes statin info."""
        guidance = _build_medication_guidance(["statins"])
        assert "statin" in guidance.lower()
        assert "transaminase" in guidance.lower() or "alt" in guidance.lower()

    def test_guidance_for_multiple_classes(self):
        """Test guidance includes all detected classes."""
        guidance = _build_medication_guidance(["beta_blockers", "ace_arb", "diuretics"])
        assert "beta blockers" in guidance.lower()
        assert "ace" in guidance.lower() or "arb" in guidance.lower()
        assert "diuretic" in guidance.lower()

    def test_guidance_empty_list(self):
        """Test empty medication list returns empty guidance."""
        guidance = _build_medication_guidance([])
        assert guidance == ""

    def test_guidance_has_header(self):
        """Test guidance includes section header."""
        guidance = _build_medication_guidance(["statins"])
        assert "Medication Considerations" in guidance


class TestRealWorldScenarios:
    """Test realistic clinical context scenarios."""

    def test_office_note_with_medications(self):
        """Test extraction from a realistic office note."""
        note = """
        HISTORY OF PRESENT ILLNESS:
        65 yo male with HTN, HLD, and CAD s/p 2 stents in 2020 presents
        for routine follow-up. Patient reports doing well, no chest pain
        or shortness of breath.

        PAST MEDICAL HISTORY:
        1. Hypertension
        2. Hyperlipidemia
        3. Coronary artery disease s/p PCI 2020
        4. Type 2 diabetes mellitus

        MEDICATIONS:
        1. Aspirin 81mg daily
        2. Clopidogrel 75mg daily
        3. Metoprolol succinate 100mg daily
        4. Lisinopril 20mg daily
        5. Atorvastatin 80mg HS
        6. Metformin 1000mg BID
        7. Omeprazole 20mg daily

        ALLERGIES: NKDA
        """
        result = _extract_medications_from_context(note)

        # Should detect multiple classes
        assert "antiplatelets" in result  # aspirin, clopidogrel
        assert "beta_blockers" in result  # metoprolol
        assert "ace_arb" in result  # lisinopril
        assert "statins" in result  # atorvastatin
        assert "diabetes_meds" in result  # metformin
        assert "proton_pump_inhibitors" in result  # omeprazole

    def test_brief_medication_list(self):
        """Test extraction from brief medication mention."""
        context = "Meds: metoprolol, lisinopril, atorvastatin"
        result = _extract_medications_from_context(context)
        assert "beta_blockers" in result
        assert "ace_arb" in result
        assert "statins" in result
