from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from ..services.document_processor import DocumentProcessor
from ..models.document import DocumentProcessResult
from ..models.chat import ChatRequest, ChatResponse
from ..services.chat_service import ChatService

from pydantic import BaseModel
from ..models.document import DocumentIntelligence

router = APIRouter()

class TranslateRequest(BaseModel):
    intelligence: DocumentIntelligence
    language: str

@router.post("/api/documents/translate", response_model=DocumentIntelligence)
async def translate_endpoint(request: TranslateRequest):
    try:
        return DocumentProcessor.translate_intelligence(request.intelligence, request.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/documents/upload", response_model=DocumentProcessResult)
async def upload_document(file: UploadFile = File(...), language: str = Form("English")):
    """
    Endpoint for document ingestion.
    Validates, processes, and structures the uploaded file for AI consumption.
    """
    try:
        result = await DocumentProcessor.process_upload(file, language)
        if result.error:
            raise HTTPException(status_code=500, detail=result.error)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint for grounded Q&A and explanation.
    """
    try:
        # For a production app this might be async if chat_service is IO-bound, 
        # but for now we wrap the sync gemini client call.
        result = ChatService.answer_question(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
