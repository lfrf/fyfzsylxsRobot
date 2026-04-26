import os


class Settings:
    def __init__(self) -> None:
        self.tmp_dir = os.getenv("TMP_DIR", "/root/autodl-tmp/a22/tmp/vision").strip() or "/root/autodl-tmp/a22/tmp/vision"
        self.extractor_mode = os.getenv("VISION_EXTRACTOR_MODE", "qwen2_5_vl").strip().lower() or "qwen2_5_vl"
        self.vision_model = (
            os.getenv(
                "VISION_MODEL",
                "/root/autodl-tmp/a22/models/Qwen2.5-VL-7B-Instruct",
            ).strip()
            or "/root/autodl-tmp/a22/models/Qwen2.5-VL-7B-Instruct"
        )
        self.vision_device = os.getenv("VISION_DEVICE", "cuda:0").strip() or "cuda:0"
        self.frame_input_mode = os.getenv("VISION_FRAME_INPUT_MODE", "event_window_keyframes").strip().lower() or "event_window_keyframes"
        self.vision_dtype = os.getenv("VISION_DTYPE", "float16").strip().lower() or "float16"
        self.vision_max_new_tokens = max(32, int(os.getenv("VISION_MAX_NEW_TOKENS", "192")))
        self.vision_warmup_enabled = os.getenv("VISION_WARMUP_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.ring_buffer_enabled = os.getenv("VISION_RING_BUFFER_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.ring_buffer_max_frames = max(16, int(os.getenv("VISION_RING_BUFFER_MAX_FRAMES", "120")))
        self.ring_buffer_max_age_ms = max(1000, int(os.getenv("VISION_RING_BUFFER_MAX_AGE_MS", "30000")))
        self.ring_buffer_window_default_ms = max(
            500,
            int(os.getenv("VISION_RING_BUFFER_WINDOW_DEFAULT_MS", "6000")),
        )
        self.ring_buffer_window_max_frames = max(
            1,
            int(os.getenv("VISION_RING_BUFFER_WINDOW_MAX_FRAMES", "10")),
        )
        self.fer_enabled = os.getenv("FER_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.fer_provider = os.getenv("FER_PROVIDER", "hsemotion").strip().lower() or "hsemotion"
        self.fer_model_name = os.getenv("FER_MODEL_NAME", "enet_b2_7").strip() or "enet_b2_7"
        self.fer_device = os.getenv("FER_DEVICE", "cpu").strip() or "cpu"
        self.fer_detector = os.getenv("FER_DETECTOR", "haar").strip().lower() or "haar"
        self.fer_max_frames = max(1, int(os.getenv("FER_MAX_FRAMES", "4")))
        self.fer_min_confidence = min(max(float(os.getenv("FER_MIN_CONFIDENCE", "0.2")), 0.0), 1.0)
        self.fer_warmup_enabled = os.getenv("FER_WARMUP_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.fer_force_no_weights_only_load = (
            os.getenv("FER_FORCE_NO_WEIGHTS_ONLY_LOAD", "true").strip().lower() in {"1", "true", "yes", "on"}
        )


settings = Settings()
