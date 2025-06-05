from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import PredefinedResponse

router = APIRouter(prefix="/predefined_response")


@router.delete("/{response_id}", tags=["Заготовленные ответы"])
async def delete_predefined_response(
    response_id: int,
    db: Session = Depends(get_db)
):
    try:
        response = db.query(PredefinedResponse).get(response_id)
        if not response:
            raise HTTPException(status_code=404, detail="Response not found")

        db.delete(response)
        db.commit()
        return {"message": "Response deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))