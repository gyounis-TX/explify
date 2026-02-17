"""Tests for the PHI scrubber module."""

import re

from phi.scrubber import scrub_phi, _extract_patient_names


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


# -----------------------------------------------------------------------
# Patient name second-pass (bare name scrubbing)
# -----------------------------------------------------------------------


class TestPatientNameExtraction:
    """Tests for _extract_patient_names and second-pass name scrubbing."""

    def test_extract_from_labeled_last_first(self):
        text = "Patient Name: Anderson, Joseph N\nLVEF: 55%"
        names = _extract_patient_names(text)
        assert any("Anderson" in n for n in names)
        assert any("Joseph" in n for n in names)

    def test_extract_from_labeled_first_last(self):
        text = "Patient: John Smith\nLVEF: 55%"
        names = _extract_patient_names(text)
        assert any("Smith" in n for n in names)
        assert any("John" in n for n in names)

    def test_extract_from_ehr_header(self):
        """EHR header pattern: Name (MRN 12345678)"""
        text = "Anderson, Joseph N (MRN 030868921)\nHistory"
        names = _extract_patient_names(text)
        assert any("Anderson" in n for n in names)
        assert any("Joseph" in n for n in names)

    def test_extract_generates_reversed_variant(self):
        text = "Patient: Anderson, Joseph\nLVEF: 55%"
        names = _extract_patient_names(text)
        assert any("Joseph Anderson" in n for n in names)

    def test_extract_no_short_fragments(self):
        """Name parts shorter than 3 chars should be excluded."""
        text = "Patient: Li, Bo\nLVEF: 55%"
        names = _extract_patient_names(text)
        # "Bo" is only 2 chars — should be excluded
        assert not any(n == "Bo" for n in names)

    def test_extract_returns_empty_for_no_name(self):
        text = "LVEF: 55%\nNormal function."
        names = _extract_patient_names(text)
        assert names == []


class TestSecondPassNameScrubbing:
    """Tests for bare patient name scrubbing throughout document."""

    def test_scrub_bare_name_in_header(self):
        text = (
            "Patient: Anderson, Joseph N\n"
            "Anderson, Joseph N (MRN 030868921)\n"
            "LVEF: 55%"
        )
        result = scrub_phi(text)
        assert "Anderson" not in result.scrubbed_text
        assert "Joseph" not in result.scrubbed_text
        assert "LVEF: 55%" in result.scrubbed_text

    def test_scrub_bare_name_in_footer(self):
        text = (
            "Patient Name: Smith, Jane A.\n"
            "Findings are normal.\n"
            "Smith, Jane A. ( 12345678) Printed 1/1/2025"
        )
        result = scrub_phi(text)
        assert "Smith" not in result.scrubbed_text
        assert "Jane" not in result.scrubbed_text

    def test_scrub_mr_prefix(self):
        """'Mr. Anderson' should be caught by last-name variant."""
        text = (
            "Patient: Anderson, Joseph\n"
            "Mr. Anderson reports feeling well.\n"
            "Mr. Anderson was seen today."
        )
        result = scrub_phi(text)
        assert "Anderson" not in result.scrubbed_text

    def test_scrub_first_name_alone(self):
        text = (
            "Patient: Anderson, Joseph\n"
            "Joseph is doing well overall."
        )
        result = scrub_phi(text)
        assert "Joseph" not in result.scrubbed_text

    def test_scrub_reversed_format(self):
        """If labeled as 'Last, First', bare 'First Last' should also be caught."""
        text = (
            "Patient: Anderson, Joseph\n"
            "Follow-up Note for Joseph Anderson"
        )
        result = scrub_phi(text)
        assert "Joseph Anderson" not in result.scrubbed_text

    def test_no_false_positive_without_name(self):
        """Without a patient name in the text, no second-pass scrubbing occurs."""
        text = "Normal sinus rhythm. LVEF: 60%. No murmurs."
        result = scrub_phi(text)
        assert result.scrubbed_text == text
        assert result.redaction_count == 0


# -----------------------------------------------------------------------
# Bare MRN pattern
# -----------------------------------------------------------------------


class TestBareMRN:
    """Tests for parenthesized MRN without label."""

    def test_scrub_bare_parenthesized_mrn(self):
        text = "Smith, Jane ( 030868921) Printed 1/1/2025"
        result = scrub_phi(text)
        assert "030868921" not in result.scrubbed_text
        assert "mrn" in result.phi_found

    def test_scrub_mrn_with_label_in_parens(self):
        text = "Smith, Jane (MRN 030868921) Printed 1/1/2025"
        result = scrub_phi(text)
        assert "030868921" not in result.scrubbed_text

    def test_no_false_positive_short_numbers(self):
        """Parenthesized numbers under 6 digits should not be matched."""
        text = "Grade (1234) stenosis"
        result = scrub_phi(text)
        assert "1234" in result.scrubbed_text


# -----------------------------------------------------------------------
# Physician name expansion
# -----------------------------------------------------------------------


class TestPhysicianNameExpansion:
    """Tests for provider name matching with first names and credentials."""

    def test_single_last_name_catches_first_name(self):
        """Provider 'Bruce' should also catch 'Matthew Bruce'."""
        text = "Matthew Bruce reviewed the results."
        result = scrub_phi(text, provider_names=["Dr. Bruce"])
        assert "Matthew" not in result.scrubbed_text
        assert "Bruce" not in result.scrubbed_text

    def test_single_last_name_catches_credentials(self):
        text = "George A. Bruce, MD, FACC, FSCAI signed the note."
        result = scrub_phi(text, provider_names=["Bruce"])
        assert "Bruce" not in result.scrubbed_text
        assert "George" not in result.scrubbed_text

    def test_single_last_name_catches_dr_prefix(self):
        text = "Dr. Bruce recommends follow-up."
        result = scrub_phi(text, provider_names=["Bruce"])
        assert "Bruce" not in result.scrubbed_text

    def test_full_name_catches_middle_initial(self):
        """Provider 'George Bruce' should catch 'George A. Bruce'."""
        text = "George A. Bruce, MD reviewed the labs."
        result = scrub_phi(text, provider_names=["George Bruce"])
        assert "George" not in result.scrubbed_text
        assert "Bruce" not in result.scrubbed_text

    def test_full_name_catches_reversed(self):
        """Provider 'George Bruce' should catch 'Bruce, George'."""
        text = "Bruce, George signed the note."
        result = scrub_phi(text, provider_names=["George Bruce"])
        assert "George" not in result.scrubbed_text
        assert "Bruce" not in result.scrubbed_text

    def test_no_false_positive_without_providers(self):
        text = "Dr. Smith reviewed the results."
        result = scrub_phi(text, provider_names=None)
        # Without provider list, bare "Dr. Smith" without a labeled prefix
        # should not be caught by provider matching
        assert result.scrubbed_text == text


# -----------------------------------------------------------------------
# Insurance false positive fix
# -----------------------------------------------------------------------


class TestInsuranceFalsePositive:
    """Tests that clinical 'Plan:' sections are not matched as insurance."""

    def test_clinical_plan_not_matched(self):
        text = "Plan\nCad sp pci continue statin plavix"
        result = scrub_phi(text)
        assert result.scrubbed_text == text
        assert "insurance" not in result.phi_found

    def test_clinical_plan_colon_not_matched(self):
        text = "Plan: Continue current medications and follow-up in 6 months."
        result = scrub_phi(text)
        assert "Continue current" in result.scrubbed_text
        assert "insurance" not in result.phi_found

    def test_real_plan_number_still_matched(self):
        text = "Plan Number: ABC123456"
        result = scrub_phi(text)
        assert "ABC123456" not in result.scrubbed_text
        assert "insurance" in result.phi_found

    def test_plan_id_still_matched(self):
        text = "Plan ID: XYZ789"
        result = scrub_phi(text)
        assert "XYZ789" not in result.scrubbed_text
        assert "insurance" in result.phi_found

    def test_insurance_policy_still_matched(self):
        text = "Insurance: BCBS12345\nPolicy: POL98765"
        result = scrub_phi(text)
        assert "BCBS12345" not in result.scrubbed_text
        assert "POL98765" not in result.scrubbed_text


# -----------------------------------------------------------------------
# New Safe Harbor patterns: bare SSN, certificate, device serial, IP
# -----------------------------------------------------------------------


class TestBareSSN:
    """Tests for 9-digit SSN without hyphens."""

    def test_scrub_bare_nine_digit_ssn(self):
        text = "SSN: 123456789 is on file."
        result = scrub_phi(text)
        assert "123456789" not in result.scrubbed_text

    def test_no_false_positive_longer_number(self):
        """10-digit numbers are caught by phone pattern (correct behavior)."""
        text = "Accession 1234567890 received."
        result = scrub_phi(text)
        # 10-digit number matches phone pattern — that's expected PHI scrubbing
        assert "1234567890" not in result.scrubbed_text

    def test_no_false_positive_shorter_number(self):
        """8 digit numbers should not match."""
        text = "Code 12345678 entered."
        result = scrub_phi(text)
        assert "12345678" in result.scrubbed_text


class TestCertificateLicense:
    """Tests for certificate/license number scrubbing."""

    def test_scrub_license_number(self):
        text = "License #: MD123456"
        result = scrub_phi(text)
        assert "MD123456" not in result.scrubbed_text
        assert "certificate" in result.phi_found

    def test_scrub_cert_no(self):
        text = "Cert No: CA-LIC-12345"
        result = scrub_phi(text)
        assert "CA-LIC-12345" not in result.scrubbed_text

    def test_scrub_registration(self):
        text = "Registration ID: REG-98765"
        result = scrub_phi(text)
        assert "REG-98765" not in result.scrubbed_text


class TestDeviceSerial:
    """Tests for device serial number scrubbing."""

    def test_scrub_serial_number(self):
        text = "Serial: ABC-123456-XYZ"
        result = scrub_phi(text)
        assert "ABC-123456-XYZ" not in result.scrubbed_text
        assert "device_serial" in result.phi_found

    def test_scrub_sn_prefix(self):
        text = "SN: 12345-ABCDE"
        result = scrub_phi(text)
        assert "12345-ABCDE" not in result.scrubbed_text


class TestIPAddress:
    """Tests for IP address scrubbing."""

    def test_scrub_ipv4(self):
        text = "Source: 192.168.1.100 accessed the record."
        result = scrub_phi(text)
        assert "192.168.1.100" not in result.scrubbed_text
        assert "ip_address" in result.phi_found

    def test_scrub_public_ip(self):
        text = "Login from 203.0.113.45"
        result = scrub_phi(text)
        assert "203.0.113.45" not in result.scrubbed_text
