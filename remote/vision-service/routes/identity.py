from fastapi import APIRouter

from models import FaceIdentityRequest, FaceIdentityResponse, LinkFaceUserRequest, LinkFaceUserResponse
from services.face_identity_service import face_identity_service

router = APIRouter()


@router.post("/v1/vision/identity/extract", response_model=FaceIdentityResponse)
async def extract_face_identity(request: FaceIdentityRequest) -> FaceIdentityResponse:
    return face_identity_service.extract_identity(request)


@router.post("/v1/vision/identity/link-user", response_model=LinkFaceUserResponse)
async def link_face_user(request: LinkFaceUserRequest) -> LinkFaceUserResponse:
    record = face_identity_service.database.link_user(
        face_id=request.face_id,
        user_id=request.user_id,
        display_name=request.display_name,
    )
    if record is None:
        return LinkFaceUserResponse(
            success=False,
            face_id=request.face_id,
            user_id=request.user_id,
            display_name=request.display_name,
            error="face_not_found",
        )
    return LinkFaceUserResponse(
        success=True,
        face_id=request.face_id,
        user_id=request.user_id,
        display_name=request.display_name,
        record=record,
    )
