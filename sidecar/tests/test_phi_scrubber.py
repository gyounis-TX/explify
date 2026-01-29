"""Tests for the PHI scrubber module."""

from phi.scrubber import scrub_phi


class TestPHIScrubber:
    def test_scrub_patient_name(self):
        text = "Patient: John Smith\nLVEF: 55%"
        result = scrub_phi(text)
        assert "John Smith" not in result.scrubbed_text
        assert "[PATIENT NAME REDACTED]" in result.scrubbed_text
        assert "patient_name" in result.phi_found
        assert "LVEF: 55%" in result.scrubbed_text

    def test_scrub_dob(self):
        text = "DOB: 01/15/1980\nLVIDd: 4.8 cm"
        result = scrub_phi(text)
        assert "01/15/1980" not in result.scrubbed_text
        assert "[DOB REDACTED]" in result.scrubbed_text
        assert "dob" in result.phi_found

    def test_scrub_mrn(self):
        text = "MRN: 12345678\nIVSd: 1.0 cm"
        result = scrub_phi(text)
        assert "12345678" not in result.scrubbed_text
        assert "[MRN REDACTED]" in result.scrubbed_text
        assert "mrn" in result.phi_found

    def test_scrub_ssn(self):
        text = "SSN: 123-45-6789\nFS: 33%"
        result = scrub_phi(text)
        assert "123-45-6789" not in result.scrubbed_text
        assert "[SSN REDACTED]" in result.scrubbed_text
        assert "ssn" in result.phi_found

    def test_scrub_phone(self):
        text = "Phone: (555) 123-4567\nRVSP: 30 mmHg"
        result = scrub_phi(text)
        assert "(555) 123-4567" not in result.scrubbed_text
        assert "phone" in result.phi_found

    def test_scrub_address(self):
        text = "Address: 123 Main Street\nLA diameter: 3.6 cm"
        result = scrub_phi(text)
        assert "123 Main Street" not in result.scrubbed_text
        assert "address" in result.phi_found

    def test_preserves_medical_data(self):
        text = (
            "LVEF: 55%\n"
            "LVIDd: 4.8 cm\n"
            "IVSd: 1.0 cm\n"
            "RVSP: 30 mmHg\n"
            "E/A ratio: 1.2\n"
            "LA Volume Index: 28 mL/m2"
        )
        result = scrub_phi(text)
        assert result.scrubbed_text == text
        assert result.redaction_count == 0
        assert len(result.phi_found) == 0

    def test_no_phi_returns_unchanged(self):
        text = "Normal left ventricular systolic function."
        result = scrub_phi(text)
        assert result.scrubbed_text == text
        assert result.redaction_count == 0

    def test_multiple_phi_types(self):
        text = (
            "Patient: Jane Doe\n"
            "DOB: 03/22/1975\n"
            "MRN: ABC12345\n"
            "LVEF: 60%"
        )
        result = scrub_phi(text)
        assert "Jane Doe" not in result.scrubbed_text
        assert "03/22/1975" not in result.scrubbed_text
        assert "ABC12345" not in result.scrubbed_text
        assert "LVEF: 60%" in result.scrubbed_text
        assert result.redaction_count >= 3
        assert len(result.phi_found) >= 3
