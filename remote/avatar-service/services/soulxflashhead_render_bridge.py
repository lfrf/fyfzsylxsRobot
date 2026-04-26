from dataclasses import asdict, dataclass, field
from pathlib import Path
import shlex
import subprocess
import time


@dataclass(frozen=True)
class SoulXFlashHeadRenderRequest:
    session_id: str
    turn_id: int
    audio_path: str
    ref_image_path: str
    emotion_style: str = "supportive"
    fps: int = 25
    chunk_seconds: float = 2.0
    seed: int = -1
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SoulXFlashHeadRenderResult:
    video_path: str
    audio_path: str
    ref_image_path: str
    renderer: str = "soulxflashhead"
    fps: int | None = None
    duration_ms: int | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class SoulXFlashHeadRenderBridge:
    def __init__(self) -> None:
        self.renderer = "soulxflashhead"

    def build_request(
        self,
        *,
        session_id: str,
        turn_id: int,
        audio_path: str,
        ref_image_path: str,
        emotion_style: str | None = None,
        fps: int = 25,
        chunk_seconds: float = 2.0,
        seed: int = -1,
        metadata: dict | None = None,
    ) -> SoulXFlashHeadRenderRequest:
        return SoulXFlashHeadRenderRequest(
            session_id=session_id,
            turn_id=turn_id,
            audio_path=audio_path,
            ref_image_path=ref_image_path,
            emotion_style=(emotion_style or "supportive").strip().lower() or "supportive",
            fps=max(int(fps), 1),
            chunk_seconds=max(float(chunk_seconds), 0.2),
            seed=seed,
            metadata=metadata or {},
        )

    def build_cli_args(
        self,
        request: SoulXFlashHeadRenderRequest,
        *,
        infer_script: str,
        output_path: str,
        command_template: str = "",
        extra_args: str = "",
    ) -> list[str]:
        template_values = {
            "python": "python",
            "infer_script": infer_script,
            "audio_path": request.audio_path,
            "ref_image_path": request.ref_image_path,
            "output_path": output_path,
            "fps": request.fps,
            "chunk_seconds": request.chunk_seconds,
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "emotion_style": request.emotion_style,
            "seed": request.seed,
        }

        if command_template.strip():
            command_text = self._render_command_template(command_template, template_values)
            return shlex.split(command_text)

        cli_args = [
            "python",
            infer_script,
            "--audio",
            request.audio_path,
            "--ref-image",
            request.ref_image_path,
            "--output",
            output_path,
            "--fps",
            str(request.fps),
            "--duration-seconds",
            str(request.chunk_seconds),
            "--seed",
            str(request.seed),
        ]
        if extra_args.strip():
            cli_args.extend(shlex.split(extra_args))
        return cli_args

    @staticmethod
    def _render_command_template(template: str, values: dict[str, object]) -> str:
        # Avoid str.format parser errors when template contains non-placeholder braces.
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    def render_video(
        self,
        request: SoulXFlashHeadRenderRequest,
        *,
        workdir: str,
        infer_script: str,
        timeout_seconds: float = 1200,
        command_template: str = "",
        extra_args: str = "",
    ) -> SoulXFlashHeadRenderResult:
        workdir_path = Path(workdir).expanduser()
        if not workdir_path.exists():
            raise FileNotFoundError(f"SoulXFlashHead root does not exist: {workdir}")

        output_root = workdir_path / "tmp" / "runtime_outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{request.session_id}-{request.turn_id}.mp4"
        started_at = time.time()

        cli_args = self.build_cli_args(
            request,
            infer_script=infer_script,
            output_path=str(output_path),
            command_template=command_template,
            extra_args=extra_args,
        )
        completed = subprocess.run(  # noqa: S603
            cli_args,
            cwd=str(workdir_path),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "SoulXFlashHead render failed. "
                f"exit_code={completed.returncode}; "
                f"stdout={completed.stdout[-1200:]}; "
                f"stderr={completed.stderr[-1200:]}"
            )

        resolved_video_path = output_path if output_path.exists() else self._resolve_latest_video(workdir_path, started_at)
        if resolved_video_path is None:
            raise RuntimeError("SoulXFlashHead render finished but no mp4 output was found.")

        return SoulXFlashHeadRenderResult(
            video_path=str(resolved_video_path),
            audio_path=request.audio_path,
            ref_image_path=request.ref_image_path,
            fps=request.fps,
            duration_ms=int(request.chunk_seconds * 1000),
            metadata={"emotion_style": request.emotion_style, **request.metadata},
        )

    def _resolve_latest_video(self, workdir: Path, after_ts: float) -> Path | None:
        candidates = [
            path
            for path in workdir.rglob("*.mp4")
            if path.is_file() and path.stat().st_mtime >= after_ts
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0]


soulxflashhead_render_bridge = SoulXFlashHeadRenderBridge()
