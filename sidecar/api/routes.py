import os
import tempfile

from fastapi import APIRouter, Body, File, HTTPException, Request, Response, UploadFile

from api.analysis_models import DetectTypeResponse, ParsedReport, ParseRequest
from api.explain_models import (
    AppSettings,
    ExplainRequest,
    ExplainResponse,
    SettingsUpdate,
)
from api.models import DetectionResult, ExtractionResult
from api import settings_store
from extraction import ExtractionPipeline
from extraction.detector import PDFDetector
from llm.client import LLMClient, LLMProvider
from llm.prompt_engine import LiteracyLevel, PromptEngine
from llm.response_parser import parse_and_validate_response
from llm.retry import LLMRetryError, with_retry
from llm.schemas import EXPLANATION_TOOL_NAME, EXPLANATION_TOOL_SCHEMA
from phi.scrubber import scrub_phi
from test_types import registry

router = APIRouter()

pipeline = ExtractionPipeline()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/extract/pdf", response_model=ExtractionResult)
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type: {file.content_type}. Expected application/pdf.",
        )

    tmp_path = None
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if not content[:4] == b"%PDF":
            raise HTTPException(
                status_code=400,
                detail="File does not appear to be a valid PDF.",
            )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        result = pipeline.extract_from_pdf(tmp_path)
        result.filename = file.filename
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract text from PDF: {str(e)}",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/extract/text", response_model=ExtractionResult)
async def extract_text(body: dict = Body(...)):
    text = body.get("text", "")
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text content is required and cannot be empty.",
        )
    return pipeline.extract_from_text(text)


@router.post("/detect", response_model=DetectionResult)
async def detect_pdf_type(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    tmp_path = None
    try:
        content = await file.read()
        if not content[:4] == b"%PDF":
            raise HTTPException(
                status_code=400,
                detail="File does not appear to be a valid PDF.",
            )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        detector = PDFDetector(tmp_path)
        return detector.detect()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to detect PDF type: {str(e)}",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/analyze/detect-type", response_model=DetectTypeResponse)
async def detect_test_type(body: dict = Body(...)):
    """Auto-detect the medical test type from extraction results."""
    try:
        extraction_result = ExtractionResult(**body)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extraction result: {str(e)}",
        )

    type_id, confidence = registry.detect(extraction_result)
    return DetectTypeResponse(
        test_type=type_id,
        confidence=round(confidence, 3),
        available_types=registry.list_types(),
    )


@router.post("/analyze/parse", response_model=ParsedReport)
async def parse_report(request: ParseRequest = Body(...)):
    """Parse extraction results into structured medical report."""
    try:
        extraction_result = ExtractionResult(**request.extraction_result)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extraction result: {str(e)}",
        )

    test_type = request.test_type
    if not test_type:
        type_id, confidence = registry.detect(extraction_result)
        if type_id is None or confidence < 0.2:
            raise HTTPException(
                status_code=422,
                detail="Could not determine the test type. Please specify test_type.",
            )
        test_type = type_id

    handler = registry.get(test_type)
    if handler is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown test type: {test_type}. "
            f"Available: {[t['test_type_id'] for t in registry.list_types()]}",
        )

    try:
        return handler.parse(extraction_result)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse report: {str(e)}",
        )


@router.post("/analyze/explain", response_model=ExplainResponse)
async def explain_report(request: ExplainRequest = Body(...)):
    """Full analysis pipeline: detect type -> parse -> PHI scrub -> LLM explain."""

    # 1. Parse extraction result
    try:
        extraction_result = ExtractionResult(**request.extraction_result)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extraction result: {str(e)}",
        )

    # 2. Detect test type
    test_type = request.test_type
    if not test_type:
        type_id, confidence = registry.detect(extraction_result)
        if type_id is None or confidence < 0.2:
            raise HTTPException(
                status_code=422,
                detail="Could not determine the test type. Please specify test_type.",
            )
        test_type = type_id

    handler = registry.get(test_type)
    if handler is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown test type: {test_type}",
        )

    # 3. Parse report
    try:
        parsed_report = handler.parse(extraction_result)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse report: {str(e)}",
        )

    # 4. Resolve API key
    settings = settings_store.get_settings()
    provider_str = request.provider.value
    api_key = request.api_key or settings_store.get_api_key_for_provider(
        provider_str
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No API key configured for provider '{provider_str}'. "
                f"Set it in Settings or pass api_key in the request."
            ),
        )

    # 5. PHI scrub
    scrub_result = scrub_phi(extraction_result.full_text)

    # 6. Build prompts
    literacy_level = LiteracyLevel(request.literacy_level.value)
    prompt_engine = PromptEngine()
    system_prompt = prompt_engine.build_system_prompt(
        literacy_level=literacy_level,
        prompt_context=handler.get_prompt_context(),
    )
    user_prompt = prompt_engine.build_user_prompt(
        parsed_report=parsed_report,
        reference_ranges=handler.get_reference_ranges(),
        glossary=handler.get_glossary(),
        scrubbed_text=scrub_result.scrubbed_text,
    )

    # 7. Call LLM with retry
    llm_provider = LLMProvider(provider_str)
    model_override = (
        settings.claude_model
        if provider_str == "claude"
        else settings.openai_model
    )
    client = LLMClient(
        provider=llm_provider,
        api_key=api_key,
        model=model_override,
    )

    try:
        llm_response = await with_retry(
            client.call_with_tool,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_name=EXPLANATION_TOOL_NAME,
            tool_schema=EXPLANATION_TOOL_SCHEMA,
            max_attempts=2,
        )
    except LLMRetryError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM API call failed after retries: {e.last_error}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM API call failed: {e}",
        )

    # 8. Parse and validate response
    try:
        explanation, issues = parse_and_validate_response(
            tool_result=llm_response.tool_call_result,
            parsed_report=parsed_report,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM response validation failed: {e}",
        )

    return ExplainResponse(
        explanation=explanation,
        parsed_report=parsed_report.model_dump(),
        validation_warnings=[issue.message for issue in issues],
        phi_categories_found=scrub_result.phi_found,
        model_used=llm_response.model,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
    )


@router.get("/glossary/{test_type}")
async def get_glossary(test_type: str):
    """Return glossary of medical terms for a given test type."""
    handler = registry.get(test_type)
    if handler is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown test type: {test_type}. "
            f"Available: {[t['test_type_id'] for t in registry.list_types()]}",
        )
    return {"test_type": test_type, "glossary": handler.get_glossary()}


@router.post("/export/pdf")
async def export_pdf(request: Request):
    """Generate a PDF report from an ExplainResponse."""
    try:
        from report_gen import render_pdf
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF export is not available: weasyprint is not installed.",
        )

    body = await request.json()

    try:
        pdf_bytes = render_pdf(body)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {e}",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="verba-report.pdf"'},
    )


def _mask_api_key(key: str | None) -> str | None:
    """Mask an API key for display, keeping first 8 and last 4 chars."""
    if not key or len(key) < 16:
        return key
    return key[:8] + "..." + key[-4:]


@router.get("/settings", response_model=AppSettings)
async def get_settings():
    """Return current application settings with masked API keys."""
    settings = settings_store.get_settings()
    settings.claude_api_key = _mask_api_key(settings.claude_api_key)
    settings.openai_api_key = _mask_api_key(settings.openai_api_key)
    return settings


@router.patch("/settings", response_model=AppSettings)
async def update_settings(update: SettingsUpdate = Body(...)):
    """Update application settings (partial update)."""
    updated = settings_store.update_settings(update)
    updated.claude_api_key = _mask_api_key(updated.claude_api_key)
    updated.openai_api_key = _mask_api_key(updated.openai_api_key)
    return updated
