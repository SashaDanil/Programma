from fastapi import APIRouter

from src.api.Reviews.UpdateReviewsResponse import router as UpdateReviewsResponse
from src.api.Reviews.ReviewWithResponse import router as ReviewWithResponse
from src.api.Reviews.ProcessReviewsWithResponses import router as ProcessReviewsWithEesponses
from src.api.Reviews.ProcessUnprocessedReviews import router as ProcessUnprocessedReviews
from src.api.Reviews.send_all_error_to_queue import router as send_all_error_to_queue
from src.api.ProductPrompts.UpdateProductPrompt import router as UpdateProductPromt
from src.api.ProductPrompts.ProductPrompts import router as ProductPromts
from src.api.ProductPrompts.SearchProductPrompts import router as SerchProductPrompts
from src.api.Reviews.GetReviewsFullInfo import router as GetReviewsFullInfo
from src.api.MainPromt.GetPrompts import router as GetPrompts
from src.api.MainPromt.UpdatePrompt import router as UpdatePrompt
from src.api.MainPromt.CreatePrompt import router as CreatePrompt
from src.api.health import router as health
from src.api.APIKeyManagement.UpdateApi import router as UpdateApi
from src.api.APIKeyManagement.CreateApi import router as CreateApi
from src.api.APIKeyManagement.DeleteApi import router as DeliteApi
from src.api.APIKeyManagement.GetApi import router as GetApi
from src.api.Reviews.ProductReport import router as ProductReport
from src.api.ReviewFilter.AllReviewFilter import router as AllReviewFilter
from src.api.ReviewFilter.ChengeReviewFilter import router as ChengeReviewFilter
from src.api.ReviewFilter.DeliteReviewFilter import router as DeliteReviewFilter
from src.api.ReviewFilter.NewReviewFilter import router as NewReviewFilter
from src.api.DefPrompt.DefPromptAll import router as DefPromptAll
from src.api.DefPrompt.DefPromptCreate import router as DefPromptCreate
from src.api.DefPrompt.DefPromptDelite import router as DefPromptDelite
from src.api.DefPrompt.DefPromptUpdate import router as DefPromptUpdate

main_router = APIRouter()

main_router.include_router(health)

# MainPromt
main_router.include_router(GetPrompts)
main_router.include_router(UpdatePrompt)
main_router.include_router(CreatePrompt)

# ProductPrompts
main_router.include_router(UpdateProductPromt)
main_router.include_router(ProductPromts)
main_router.include_router(SerchProductPrompts)

# APIKeysManagement
main_router.include_router(UpdateApi)
main_router.include_router(CreateApi)
main_router.include_router(DeliteApi)
main_router.include_router(GetApi)

# Reviews
main_router.include_router(GetReviewsFullInfo)
main_router.include_router(UpdateReviewsResponse)
main_router.include_router(ReviewWithResponse)
main_router.include_router(ProcessReviewsWithEesponses)
main_router.include_router(ProcessUnprocessedReviews)
main_router.include_router(ProductReport)
main_router.include_router(send_all_error_to_queue)

# ReviewFilter

main_router.include_router(AllReviewFilter)
main_router.include_router(ChengeReviewFilter)
main_router.include_router(DeliteReviewFilter)
main_router.include_router(NewReviewFilter)

# DefPrompt

main_router.include_router(DefPromptAll)
main_router.include_router(DefPromptCreate)
main_router.include_router(DefPromptDelite)
main_router.include_router(DefPromptUpdate)

