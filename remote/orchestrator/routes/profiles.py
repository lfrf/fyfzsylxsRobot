from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.profile import memory_store, profile_store, user_profile_service

router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


class ResolveFaceProfileRequest(BaseModel):
    face_id: str | None = None
    session_id: str | None = None
    source: str = "background_face_identity"
    display_name: str | None = None


class DisplayNameUpdateRequest(BaseModel):
    display_name: str | None = None


def _dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return model


@router.get("/by-face/{face_id}")
async def get_profile_by_face(face_id: str) -> dict:
    profile = profile_store.get_profile_by_face(face_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile_not_found")
    return {
        "profile": _dump(profile),
        "face_id": face_id,
        "storage_paths": profile_store.storage_paths(),
    }


@router.post("/resolve-face")
async def resolve_face_profile(request: ResolveFaceProfileRequest) -> dict:
    identity = user_profile_service.resolve_face_identity(
        face_id=request.face_id,
        source=request.source or "background_face_identity",
        display_name=request.display_name,
    )
    return {
        "identity": _dump(identity),
        "profile": _dump(identity.profile),
        "session_id": request.session_id,
        "storage_paths": profile_store.storage_paths(),
    }


@router.post("/{user_id}/display-name")
async def update_profile_display_name(user_id: str, request: DisplayNameUpdateRequest) -> dict:
    identity = user_profile_service.update_display_name(
        user_id=user_id,
        display_name=request.display_name,
    )
    if not identity.persisted:
        raise HTTPException(status_code=404, detail=identity.identity_source)
    return {
        "identity": _dump(identity),
        "profile": _dump(identity.profile),
        "storage_paths": profile_store.storage_paths(),
    }


@router.get("/{user_id}")
async def get_profile(user_id: str) -> dict:
    profile = profile_store.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile_not_found")
    return {
        "profile": _dump(profile),
        "memory_event_count": len(memory_store.read_events(profile.user_id, include_summarized=True)),
        "unsummarized_count": memory_store.count_unsummarized(profile.user_id),
        "storage_paths": profile_store.storage_paths(),
    }


@router.post("/{user_id}/summarize")
async def summarize_profile(user_id: str) -> dict:
    profile = profile_store.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile_not_found")
    result = user_profile_service.summarize_user(profile.user_id)
    updated_profile = profile_store.get_profile(profile.user_id) or profile
    return {
        "summary": _dump(result),
        "profile": _dump(updated_profile),
        "unsummarized_count": memory_store.count_unsummarized(profile.user_id),
    }
