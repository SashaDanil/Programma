from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import PredefinedResponse
from src.schemas.predefined_response import PredefinedResponseCreate, PredefinedResponseInDB

router = APIRouter(prefix="/predefined_response")


@router.post("/create", response_model=PredefinedResponseInDB, tags=["Заготовленные ответы"])
async def create_predefined_response(
    response_data: PredefinedResponseCreate,
    db: Session = Depends(get_db)
):
    try:
        db_response = PredefinedResponse(**response_data.model_dump())
        db.add(db_response)
        db.commit()
        db.refresh(db_response)
        return db_response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))