from models import AudioMeta, ChatRequest, RemoteChatRequest
from services.media import video_turn_service


def normalize_chat_request(
    request: ChatRequest,
    session_id: str,
    turn_id: int,
    request_id: str | None = None,
) -> RemoteChatRequest:
    user_text = (request.user_text or "").strip()
    has_audio = bool(request.audio_base64)
    input_type = request.input_type or "text"

    if user_text and has_audio:
        raise ValueError("Text input and audio input cannot be submitted in the same turn.")

    if not user_text and not has_audio:
        raise ValueError("Either user_text or audio input is required.")

    if has_audio:
        input_type = "audio"
        user_text = user_text or (request.client_asr_text or "").strip()
        text_source = request.text_source or request.client_asr_source or "remote_speech_pending"
        alignment_mode = request.alignment_mode or "audio_only"
        audio_meta_payload = request.audio_meta or AudioMeta(
            format=request.audio_format,
            duration_ms=request.audio_duration_ms,
            sample_rate_hz=request.audio_sample_rate_hz,
            channels=request.audio_channels,
            source="browser_microphone",
        )
        speech_features_payload = request.speech_features
    else:
        text_source = request.text_source or "typed"
        alignment_mode = request.alignment_mode or "text_only"
        audio_meta_payload = request.audio_meta
        speech_features_payload = request.speech_features

    processed_video = video_turn_service.process(
        video_frames=request.video_frames,
        video_meta=request.video_meta,
        turn_time_window=request.turn_time_window,
        primary_input_type=input_type,
    )

    if processed_video.alignment_mode:
        alignment_mode = request.alignment_mode or processed_video.alignment_mode

    vision_features_payload = request.vision_features or processed_video.vision_features
    turn_time_window = processed_video.turn_time_window or request.turn_time_window

    return RemoteChatRequest(
        session_id=session_id,
        turn_id=turn_id,
        user_text=user_text,
        input_type=input_type,
        client_ts=request.client_ts,
        text_source=text_source,
        client_asr_text=request.client_asr_text,
        client_asr_source=request.client_asr_source,
        audio_base64=request.audio_base64,
        audio_format=audio_meta_payload.format if audio_meta_payload else request.audio_format,
        audio_duration_ms=audio_meta_payload.duration_ms if audio_meta_payload else request.audio_duration_ms,
        audio_sample_rate_hz=(
            audio_meta_payload.sample_rate_hz if audio_meta_payload else request.audio_sample_rate_hz
        ),
        audio_channels=audio_meta_payload.channels if audio_meta_payload else request.audio_channels,
        audio_meta=audio_meta_payload,
        video_frames=processed_video.video_frames,
        video_meta=processed_video.video_meta,
        speech_features=speech_features_payload,
        vision_features=vision_features_payload,
        turn_time_window=turn_time_window,
        alignment_mode=alignment_mode,
        avatar_profile_id=request.avatar_profile_id,
        avatar_ref_image_path=request.avatar_ref_image_path,
    )
