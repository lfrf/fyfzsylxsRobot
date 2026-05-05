from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.profile import memory_store, profile_store, user_profile_service

router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


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
