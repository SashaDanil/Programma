from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import PredefinedResponse
from src.schemas.predefined_response import PredefinedResponseUpdate, PredefinedResponseInDB

router = APIRouter(prefix="/predefined_response")


@router.patch("/{response_id}", response_model=PredefinedResponseInDB, tags=["Заготовленные ответы"])
async def update_predefined_response(
    response_id: int,
    update_data: PredefinedResponseUpdate,
    db: Session = Depends(get_db)
):
    try:
        response = db.query(PredefinedResponse).get(response_id)
        if not response:
            raise HTTPException(status_code=404, detail="Response not found")

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(response, field, value)

        db.commit()
        db.refresh(response)
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))