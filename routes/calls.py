from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
def call_status():
    return {"status": "WebRTC signaling handled via Socket.IO"}
