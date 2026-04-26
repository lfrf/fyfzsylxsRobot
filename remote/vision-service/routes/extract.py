from fastapi import APIRouter

from models import ExtractRequest, ExtractResponse
from services.frame_feature_extractor import frame_feature_extractor

router = APIRouter()


@router.post("/extract", response_model=ExtractResponse)
async def extract(request: ExtractRequest) -> ExtractResponse:
    return frame_feature_extractor.extract(request)
