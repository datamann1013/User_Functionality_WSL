from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from ..services.chat_memory import ChatMemory
import os

router = APIRouter()

# Initialize chat memory with disk persistence (optional)
CHAT_MEMORY_PATH = os.environ.get('CHAT_MEMORY_PATH', 'chat_memory.json')
chat_memory = ChatMemory(max_length=20, persist_path=CHAT_MEMORY_PATH)

@router.post('/chat/send')
async def send_message(request: Request):
    data = await request.json()
    session_id = data.get('session_id')
    text = data.get('text')
    file_ref = data.get('file')  # e.g., file URL or ID
    metadata = data.get('metadata', {})
    if not session_id or not text:
        return JSONResponse({'error': 'session_id and text required'}, status_code=400)
    message = {'text': text, 'file': file_ref, 'metadata': metadata}
    chat_memory.add_message(session_id, message)
    return {'status': 'ok'}

@router.get('/chat/history')
async def get_history(session_id: str):
    messages = chat_memory.get_memory(session_id)
    return {'messages': messages}

@router.post('/chat/clear')
async def clear_history(request: Request):
    data = await request.json()
    session_id = data.get('session_id')
    chat_memory.clear_memory(session_id)
    return {'status': 'cleared'}

