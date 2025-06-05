from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query


router = APIRouter()

@router.get("/health", tags=["Тесты"])
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
