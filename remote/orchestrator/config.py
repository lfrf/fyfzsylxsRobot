import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        orchestrator_root = Path(__file__).resolve().parent
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"
        self.llm_model = os.getenv("LLM_MODEL", "mock-support-v1").strip() or "mock-support-v1"

        self.llm_api_base = os.getenv("LLM_API_BASE", "http://127.0.0.1:8000/v1").strip().rstrip("/")
        self.llm_api_key = os.getenv("LLM_API_KEY", "EMPTY").strip() or "EMPTY"
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "256"))
        self.llm_request_timeout_seconds = int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60"))
        self.robot_chat_use_mock_llm = os.getenv("ROBOT_CHAT_USE_MOCK_LLM", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self.max_context_messages = int(os.getenv("MAX_CONTEXT_MESSAGES", "8"))
        self.context_summary_turns = int(os.getenv("CONTEXT_SUMMARY_TURNS", "4"))
        self.log_dir = os.getenv("LOG_DIR", "/tmp/a22_logs/orchestrator").strip() or "/tmp/a22_logs/orchestrator"
        self.speech_service_enabled = os.getenv("SPEECH_SERVICE_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.speech_service_base = (
            os.getenv("SPEECH_SERVICE_BASE", "http://127.0.0.1:19100").strip().rstrip("/")
            or "http://127.0.0.1:19100"
        )
        self.speech_service_timeout_seconds = float(os.getenv("SPEECH_SERVICE_TIMEOUT_SECONDS", "60"))
        self.robot_chat_use_mock_asr = os.getenv("ROBOT_CHAT_USE_MOCK_ASR", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.tts_service_base = (
            os.getenv("TTS_SERVICE_BASE", self.speech_service_base).strip().rstrip("/")
            or self.speech_service_base
        )
        self.tts_service_timeout_seconds = float(
            os.getenv("TTS_SERVICE_TIMEOUT_SECONDS", os.getenv("SPEECH_SERVICE_TIMEOUT_SECONDS", "60"))
        )
        self.robot_chat_use_mock_tts = os.getenv("ROBOT_CHAT_USE_MOCK_TTS", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.robot_tts_provider = os.getenv("ROBOT_TTS_PROVIDER", "cosyvoice").strip().lower() or "cosyvoice"
        self.robot_tts_proxy_media = os.getenv("ROBOT_TTS_PROXY_MEDIA", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.vision_service_enabled = os.getenv("VISION_SERVICE_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.vision_service_base = (
            os.getenv("VISION_SERVICE_BASE", "http://127.0.0.1:19200").strip().rstrip("/")
            or "http://127.0.0.1:19200"
        )
        self.vision_service_timeout_seconds = float(os.getenv("VISION_SERVICE_TIMEOUT_SECONDS", "20"))
        self.emotion_service_enabled = os.getenv("EMOTION_SERVICE_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.emotion_service_base = (
            os.getenv("EMOTION_SERVICE_BASE", "http://127.0.0.1:19400").strip().rstrip("/")
            or "http://127.0.0.1:19400"
        )
        self.emotion_service_timeout_seconds = float(os.getenv("EMOTION_SERVICE_TIMEOUT_SECONDS", "15"))
        default_rag_kb_dir = orchestrator_root / "knowledge_base" / "raw"
        default_rag_processed_dir = orchestrator_root / "knowledge_base" / "processed"
        default_rag_index_dir = orchestrator_root / "knowledge_base" / "indexes"
        self.rag_enabled = os.getenv("RAG_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.rag_kb_dir = os.getenv("RAG_KB_DIR", str(default_rag_kb_dir)).strip() or str(default_rag_kb_dir)
        self.rag_processed_dir = (
            os.getenv("RAG_PROCESSED_DIR", str(default_rag_processed_dir)).strip()
            or str(default_rag_processed_dir)
        )
        self.rag_index_dir = (
            os.getenv("RAG_INDEX_DIR", str(default_rag_index_dir)).strip() or str(default_rag_index_dir)
        )
        self.rag_top_k = max(1, int(os.getenv("RAG_TOP_K", "4")))
        self.rag_max_context_chars = max(500, int(os.getenv("RAG_MAX_CONTEXT_CHARS", "2500")))
        self.rag_min_score = max(0.0, float(os.getenv("RAG_MIN_SCORE", "0.08")))
        self.rag_embedding_model = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5").strip()
        self.rag_rebuild_on_start = os.getenv("RAG_REBUILD_ON_START", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.system_prompt = os.getenv(
            "LLM_SYSTEM_PROMPT",
            (
                "You are RobotMatch, the remote brain for a Raspberry Pi desktop companion robot. "
                "Answer with warmth, empathy, and concise helpful guidance. "
                "Keep replies safe, supportive, and suitable for a voice-first robot demo."
            ),
        ).strip()


settings = Settings()
