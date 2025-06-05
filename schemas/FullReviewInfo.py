from typing import List

from src.schemas.ReviewBase import ReviewBaseModel
from src.schemas.Photo import PhotoModel
from src.schemas.Video import VideoModel

class FullReviewInfoModel(ReviewBaseModel):
    photos: List[PhotoModel] = []
    videos: List[VideoModel] = []
