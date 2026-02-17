"""Tests for the Quick Normal text-based exclusion patterns."""

import re
import sys
import os

# Add sidecar to path so we can import routes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.routes import _ABNORMAL_TEXT_PATTERNS


class TestAbnormalTextPatterns:
    """Reports with these patterns should NOT get Quick Normal."""

    # -- Dilated structures --

    def test_dilated_ascending_aorta(self):
        text = "The ascending aorta is mildly dilated. Dilated ascending aorta measuring 4.2 cm."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_dilated_aortic_root(self):
        text = "Findings: Dilated aortic root at 4.0 cm."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_dilated_atrium(self):
        text = "The left atrium is dilated. Dilated atrium noted."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_dilated_ventricle(self):
        text = "Dilated ventricle with preserved systolic function."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    # -- Comparison with prior study --

    def test_compared_with_prior_study(self):
        text = "Compared with the prior study dated 1/1/2025, the EF is unchanged."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_compared_to_previous_echocardiogram(self):
        text = "Compared to previous echocardiogram, no significant changes."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_compared_with_prior_exam(self):
        text = "Compared with prior exam from March 2025."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_compared_to_prior_echo(self):
        text = "Compared to the prior echo, the LVEF has decreased."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    # -- Worsening / increasing language --

    def test_has_increased(self):
        text = "The pericardial effusion has increased in size."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_has_worsened(self):
        text = "Mitral regurgitation has worsened from mild to moderate."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_has_deteriorated(self):
        text = "Left ventricular function has deteriorated."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_interval_increase(self):
        text = "Interval increase in left atrial size noted."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_interval_worsening(self):
        text = "There is interval worsening of the tricuspid regurgitation."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_since_prior_progression(self):
        text = "Since prior study, there has been progression of aortic stenosis."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_worse_compared_prior(self):
        text = "RV function is worse compared to prior."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_increased_since_previous(self):
        text = "RVSP has increased since previous examination."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    # -- New findings --

    def test_new_pericardial_effusion(self):
        text = "New pericardial effusion is present."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_new_wall_motion_abnormality(self):
        text = "New wall motion abnormality in the anterior wall."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_new_finding(self):
        text = "New finding of moderate aortic regurgitation."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)

    def test_new_pleural_effusion(self):
        text = "New pleural effusion on the right side."
        assert _ABNORMAL_TEXT_PATTERNS.search(text)


class TestNormalReportsShouldPass:
    """Normal reports without these patterns should NOT match."""

    def test_clean_normal_echo(self):
        text = """ECHOCARDIOGRAM
        LVEF: 60%. Normal LV size and function.
        No valvular abnormalities. Normal diastolic function.
        Impression: Normal echocardiogram."""
        assert _ABNORMAL_TEXT_PATTERNS.search(text) is None

    def test_normal_with_measurements(self):
        text = """LVIDd: 4.5 cm. IVSd: 1.0 cm. LVEF: 55-60%.
        Normal left ventricular size and systolic function.
        Trace mitral regurgitation. No pericardial effusion."""
        assert _ABNORMAL_TEXT_PATTERNS.search(text) is None

    def test_prior_in_non_comparison_context(self):
        """'Prior' used without comparison language should not match."""
        text = "No prior cardiac surgery. LVEF 60%."
        assert _ABNORMAL_TEXT_PATTERNS.search(text) is None

    def test_normal_word_should_not_match(self):
        text = "All findings are within normal limits."
        assert _ABNORMAL_TEXT_PATTERNS.search(text) is None
