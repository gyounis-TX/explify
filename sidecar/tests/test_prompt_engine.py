"""Integration tests for prompt engine."""

import pytest
from llm.prompt_engine import (
    PromptEngine,
    LiteracyLevel,
    _extract_indication_from_report,
    _select_domain_knowledge,
)


class TestIndicationExtraction:
    """Test extraction of study indication from report text."""

    def test_indication_colon_format(self):
        """Test 'Indication: reason' format."""
        text = "ECHOCARDIOGRAM\nIndication: Chest pain\nFindings: Normal"
        result = _extract_indication_from_report(text)
        assert result == "Chest pain"

    def test_indication_plural(self):
        """Test 'Indications:' format."""
        text = "Indications: Shortness of breath and fatigue"
        result = _extract_indication_from_report(text)
        assert result == "Shortness of breath and fatigue"

    def test_reason_for_study(self):
        """Test 'Reason for study:' format."""
        text = "Reason for study: Evaluate LV function"
        result = _extract_indication_from_report(text)
        assert result == "Evaluate LV function"

    def test_reason_for_exam(self):
        """Test 'Reason for exam:' format."""
        text = "Reason for exam: Rule out aortic stenosis"
        result = _extract_indication_from_report(text)
        assert result == "Rule out aortic stenosis"

    def test_clinical_indication(self):
        """Test 'Clinical indication:' format."""
        text = "Clinical indication: Palpitations"
        result = _extract_indication_from_report(text)
        assert result == "Palpitations"

    def test_clinical_history(self):
        """Test 'Clinical history:' format."""
        text = "Clinical history: Known HCM, annual follow-up"
        result = _extract_indication_from_report(text)
        assert result == "Known HCM, annual follow-up"

    def test_reason_for_referral(self):
        """Test 'Reason for referral:' format."""
        text = "Reason for referral: New heart murmur"
        result = _extract_indication_from_report(text)
        assert result == "New heart murmur"

    def test_indication_none(self):
        """Test that 'None' indication returns None."""
        text = "Indication: None\nFindings: Normal"
        result = _extract_indication_from_report(text)
        assert result is None

    def test_indication_na(self):
        """Test that 'N/A' indication returns None."""
        text = "Indication: N/A"
        result = _extract_indication_from_report(text)
        assert result is None

    def test_no_indication(self):
        """Test when no indication is present."""
        text = "ECHOCARDIOGRAM REPORT\nPatient: John Doe\nFindings: Normal"
        result = _extract_indication_from_report(text)
        assert result is None

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        text = "INDICATION: DYSPNEA ON EXERTION"
        result = _extract_indication_from_report(text)
        assert result == "DYSPNEA ON EXERTION"


class TestDomainKnowledgeSelection:
    """Test selection of appropriate domain knowledge based on test type."""

    def test_lab_category(self):
        """Test lab category selects lab domain knowledge."""
        context = {"category": "lab"}
        result = _select_domain_knowledge(context)
        assert "iron deficiency" in result.lower() or "thyroid" in result.lower()

    def test_lab_test_type(self):
        """Test lab test type selects lab domain knowledge."""
        context = {"test_type": "lab_results"}
        result = _select_domain_knowledge(context)
        assert "iron deficiency" in result.lower() or "thyroid" in result.lower()

    def test_cardiac_category(self):
        """Test cardiac category selects cardiac domain knowledge."""
        context = {"category": "cardiac"}
        result = _select_domain_knowledge(context)
        assert "hypertrophic cardiomyopathy" in result.lower() or "hcm" in result.lower()

    def test_imaging_category(self):
        """Test imaging category selects imaging domain knowledge."""
        context = {"category": "imaging_ct"}
        result = _select_domain_knowledge(context)
        assert "anatomical" in result.lower() or "incidental" in result.lower()

    def test_ekg_test_type(self):
        """Test EKG test type selects EKG domain knowledge."""
        context = {"test_type": "ekg"}
        result = _select_domain_knowledge(context)
        assert "rhythm" in result.lower() or "qtc" in result.lower()

    def test_pft_test_type(self):
        """Test PFT test type selects PFT domain knowledge."""
        context = {"test_type": "pft"}
        result = _select_domain_knowledge(context)
        assert "obstructive" in result.lower() or "fev1" in result.lower()

    def test_default_to_cardiac(self):
        """Test unknown category defaults to cardiac."""
        context = {"category": "unknown"}
        result = _select_domain_knowledge(context)
        assert "hypertrophic cardiomyopathy" in result.lower() or "hcm" in result.lower()

    def test_interpretation_rules_appended(self):
        """Test handler interpretation rules are appended."""
        context = {
            "category": "cardiac",
            "interpretation_rules": "Custom rule: Always mention LVEF first",
        }
        result = _select_domain_knowledge(context)
        assert "Custom rule: Always mention LVEF first" in result


class TestSystemPromptConstruction:
    """Test system prompt construction."""

    def test_basic_system_prompt(self):
        """Test basic system prompt construction."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
        )
        assert "cardiology" in prompt.lower()
        assert "8th-grade" in prompt.lower() or "grade 8" in prompt.lower()

    def test_system_prompt_with_demographics_male(self):
        """Test system prompt includes male demographics guidance."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            patient_age=55,
            patient_gender="Male",
        )
        assert "Male" in prompt
        assert "55" in prompt
        assert "male-specific" in prompt.lower()

    def test_system_prompt_with_demographics_female(self):
        """Test system prompt includes female demographics guidance."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            patient_age=45,
            patient_gender="Female",
        )
        assert "Female" in prompt
        assert "female-specific" in prompt.lower()

    def test_system_prompt_geriatric(self):
        """Test geriatric patient guidance."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "internal medicine"},
            patient_age=75,
        )
        assert "geriatric" in prompt.lower() or "65+" in prompt

    def test_system_prompt_pediatric(self):
        """Test pediatric patient guidance."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "pediatric cardiology"},
            patient_age=12,
        )
        assert "pediatric" in prompt.lower()

    def test_short_comment_prompt(self):
        """Test short comment mode produces shorter prompt."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            short_comment=True,
            short_comment_char_limit=1000,
        )
        assert "condensed" in prompt.lower()
        assert "1000" in prompt or "900" in prompt  # Target is 90% of limit

    def test_sms_summary_prompt(self):
        """Test SMS summary mode produces ultra-short prompt."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            sms_summary=True,
            sms_summary_char_limit=300,
        )
        assert "sms" in prompt.lower() or "ultra-condensed" in prompt.lower()
        assert "300" in prompt or "270" in prompt  # Target is 90% of limit

    def test_first_person_voice(self):
        """Test first person voice instructions."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            explanation_voice="first_person",
        )
        assert "first person" in prompt.lower()

    def test_third_person_voice_with_physician(self):
        """Test third person voice with physician name."""
        engine = PromptEngine()
        prompt = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            explanation_voice="third_person",
            physician_name="Dr. Smith",
        )
        assert "Dr. Smith" in prompt

    def test_tone_preference(self):
        """Test tone preference is included."""
        engine = PromptEngine()
        prompt_reassuring = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            tone_preference=5,
        )
        prompt_direct = engine.build_system_prompt(
            literacy_level=LiteracyLevel.GRADE_8,
            prompt_context={"specialty": "cardiology"},
            tone_preference=1,
        )
        assert "reassuring" in prompt_reassuring.lower() or "warm" in prompt_reassuring.lower()
        assert "direct" in prompt_direct.lower() or "clinical" in prompt_direct.lower()


class TestUserPromptConstruction:
    """Test user prompt construction."""

    def test_user_prompt_includes_clinical_context(self):
        """Test clinical context is included in user prompt."""
        from api.analysis_models import ParsedReport
        engine = PromptEngine()

        parsed_report = ParsedReport(
            test_type="echo",
            test_type_display="Echocardiogram",
            detection_confidence=1.0,
            measurements=[],
            findings=[],
            sections=[],
        )

        prompt = engine.build_user_prompt(
            parsed_report=parsed_report,
            reference_ranges={},
            glossary={},
            scrubbed_text="Normal echocardiogram",
            clinical_context="Patient with chest pain and shortness of breath",
        )

        assert "chest pain" in prompt.lower()
        assert "shortness of breath" in prompt.lower()

    def test_user_prompt_extracts_indication(self):
        """Test indication is extracted from report when no clinical context."""
        from api.analysis_models import ParsedReport
        engine = PromptEngine()

        parsed_report = ParsedReport(
            test_type="echo",
            test_type_display="Echocardiogram",
            detection_confidence=1.0,
            measurements=[],
            findings=[],
            sections=[],
        )

        prompt = engine.build_user_prompt(
            parsed_report=parsed_report,
            reference_ranges={},
            glossary={},
            scrubbed_text="Indication: Evaluate murmur\nFindings: Normal study",
            clinical_context=None,
        )

        assert "evaluate murmur" in prompt.lower()

    def test_user_prompt_includes_medication_guidance(self):
        """Test medication guidance is included when meds detected."""
        from api.analysis_models import ParsedReport
        engine = PromptEngine()

        parsed_report = ParsedReport(
            test_type="echo",
            test_type_display="Echocardiogram",
            detection_confidence=1.0,
            measurements=[],
            findings=[],
            sections=[],
        )

        prompt = engine.build_user_prompt(
            parsed_report=parsed_report,
            reference_ranges={},
            glossary={},
            scrubbed_text="Normal echocardiogram",
            clinical_context="Patient on metoprolol 50mg, lisinopril 20mg",
        )

        assert "medication considerations" in prompt.lower()
        assert "beta blocker" in prompt.lower()
