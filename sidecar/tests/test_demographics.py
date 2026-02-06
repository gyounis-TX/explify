"""Integration tests for demographics extraction."""

import pytest
from extraction.demographics import extract_demographics, Demographics


class TestAgeExtraction:
    """Test age extraction from various formats."""

    def test_age_explicit_label(self):
        """Test 'Age: 45' format."""
        result = extract_demographics("Patient Report\nAge: 45\nSex: M")
        assert result.age == 45

    def test_age_slash_sex_format(self):
        """Test 'Age/Sex: 45/M' format."""
        result = extract_demographics("Age/Sex: 65/F")
        assert result.age == 65

    def test_age_yo_format(self):
        """Test '45 yo' format."""
        result = extract_demographics("This is a 72 yo male presenting with...")
        assert result.age == 72

    def test_age_year_old_format(self):
        """Test '45-year-old' format."""
        result = extract_demographics("A 58-year-old female patient")
        assert result.age == 58

    def test_age_years_old_format(self):
        """Test '45 years old' format."""
        result = extract_demographics("The patient is 42 years old")
        assert result.age == 42

    def test_age_compact_format(self):
        """Test '45M' compact format."""
        result = extract_demographics("Patient: John Doe\n65M\nMRN: 12345")
        assert result.age == 65

    def test_age_with_slash(self):
        """Test '45/M' format."""
        result = extract_demographics("Patient info: 55/F")
        assert result.age == 55

    def test_age_invalid_too_high(self):
        """Test that ages over 120 are rejected."""
        result = extract_demographics("Age: 150")
        assert result.age is None

    def test_no_age_found(self):
        """Test when no age is present."""
        result = extract_demographics("Normal echocardiogram findings")
        assert result.age is None


class TestGenderExtraction:
    """Test gender extraction from various formats."""

    def test_gender_explicit_male(self):
        """Test 'Sex: M' format."""
        result = extract_demographics("Age: 45\nSex: M")
        assert result.gender == "Male"

    def test_gender_explicit_female(self):
        """Test 'Sex: Female' format."""
        result = extract_demographics("Gender: Female")
        assert result.gender == "Female"

    def test_gender_in_age_string(self):
        """Test '45 yo male' format."""
        result = extract_demographics("A 72 yo female patient")
        assert result.gender == "Female"

    def test_gender_compact_male(self):
        """Test '45M' format extracts male."""
        result = extract_demographics("Patient: 65M")
        assert result.gender == "Male"

    def test_gender_compact_female(self):
        """Test '45F' format extracts female."""
        result = extract_demographics("Patient: 55F")
        assert result.gender == "Female"

    def test_gender_with_slash(self):
        """Test 'Age/Sex: 45/F' format."""
        result = extract_demographics("Age/Sex: 45/F")
        assert result.gender == "Female"

    def test_no_gender_found(self):
        """Test when no gender is present."""
        result = extract_demographics("Age: 45\nNormal findings")
        assert result.gender is None


class TestCombinedExtraction:
    """Test extraction of both age and gender."""

    def test_combined_slash_format(self):
        """Test 'Age/Sex: 45/M' extracts both."""
        result = extract_demographics("Age/Sex: 68/M\nIndication: Chest pain")
        assert result.age == 68
        assert result.gender == "Male"

    def test_combined_yo_format(self):
        """Test '45 yo male' extracts both."""
        result = extract_demographics("This is a 55 yo female with hypertension")
        assert result.age == 55
        assert result.gender == "Female"

    def test_combined_year_old_format(self):
        """Test '45 year old male' extracts both."""
        result = extract_demographics("A 62 year old male presenting with syncope")
        assert result.age == 62
        assert result.gender == "Male"

    def test_real_report_header(self):
        """Test extraction from realistic report header."""
        report = """
        ECHOCARDIOGRAM REPORT
        Patient: Smith, John
        Age/Sex: 73/M
        DOB: 01/15/1951
        MRN: 123456

        INDICATION: Shortness of breath
        """
        result = extract_demographics(report)
        assert result.age == 73
        assert result.gender == "Male"

    def test_empty_text(self):
        """Test empty text returns empty demographics."""
        result = extract_demographics("")
        assert result.age is None
        assert result.gender is None

    def test_none_text(self):
        """Test None text returns empty demographics."""
        result = extract_demographics(None)  # type: ignore
        assert result.age is None
        assert result.gender is None
