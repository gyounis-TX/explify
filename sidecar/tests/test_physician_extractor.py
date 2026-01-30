"""Tests for extraction.physician_extractor."""

import pytest
from extraction.physician_extractor import extract_physician_name


class TestExtractPhysicianName:
    def test_referred_by(self):
        text = "Referred by: Dr. John Smith, MD"
        assert extract_physician_name(text) == "Dr. Smith"

    def test_referring_physician(self):
        text = "Referring Physician: Jane Doe, DO"
        assert extract_physician_name(text) == "Dr. Doe"

    def test_ordering_physician(self):
        text = "Ordering Physician: Robert Johnson"
        assert extract_physician_name(text) == "Dr. Johnson"

    def test_ordered_by(self):
        text = "Ordered by: Dr. Alice Williams NP"
        assert extract_physician_name(text) == "Dr. Williams"

    def test_referring_provider(self):
        text = "Referring Provider: Michael Brown PA"
        assert extract_physician_name(text) == "Dr. Brown"

    def test_attending_physician(self):
        text = "Attending Physician: Dr. Sarah Davis"
        assert extract_physician_name(text) == "Dr. Davis"

    def test_requesting_physician(self):
        text = "Requesting Physician: Dr. Emily Clark MD"
        assert extract_physician_name(text) == "Dr. Clark"

    def test_primary_care_physician(self):
        text = "Primary Care Physician: Thomas Anderson"
        assert extract_physician_name(text) == "Dr. Anderson"

    def test_clinician(self):
        text = "Clinician: Dr. Patricia Martinez"
        assert extract_physician_name(text) == "Dr. Martinez"

    def test_middle_initial(self):
        text = "Referring Physician: James R. Wilson, MD"
        assert extract_physician_name(text) == "Dr. Wilson"

    def test_hyphenated_name(self):
        text = "Ordering Physician: Dr. Maria Garcia-Lopez"
        assert extract_physician_name(text) == "Dr. Garcia-Lopez"

    def test_case_insensitive(self):
        text = "REFERRED BY: DR. PETER CHANG, MD"
        assert extract_physician_name(text) == "Dr. Chang"

    def test_case_insensitive_lower(self):
        text = "referred by: dr. peter chang"
        assert extract_physician_name(text) == "Dr. Chang"

    def test_no_match(self):
        text = "This report does not mention any physician labels."
        assert extract_physician_name(text) is None

    def test_empty_string(self):
        assert extract_physician_name("") is None

    def test_none_input(self):
        assert extract_physician_name(None) is None

    def test_colon_separator(self):
        text = "Referring Physician: Dr. Mark Taylor MD"
        assert extract_physician_name(text) == "Dr. Taylor"

    def test_dash_separator(self):
        text = "Ordering Physician - Karen Lee, DO"
        assert extract_physician_name(text) == "Dr. Lee"

    def test_single_name_becomes_dr(self):
        text = "Referring Physician: younis"
        assert extract_physician_name(text) == "Dr. Younis"

    def test_age_boundary(self):
        text = "Referring Physician: Younis age 45"
        assert extract_physician_name(text) == "Dr. Younis"

    def test_age_boundary_with_prefix(self):
        text = "Ordering Physician: Dr. John Smith age 52 male"
        assert extract_physician_name(text) == "Dr. Smith"

    def test_embedded_in_report(self):
        text = (
            "COMPLETE BLOOD COUNT\n"
            "Patient: [REDACTED]\n"
            "Ordering Physician: Dr. Steven Hall, MD\n"
            "Date: 2024-01-15\n"
            "Results:\n"
            "WBC: 6.5 x10^3/uL\n"
        )
        assert extract_physician_name(text) == "Dr. Hall"
