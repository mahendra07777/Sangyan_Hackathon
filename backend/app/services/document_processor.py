import os
import io
import logging
import json
from typing import Tuple, List
import fitz  # PyMuPDF
from fastapi import UploadFile, HTTPException
from ..models.document import Document, DocumentSection, DocumentChunk, DocumentProcessResult, DocumentIntelligence
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class DocumentProcessor:
    @staticmethod
    async def validate_file(file: UploadFile) -> None:
        """Validate the uploaded file."""
        allowed_types = ["application/pdf", "image/png", "image/jpeg", "text/plain"]
        
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
            
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        
        if size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
            
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {MAX_FILE_SIZE/1024/1024}MB")

    @staticmethod
    def extract_intelligence(content: bytes, mime_type: str, language: str = "English") -> DocumentIntelligence:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Using placeholder intelligence.")
            return DocumentIntelligence(
                document_type="Unknown",
                simple_summary="API Key missing. Cannot analyze document.",
            )
            
        client = genai.Client(api_key=api_key)
        
        language_constraint = ""
        if language == "Hindi":
            language_constraint = 'CRITICAL: You MUST extract and provide all text in proper Hindi using the DEVANAGARI script (e.g., "यह दस्तावेज़ कंपनी के राजस्व को दर्शाता है").'
        elif language == "Hinglish":
            language_constraint = 'CRITICAL: You MUST extract and provide all text in conversational Hinglish using the ROMAN script (e.g., "Yeh document company ka revenue dikhata hai").'
        else:
            language_constraint = 'CRITICAL: You MUST extract and provide all text in proper, formal ENGLISH. Do not leave any non-English words in your explanations.'

        prompt = f"""
        You are a financial document understanding engine for Bharat Investor Copilot.
        Extract the requested structured information from the provided document to help the user deeply understand the document as a whole.
        
        Rules:
        1. Never invent a financial number. Use 'Not found' if missing or cannot be reliably extracted.
        2. Preserve units, currencies, periods, dates, and percentages exactly as reported.
        3. Distinguish reported facts vs calculations vs your explanations.
        4. If the document is ambiguous, explicitly say so in uncertainty_notes.
        5. NEVER infer investment recommendations, future price movements, expected returns, or buy/sell/hold decisions.
        6. Provide evidence references (e.g., page number, section name) for every fact, change, and relationship. Do not create fake citations.
        7. Financial terms should have educational, plain-language definitions and explain why they generally matter.
        8. For `changes`, only calculate changes when underlying values and periods are available. Distinguish percentage change from percentage point change. Do not invent trends.
        9. For `relationships`, identify connections between facts (e.g., "Revenue increased while margin decreased"). Do NOT automatically claim causation. Say "These figures moved differently" instead of "X caused Y".
        10. `document_story` should summarize major themes across the document (NOT an investment score or recommendation).
        11. `areas_to_understand` is a navigation layer (e.g. "PROFITABILITY", "LEVERAGE").
        12. `investigation_paths` generates exploration questions based on the changes and relationships found.
        
        LANGUAGE INSTRUCTION:
        You MUST provide all extracted text, explanations, summaries, and term definitions in {language}.
        {language_constraint}
        - NEVER translate numbers, percentages, currencies, abbreviations (e.g. IPO, EBITDA), or company/regulatory names. Keep them exactly as in the original document.
        """
        
        import time
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=[
                        prompt, 
                        types.Part.from_bytes(data=content, mime_type=mime_type)
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DocumentIntelligence
                    )
                )
                return DocumentIntelligence.model_validate_json(response.text)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                
                # Retry on rate limits or server overload
                if "503" in error_msg or "429" in error_msg:
                    if attempt < max_retries - 1:
                        time.sleep(3 ** attempt)  # 1s, 3s, 9s, 27s
                        continue
                        
                logger.error(f"Gemini extraction completely failed: {error_msg}")
                return DocumentIntelligence(
                    document_type="Error",
                    simple_summary=f"Failed to analyze document with AI: {error_msg}"
                )

    @staticmethod
    def process_pdf(content: bytes, document: Document, language: str = "English") -> Document:
        """Extract text and metadata from PDF using PyMuPDF."""
        try:
            pdf_document = fitz.open(stream=content, filetype="pdf")
            document.page_count = len(pdf_document)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text = page.get_text()
                
                if text.strip():
                    section = DocumentSection(
                        document_id=document.id,
                        page_number=page_num + 1,
                        content=text.strip()
                    )
                    
                    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                    for p in paragraphs:
                        chunk = DocumentChunk(
                            document_id=document.id,
                            page_number=page_num + 1,
                            content=p
                        )
                        section.chunks.append(chunk)
                        
                    document.sections.append(section)
                    
            pdf_document.close()
            document.status = "ready"
            
            # Phase 3/5: Extract Intelligence using Gemini
            document.intelligence = DocumentProcessor.extract_intelligence(content, "application/pdf", language)
            
            return document
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            document.status = "error"
            raise ValueError(f"Failed to process PDF: {str(e)}")

    @staticmethod
    def translate_intelligence(intelligence: DocumentIntelligence, language: str) -> DocumentIntelligence:
        # If it's the same language or English without translation needed, we could optimize, but we'll always translate if called.
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return intelligence
            
        client = genai.Client(api_key=api_key)
        
        language_constraint = ""
        if language == "Hindi":
            language_constraint = 'CRITICAL: You MUST translate the text into proper Hindi using the DEVANAGARI script (e.g., "यह दस्तावेज़ कंपनी के राजस्व को दर्शाता है").'
        elif language == "Hinglish":
            language_constraint = 'CRITICAL: You MUST translate the text into conversational Hinglish using the ROMAN script (e.g., "Yeh document company ka revenue dikhata hai").'
        else:
            language_constraint = 'CRITICAL: You MUST translate the text into proper, formal ENGLISH. If the original text is in Hindi or Hinglish, completely translate it into English. Do not leave any non-English words.'

        prompt = f"""
        You must translate specific text fields of the following JSON object into {language}.
        
        Language Constraints:
        {language_constraint}
        
        Translation Rules:
        1. Keep all numbers, currencies, units, and dates exactly as they are.
        2. Keep company names, financial terms, and abbreviations (e.g., EBITDA, YoY, Revenue, Operating Margin) exactly as they are.
        3. Do NOT modify the 'evidence_reference' or 'evidence_references' fields.
        4. You MUST translate these specific text fields anywhere they appear:
           - simple_summary
           - document_story
           - key_facts.explanation
           - financial_terms.plain_language_definition
           - financial_terms.why_it_matters_general
           - changes.explanation
           - relationships.observation
           - relationships.why_it_may_matter
           - relationships.uncertainty
           - areas_to_understand.title
           - areas_to_understand.description
           - areas_to_understand.questions
           - investigation_paths.question
           - important_sections
           - uncertainty_notes
        5. Return exactly the same JSON schema, just with the text in those fields translated.
        
        Original JSON:
        {intelligence.model_dump_json()}
        """
        
        import time
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DocumentIntelligence
                    )
                )
                return DocumentIntelligence.model_validate_json(response.text)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Translation attempt {attempt + 1} failed: {error_msg}")
                
                # Retry on rate limits or server overload
                if "503" in error_msg or "429" in error_msg:
                    if attempt < max_retries - 1:
                        time.sleep(3 ** attempt)  # 1s, 3s, 9s, 27s
                        continue
                        
                logger.error(f"Failed to translate intelligence after {attempt + 1} attempts: {error_msg}")
                
                # Do NOT return original intelligence on failure, as it will corrupt frontend cache
                if attempt == max_retries - 1:
                    raise Exception(f"Failed to translate intelligence: {error_msg}")

    @staticmethod
    def process_text(content: bytes, document: Document, language: str = "English") -> Document:
        """Extract text from plain text file."""
        text = content.decode('utf-8')
        document.page_count = 1
        
        if text.strip():
            section = DocumentSection(
                document_id=document.id,
                page_number=1,
                content=text.strip()
            )
            
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                chunk = DocumentChunk(
                    document_id=document.id,
                    page_number=1,
                    content=p
                )
                section.chunks.append(chunk)
                
            document.sections.append(section)
            
        document.status = "ready"
        
        # Phase 3/5: Extract Intelligence
        document.intelligence = DocumentProcessor.extract_intelligence(content, "text/plain", language)
        
        return document

    @staticmethod
    def process_image(content: bytes, document: Document, language: str = "English") -> Document:
        """Process image and extract intelligence using Gemini Vision capabilities."""
        document.page_count = 1
        document.status = "ready"
        
        # Phase 3/5: Extract Intelligence
        document.intelligence = DocumentProcessor.extract_intelligence(content, document.file_type, language)
        
        return document

    @classmethod
    async def process_upload(cls, file: UploadFile, language: str = "English") -> DocumentProcessResult:
        """Main pipeline entry point."""
        await cls.validate_file(file)
        
        content = await file.read()
        
        document = Document(
            filename=file.filename or "unknown",
            file_type=file.content_type or "unknown",
            file_size_bytes=len(content),
            status="processing"
        )
        
        try:
            if file.content_type == "application/pdf":
                document = cls.process_pdf(content, document, language)
            elif file.content_type == "text/plain":
                document = cls.process_text(content, document, language)
            elif file.content_type in ["image/png", "image/jpeg"]:
                document = cls.process_image(content, document, language)
                
            return DocumentProcessResult(document=document)
            
        except Exception as e:
            document.status = "error"
            return DocumentProcessResult(
                document=document,
                message="Processing failed",
                error=str(e)
            )
