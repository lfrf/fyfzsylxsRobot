from dataclasses import dataclass

from services.mode_policy import DEFAULT_MODE_ID, MODE_POLICIES, normalize_mode


MODE_COMMANDS = {
    "elderly": (
        "切换为老年模式",
        "进入老年模式",
        "老人模式",
        "老年模式",
    ),
    "child": (
        "切换为儿童模式",
        "进入儿童模式",
        "孩子模式",
        "儿童模式",
    ),
    "student": (
        "切换为学生模式",
        "进入学生模式",
        "学习模式",
        "学生模式",
    ),
    "normal": (
        "切换为正常模式",
        "切换为普通模式",
        "进入正常模式",
        "进入普通模式",
        "正常模式",
        "普通模式",
    ),
}


@dataclass(frozen=True)
class ModeSwitchDetection:
    target_mode: str | None = None
    matched_text: str | None = None

    @property
    def detected(self) -> bool:
        return self.target_mode is not None


class ModeManager:
    def __init__(self, default_mode: str = DEFAULT_MODE_ID) -> None:
        self.default_mode = normalize_mode(default_mode)
        self._session_modes: dict[str, str] = {}

    def get_session_mode(self, session_id: str, requested_mode: str | None = None) -> str:
        if session_id in self._session_modes:
            return self._session_modes[session_id]

        mode = normalize_mode(requested_mode or self.default_mode)
        self._session_modes[session_id] = mode
        return mode

    def set_session_mode(self, session_id: str, mode_id: str) -> str:
        mode = normalize_mode(mode_id)
        self._session_modes[session_id] = mode
        return mode

    def detect_switch(self, text: str | None) -> ModeSwitchDetection:
        if not text:
            return ModeSwitchDetection()

        normalized_text = "".join(str(text).split())
        for mode_id, commands in MODE_COMMANDS.items():
            for command in commands:
                if command in normalized_text:
                    return ModeSwitchDetection(target_mode=mode_id, matched_text=command)
        return ModeSwitchDetection()

    def reset(self) -> None:
        self._session_modes.clear()


mode_manager = ModeManager()

__all__ = [
    "MODE_COMMANDS",
    "MODE_POLICIES",
    "ModeManager",
    "ModeSwitchDetection",
    "mode_manager",
]
