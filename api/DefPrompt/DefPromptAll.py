from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import PredefinedResponse
from src.schemas.predefined_response import PredefinedResponseInDB, PredefinedResponseList

router = APIRouter(prefix="/predefined_response",)


@router.get("/get", response_model=PredefinedResponseList, tags=["Заготовленные ответы"])
async def get_all_predefined_responses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    try:
        items = db.query(PredefinedResponse).offset(skip).limit(limit).all()
        total = db.query(PredefinedResponse).count()
        return {"items": items, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{response_id}", response_model=PredefinedResponseInDB, tags=["Заготовленные ответы"])
async def get_predefined_response(
    response_id: int,
    db: Session = Depends(get_db)
):
    response = db.query(PredefinedResponse).get(response_id)
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    return response