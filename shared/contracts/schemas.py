from pydantic import BaseModel, Field


class AudioMetaSchema(BaseModel):
    format: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    sample_rate_hz: int | None = Field(default=None, ge=1)
    channels: int | None = Field(default=None, ge=1)
    source: str | None = None
    frame_count: int | None = Field(default=None, ge=0)


class AudioChunkSchema(BaseModel):
    chunk_id: str | None = None
    sequence_id: int | None = Field(default=None, ge=0)
    audio_base64: str | None = None
    audio_format: str | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channels: int | None = Field(default=None, ge=1)


class SpeechFeaturesSchema(BaseModel):
    transcript_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    speaking_rate: float | None = Field(default=None, ge=0.0)
    pause_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    rms_energy: float | None = Field(default=None, ge=0.0)
    peak_level: float | None = Field(default=None, ge=0.0)
    pitch_hz: float | None = Field(default=None, ge=0.0)
    dominant_channel: int | None = Field(default=None, ge=1)
    emotion_tags: list[str] = Field(default_factory=list)
    channel_rms_levels: list[float] = Field(default_factory=list)
    source: str | None = None


class VideoFrameSchema(BaseModel):
    frame_id: str | None = None
    timestamp_ms: int | None = Field(default=None, ge=0)
    mime_type: str | None = None
    image_base64: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    source: str | None = None


class VideoMetaSchema(BaseModel):
    format: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    buffer_duration_ms: int | None = Field(default=None, ge=0)
    frame_count: int | None = Field(default=None, ge=0)
    buffered_frame_count: int | None = Field(default=None, ge=0)
    sampled_frame_count: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, ge=0.0)
    source: str | None = None
    keyframe_strategy: str | None = None


class VisionFeaturesSchema(BaseModel):
    scene_summary: str | None = None
    attention_target: str | None = None
    motion_level: str | None = None
    emotion_tags: list[str] = Field(default_factory=list)
    source: str | None = None
    frame_count: int | None = Field(default=None, ge=0)


class TurnTimeWindowSchema(BaseModel):
    window_id: str | None = None
    source_clock: str | None = None
    transport_mode: str | None = None
    capture_strategy: str | None = None
    stream_id: str | None = None
    sequence_id: int | None = Field(default=None, ge=0)
    capture_started_at_ms: int | None = Field(default=None, ge=0)
    capture_ended_at_ms: int | None = Field(default=None, ge=0)
    triggered_at_ms: int | None = Field(default=None, ge=0)
    pre_roll_ms: int | None = Field(default=None, ge=0)
    post_roll_ms: int | None = Field(default=None, ge=0)
    audio_started_at_ms: int | None = Field(default=None, ge=0)
    audio_ended_at_ms: int | None = Field(default=None, ge=0)
    video_started_at_ms: int | None = Field(default=None, ge=0)
    video_ended_at_ms: int | None = Field(default=None, ge=0)
    window_duration_ms: int | None = Field(default=None, ge=0)



class MultimodalSignalSchema(BaseModel):
    modality: str = Field(..., min_length=1)
    source: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class EmotionInferenceSchema(BaseModel):
    dominant_emotion: str | None = None
    emotion_tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = None
    model_ref: str | None = None


class MultimodalEvidenceSchema(BaseModel):
    canonical_user_text: str | None = None
    speech_context: str | None = None
    vision_context: str | None = None
    speech_emotion_tags: list[str] = Field(default_factory=list)
    vision_emotion_tags: list[str] = Field(default_factory=list)
    emotion_inference: EmotionInferenceSchema | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    video_frame_count: int | None = Field(default=None, ge=0)


class MultimodalResultSchema(BaseModel):
    contract_version: str = Field(default="m5-v1")
    alignment_mode: str = Field(..., min_length=1)
    modalities: list[MultimodalSignalSchema] = Field(default_factory=list)
    dominant_emotion: str | None = None
    fusion_summary: str | None = None
    evidence: MultimodalEvidenceSchema | None = None

class ChatRequestSchema(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: int = Field(..., ge=1)
    user_text: str = Field(default="")
    input_type: str = Field(default="text")
    client_ts: int | None = None
    text_source: str | None = None
    client_asr_text: str | None = None
    client_asr_source: str | None = None
    audio_base64: str | None = None
    audio_format: str | None = None
    audio_duration_ms: int | None = Field(default=None, ge=0)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1)
    audio_channels: int | None = Field(default=None, ge=1)
    audio_stream_id: str | None = None
    audio_stream_event: str | None = None
    audio_stream_sequence_id: int | None = Field(default=None, ge=0)
    audio_chunks: list[AudioChunkSchema] = Field(default_factory=list)
    audio_meta: AudioMetaSchema | None = None
    video_frames: list[VideoFrameSchema] = Field(default_factory=list)
    video_meta: VideoMetaSchema | None = None
    speech_features: SpeechFeaturesSchema | None = None
    vision_features: VisionFeaturesSchema | None = None
    turn_time_window: TurnTimeWindowSchema | None = None
    alignment_mode: str | None = None
    avatar_profile_id: str | None = None
    avatar_ref_image_path: str | None = None


class AvatarActionSchema(BaseModel):
    facial_expression: str
    head_motion: str


class AvatarAudioCueSchema(BaseModel):
    audio_url: str | None = None
    mime_type: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    sample_rate_hz: int | None = Field(default=None, ge=1)
    cache_key: str | None = None


class VisemeCueSchema(BaseModel):
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    label: str = Field(..., min_length=1)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)


class ExpressionCueSchema(BaseModel):
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    expression: str = Field(..., min_length=1)
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)


class MotionCueSchema(BaseModel):
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    motion: str = Field(..., min_length=1)
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)


class AvatarOutputSchema(BaseModel):
    contract_version: str = Field(default="v1")
    renderer_mode: str = Field(default="parameterized_2d")
    transport_mode: str = Field(default="http_poll")
    websocket_endpoint: str | None = None
    stream_id: str | None = None
    sequence_id: int | None = Field(default=None, ge=0)
    avatar_id: str | None = None
    emotion_style: str | None = None
    audio: AvatarAudioCueSchema | None = None
    viseme_seq: list[VisemeCueSchema] = Field(default_factory=list)
    expression_seq: list[ExpressionCueSchema] = Field(default_factory=list)
    motion_seq: list[MotionCueSchema] = Field(default_factory=list)


class ChatResponseSchema(BaseModel):
    server_status: str
    reply_text: str
    emotion_style: str
    avatar_action: AvatarActionSchema
    avatar_output: AvatarOutputSchema | None = None
    reply_audio_url: str | None = None
    reply_video_url: str | None = None
    reply_video_stream_url: str | None = None
    video_text: str | None = None
    video_is_partial: bool = False
    server_ts: int | None = None
    input_mode: str | None = None
    response_source: str | None = None
    context_summary: str | None = None
    reasoning_hint: str | None = None
    turn_time_window: TurnTimeWindowSchema | None = None
    alignment_mode: str | None = None
    multimodal_result: MultimodalResultSchema | None = None


class ErrorResponseSchema(BaseModel):
    detail: str


SUPPORTED_ROBOT_MODES = {"care", "accompany", "learning", "game"}


class RobotFaceState(BaseModel):
    timestamp: float | None = None
    face_detected: bool = False
    face_center: dict[str, float] | None = None
    face_bbox: dict[str, float] | None = None
    tracking_state: str = Field(default="mock")


class RobotInput(BaseModel):
    type: str = Field(default="audio_base64")
    audio_base64: str = Field(..., min_length=1)
    audio_format: str = Field(default="wav")
    sample_rate: int | None = Field(default=16000, ge=1)
    channels: int | None = Field(default=1, ge=1)
    duration_ms: int | None = Field(default=None, ge=0)
    text_hint: str | None = None


class VisionContext(BaseModel):
    source: str = Field(default="mock")
    latest: RobotFaceState | None = None
    recent: list[RobotFaceState] = Field(default_factory=list)
    image_frames: list[VideoFrameSchema] = Field(default_factory=list)


class RobotState(BaseModel):
    state: str = Field(default="IDLE")
    current_expression: str = Field(default="neutral")
    head_pose: dict[str, float] | None = None
    hardware_ready: dict[str, bool] = Field(default_factory=dict)
    mode_id: str = Field(default="care")


class TTSResult(BaseModel):
    type: str = Field(default="audio_url")
    audio_url: str | None = None
    format: str = Field(default="wav")
    duration_ms: int | None = Field(default=None, ge=0)


class EmotionResult(BaseModel):
    label: str = Field(default="neutral")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    valence: str | None = None
    arousal: str | None = None


class RobotAction(BaseModel):
    expression: str = Field(default="neutral")
    motion: str = Field(default="none")
    speech_style: str = Field(default="natural_warm")
    head_target: dict[str, float] | None = None
    priority: str = Field(default="normal")


class ModeInfo(BaseModel):
    mode_id: str = Field(default="care")
    display_name: str = Field(default="关怀模式")
    prompt_policy: str = Field(default="care_gentle")
    rag_namespace: str = Field(default="care")
    action_style: str = Field(default="calm_supportive")


class ModeSwitchResult(BaseModel):
    switched: bool = False
    from_mode: str | None = None
    to_mode: str | None = None
    reason: str | None = None
    confirmation_text: str | None = None


class RobotChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    timestamp: float | None = None
    mode: str = Field(default="care")
    input: RobotInput
    vision_context: VisionContext | None = None
    robot_state: RobotState | None = None
    request_options: dict = Field(default_factory=dict)


class RobotChatResponse(BaseModel):
    success: bool
    session_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    mode: ModeInfo = Field(default_factory=ModeInfo)
    mode_switch: ModeSwitchResult | None = None
    mode_changed: bool = False
    active_rag_namespace: str | None = None
    asr_text: str = Field(default="")
    reply_text: str = Field(default="")
    emotion: EmotionResult = Field(default_factory=EmotionResult)
    tts: TTSResult = Field(default_factory=TTSResult)
    robot_action: RobotAction = Field(default_factory=RobotAction)
    error: dict | None = None
    fallback: dict | None = None
    debug: dict = Field(default_factory=dict)
