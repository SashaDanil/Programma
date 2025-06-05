from typing import List, Optional, Dict
from pydantic import BaseModel

class ResponseStats(BaseModel):
    total_reviews: int
    with_response: int
    without_response: int

class PaginatedResponseModel(BaseModel):
    data: List[dict]  # Изменил с FullReviewInfo на dict для большей гибкости
    total: int
    limit: int
    offset: int
    status_counts: Optional[Dict[str, int]] = None
    response_stats: Optional[ResponseStats] = None

