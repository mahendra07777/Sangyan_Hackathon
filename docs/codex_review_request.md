# Codex Engineering Review Request

Please inspect the following repository components for Bharat Investor Copilot:

- `backend/app/api/routes.py`
- `backend/app/services/chat_service.py`
- `app/src/lib/api.ts`
- `app/src/pages/Workspace.tsx`

**Specifically evaluate:**
1. Frontend reliability (State management, API fallback).
2. Backend reliability (FastAPI error handling, retry mechanism).
3. Security (CORS, file payload parsing, dotenv usage).
4. Error handling (Are any raw stack traces leaked to the client?).
5. Test coverage (17 automated cases run).
6. Unnecessary complexity.
7. Obvious bugs that might break the demo flow.

Do NOT create a second competing architecture. Focus on hardening the existing implementation.
