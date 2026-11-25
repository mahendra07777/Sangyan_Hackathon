from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from ..services.document_processor import DocumentProcessor, SingleDocConsentManager
from ..services.chat_service import ChatService
from ..models.document import (
    DocumentProcessResult,
    DocumentIntelligence,
    ConsentPreviewRequest,
    ConsentPreviewResponse,
    ConsentConfirmRequest,
    ConsentConfirmResponse,
    AIAnalyzeRequest,
    AISessionPreviewResponse,
    AISessionActivateRequest,
    AISessionActivateResponse,
    AISessionCredentialsRequest,
    AISessionStatusResponse,
)
from ..models.chat import ChatRequest, ChatResponse

router = APIRouter()


class TranslateRequest(BaseModel):
    intelligence: DocumentIntelligence
    language: str
    mode: str = "local"
    challenge_id: Optional[str] = None
    consent_token: Optional[str] = None
    document_id: Optional[str] = None
    ai_session_id: Optional[str] = None
    ai_session_token: Optional[str] = None


@router.post("/api/documents/ai-session/preview", response_model=AISessionPreviewResponse)
async def ai_session_preview_endpoint():
    """
    One-time AI activation disclosure preview.
    Does NOT authorize any external transmission until explicitly activated.
    """
    return SingleDocConsentManager.create_ai_session_preview()


@router.post("/api/documents/ai-session/activate", response_model=AISessionActivateResponse)
async def ai_session_activate_endpoint(request: AISessionActivateRequest):
    """
    Consumes a valid activation challenge and issues a bounded, session-scoped HMAC authorization token.
    """
    try:
        return SingleDocConsentManager.activate_ai_session(request.activation_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/ai-session/disable", response_model=AISessionStatusResponse)
async def ai_session_disable_endpoint(request: AISessionCredentialsRequest):
    """
    Revokes session-level AI authorization and reverts to local-only processing.
    """
    return SingleDocConsentManager.disable_ai_session(
        ai_session_id=request.ai_session_id,
        ai_session_token=request.ai_session_token,
    )


@router.post("/api/documents/ai-session/status", response_model=AISessionStatusResponse)
async def ai_session_status_endpoint(request: AISessionCredentialsRequest):
    """
    Checks whether a session-level AI authorization token is currently active and unexpired.
    """
    return SingleDocConsentManager.get_ai_session_status(
        ai_session_id=request.ai_session_id,
        ai_session_token=request.ai_session_token,
    )


@router.post("/api/documents/consent/preview", response_model=ConsentPreviewResponse)
async def consent_preview_endpoint(request: ConsentPreviewRequest):
    """
    Safeguard A & B: Previews the exact proposed payload without authorizing transmission.
    Operation-specific (EXPLAIN, CHAT, TRANSLATE).
    """
    try:
        return SingleDocConsentManager.create_preview(
            doc_id=request.document_id,
            operation=request.operation
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/consent/confirm", response_model=ConsentConfirmResponse)
async def consent_confirm_endpoint(request: ConsentConfirmRequest):
    """
    Safeguard A: Explicit confirmation by user.
    Backend verifies payload hash match, issues a short-lived single-use HMAC token.
    """
    try:
        return SingleDocConsentManager.confirm_consent(
            challenge_id=request.challenge_id,
            doc_id=request.document_id,
            operation=request.operation,
            payload_hash=request.payload_hash
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/upload", response_model=DocumentProcessResult)
async def upload_document(
    file: UploadFile = File(...),
    language: str = Form("English"),
    mode: str = Form("local"),
    ai_session_id: Optional[str] = Form(None),
    ai_session_token: Optional[str] = Form(None),
):
    """
    Endpoint for document ingestion.
    Always extracts locally first. Runs Gemini explanation automatically only when mode='ai'
    AND a valid session-level AI authorization token is verified; falls back locally on failure.
    """
    try:
        result = await DocumentProcessor.process_upload(
            file,
            language,
            mode,
            ai_session_id=ai_session_id,
            ai_session_token=ai_session_token,
        )
        if result.error:
            raise HTTPException(status_code=500, detail=result.error)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/ai-analyze", response_model=DocumentIntelligence)
async def ai_analyze_endpoint(request: AIAnalyzeRequest):
    """
    Executes external AI explanation ONLY when authorized by a verified session AI token
    or single-use consent token. Preserves locally extracted facts on failure.
    """
    try:
        return DocumentProcessor.execute_external_ai_analysis(
            document_id=request.document_id,
            challenge_id=request.challenge_id,
            consent_token=request.consent_token,
            language=request.language,
            ai_session_id=request.ai_session_id,
            ai_session_token=request.ai_session_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/translate", response_model=DocumentIntelligence)
async def translate_endpoint(request: TranslateRequest):
    """
    Translates document intelligence.
    In External Mode: requires valid session AI token or TRANSLATE consent token; falls back locally.
    """
    try:
        return DocumentProcessor.translate_intelligence(
            intelligence=request.intelligence,
            language=request.language,
            mode=request.mode,
            challenge_id=request.challenge_id,
            consent_token=request.consent_token,
            doc_id=request.document_id,
            ai_session_id=request.ai_session_id,
            ai_session_token=request.ai_session_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint for grounded Q&A and explanation.
    Strict Local Mode default: answers using local facts and educational definitions without external calls.
    External AI requires valid CHAT-specific consent token.
    """
    try:
        return ChatService.answer_question(request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
