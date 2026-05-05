from fastapi import APIRouter

from models import FaceIdentityRequest, FaceIdentityResponse
from services.face_identity_service import face_identity_service

router = APIRouter()


@router.post("/v1/vision/identity/extract", response_model=FaceIdentityResponse)
async def extract_face_identity(request: FaceIdentityRequest) -> FaceIdentityResponse:
    return face_identity_service.extract_identity(request)
