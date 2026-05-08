from fastapi import APIRouter

from models import (
    FaceIdentityRequest,
    FaceIdentityResponse,
    LinkFaceUserRequest,
    LinkFaceUserResponse,
    MergeFaceRequest,
    MergeFaceResponse,
)
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


@router.post("/v1/vision/identity/merge-faces", response_model=MergeFaceResponse)
async def merge_faces(request: MergeFaceRequest) -> MergeFaceResponse:
    record = face_identity_service.database.merge_faces(
        primary_face_id=request.primary_face_id,
        duplicate_face_id=request.duplicate_face_id,
    )
    if record is None:
        return MergeFaceResponse(
            success=False,
            primary_face_id=request.primary_face_id,
            duplicate_face_id=request.duplicate_face_id,
            error="face_not_found_or_same_record",
        )
    return MergeFaceResponse(
        success=True,
        primary_face_id=str(record.get("face_id") or request.primary_face_id),
        duplicate_face_id=request.duplicate_face_id,
        record=record,
    )
