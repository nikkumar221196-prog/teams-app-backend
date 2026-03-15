from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, shutil
import database

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    dest = os.path.join(UPLOAD_DIR, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "url": f"/uploads/{file.filename}"}

@router.get("/messages/{organization}")
def get_messages(organization: str):
    messages = database.get_messages_by_org(organization)
    return {"messages": messages}

class DeleteMessageRequest(BaseModel):
    message_id: int
    organization: str

@router.post("/delete-message")
def delete_message(req: DeleteMessageRequest):
    success = database.delete_message(req.message_id, req.organization)
    return {"success": success}

class DeleteAllMessagesRequest(BaseModel):
    organization: str

@router.post("/delete-all-messages")
def delete_all_messages(req: DeleteAllMessagesRequest):
    count = database.delete_all_messages(req.organization)
    return {"success": True, "deleted_count": count}
