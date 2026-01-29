"""Tests for the glossary API endpoint."""

from test_types.echo.handler import EchocardiogramHandler


class TestEchoGlossary:
    def test_glossary_returns_many_terms(self):
        handler = EchocardiogramHandler()
        glossary = handler.get_glossary()
        assert len(glossary) >= 30

    def test_glossary_values_are_non_empty_strings(self):
        handler = EchocardiogramHandler()
        glossary = handler.get_glossary()
        for term, definition in glossary.items():
            assert isinstance(term, str) and len(term) > 0
            assert isinstance(definition, str) and len(definition) > 0

    def test_key_terms_present(self):
        handler = EchocardiogramHandler()
        glossary = handler.get_glossary()
        assert "LVEF" in glossary
        assert "Ejection Fraction" in glossary
        assert "Left Ventricle" in glossary
        assert "Mitral Valve" in glossary
        assert "Aortic Valve" in glossary
        assert "Doppler" in glossary

    def test_glossary_response_structure(self):
        """Simulate what the endpoint returns."""
        handler = EchocardiogramHandler()
        response = {
            "test_type": handler.test_type_id,
            "glossary": handler.get_glossary(),
        }
        assert response["test_type"] == "echocardiogram"
        assert isinstance(response["glossary"], dict)
        assert len(response["glossary"]) >= 30
