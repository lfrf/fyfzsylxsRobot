from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
import time


@dataclass(frozen=True)
class AvatarPosePreset:
    pose_dir: str
    description: str


@dataclass(frozen=True)
class AvatarRenderRequest:
    session_id: str
    turn_id: int
    audio_path: str
    ref_image_path: str
    pose_dir: str
    emotion_style: str = "supportive"
    width: int = 768
    height: int = 768
    length: int = 48
    steps: int = 6
    sample_rate: int = 16000
    cfg: float = 1.0
    fps: int = 24
    context_frames: int = 12
    context_overlap: int = 3
    seed: int = -1
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AvatarRenderResult:
    video_path: str
    audio_path: str
    ref_image_path: str
    pose_dir: str
    renderer: str = "echomimic_v2"
    fps: int | None = None
    frame_count: int | None = None
    duration_ms: int | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_POSE_PRESETS: dict[str, AvatarPosePreset] = {
    "gentle": AvatarPosePreset(
        pose_dir="assets/halfbody_demo/pose/01",
        description="Low-intensity speaking pose for gentle or soothing delivery.",
    ),
    "supportive": AvatarPosePreset(
        pose_dir="assets/halfbody_demo/pose/01",
        description="Default supportive speaking pose.",
    ),
    "neutral": AvatarPosePreset(
        pose_dir="assets/halfbody_demo/pose/01",
        description="Neutral speaking pose.",
    ),
    "attentive": AvatarPosePreset(
        pose_dir="assets/halfbody_demo/pose/01",
        description="Focused listening pose.",
    ),
    "listening": AvatarPosePreset(
        pose_dir="assets/halfbody_demo/pose/01",
        description="Listening-oriented pose preset.",
    ),
    "encouraging": AvatarPosePreset(
        pose_dir="assets/halfbody_demo/pose/01",
        description="Slightly stronger speaking pose for encouraging delivery.",
    ),
}


class AvatarRenderBridge:
    def __init__(
        self,
        *,
        renderer: str = "echomimic_v2",
        pose_presets: dict[str, AvatarPosePreset] | None = None,
        default_style: str = "supportive",
    ) -> None:
        self.renderer = renderer
        self._pose_presets = pose_presets or DEFAULT_POSE_PRESETS
        self._default_style = default_style

    def build_request(
        self,
        *,
        session_id: str,
        turn_id: int,
        audio_path: str,
        ref_image_path: str,
        emotion_style: str | None = None,
        pose_dir: str | None = None,
        width: int = 768,
        height: int = 768,
        length: int = 48,
        steps: int = 4,
        sample_rate: int = 16000,
        cfg: float = 1.0,
        fps: int = 16,
        context_frames: int = 12,
        context_overlap: int = 3,
        seed: int = -1,
        metadata: dict | None = None,
    ) -> AvatarRenderRequest:
        resolved_style = self._resolve_style(emotion_style)
        resolved_pose_dir = pose_dir or self._pose_presets[resolved_style].pose_dir

        return AvatarRenderRequest(
            session_id=session_id,
            turn_id=turn_id,
            audio_path=audio_path,
            ref_image_path=ref_image_path,
            pose_dir=resolved_pose_dir,
            emotion_style=resolved_style,
            width=width,
            height=height,
            length=length,
            steps=steps,
            sample_rate=sample_rate,
            cfg=cfg,
            fps=fps,
            context_frames=context_frames,
            context_overlap=context_overlap,
            seed=seed,
            metadata=metadata or {},
        )

    def build_cli_args(
        self,
        request: AvatarRenderRequest,
        *,
        infer_script: str = "infer.py",
        workdir: str | None = None,
    ) -> list[str]:
        if Path(infer_script).name == "infer_acc.py":
            if workdir is None:
                raise ValueError("workdir is required when using infer_acc.py")
            config_path = self._write_infer_acc_config(Path(workdir), request)
            return [
                "python",
                infer_script,
                "--config",
                str(config_path),
                "-W",
                str(request.width),
                "-H",
                str(request.height),
                "-L",
                str(request.length),
                "--steps",
                str(request.steps),
                "--cfg",
                str(request.cfg),
                "--sample_rate",
                str(request.sample_rate),
                "--fps",
                str(request.fps),
                "--context_frames",
                str(request.context_frames),
                "--context_overlap",
                str(request.context_overlap),
                "--seed",
                str(request.seed),
            ]

        ref_image_path = Path(request.ref_image_path)
        audio_path = Path(request.audio_path)
        pose_dir = Path(request.pose_dir)
        ref_images_dir, refimg_name = self._split_ref_image_cli_args(ref_image_path)

        return [
            "python",
            infer_script,
            "-W",
            str(request.width),
            "-H",
            str(request.height),
            "-L",
            str(request.length),
            "--steps",
            str(request.steps),
            "--cfg",
            str(request.cfg),
            "--sample_rate",
            str(request.sample_rate),
            "--fps",
            str(request.fps),
            "--context_frames",
            str(request.context_frames),
            "--context_overlap",
            str(request.context_overlap),
            "--seed",
            str(request.seed),
            "--ref_images_dir",
            ref_images_dir,
            "--audio_dir",
            str(audio_path.parent),
            "--pose_dir",
            str(pose_dir.parent),
            "--refimg_name",
            refimg_name,
            "--audio_name",
            audio_path.name,
            "--pose_name",
            pose_dir.name,
        ]

    def build_expected_result(
        self,
        *,
        request: AvatarRenderRequest,
        video_path: str,
        frame_count: int | None = None,
        duration_ms: int | None = None,
    ) -> AvatarRenderResult:
        return AvatarRenderResult(
            video_path=video_path,
            audio_path=request.audio_path,
            ref_image_path=request.ref_image_path,
            pose_dir=request.pose_dir,
            renderer=self.renderer,
            fps=request.fps,
            frame_count=frame_count,
            duration_ms=duration_ms,
            metadata={
                "emotion_style": request.emotion_style,
                **request.metadata,
            },
        )

    def render_video(
        self,
        request: AvatarRenderRequest,
        *,
        workdir: str,
        infer_script: str = "infer.py",
        timeout_seconds: float = 1800,
    ) -> AvatarRenderResult:
        workdir_path = Path(workdir).expanduser()
        if not workdir_path.exists():
            raise FileNotFoundError(f"EchoMimic root does not exist: {workdir}")

        before_started_at = time.time()
        cli_args = self.build_cli_args(request, infer_script=infer_script, workdir=str(workdir_path))
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
                "EchoMimic render failed. "
                f"exit_code={completed.returncode}; "
                f"stdout={completed.stdout[-1000:]}; "
                f"stderr={completed.stderr[-1000:]}"
            )

        video_path = self._resolve_output_video_path(workdir_path, after_ts=before_started_at)
        if video_path is None:
            raise RuntimeError("EchoMimic render finished but no new mp4 output was found.")

        return self.build_expected_result(
            request=request,
            video_path=str(video_path),
        )

    def _resolve_style(self, emotion_style: str | None) -> str:
        normalized = (emotion_style or "").strip().lower()
        if normalized in self._pose_presets:
            return normalized
        return self._default_style

    def _split_ref_image_cli_args(self, ref_image_path: Path) -> tuple[str, str]:
        if ref_image_path.parent == ref_image_path.parent.parent:
            return str(ref_image_path.parent), ref_image_path.name

        ref_images_dir = str(ref_image_path.parent.parent)
        refimg_name = f"{ref_image_path.parent.name}/{ref_image_path.name}"
        return ref_images_dir, refimg_name

    def _write_infer_acc_config(self, workdir: Path, request: AvatarRenderRequest) -> Path:
        runtime_dir = workdir / "tmp" / "runtime_configs"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        config_path = runtime_dir / f"{request.session_id}-{request.turn_id}.yaml"
        config_payload = {
            "pretrained_base_model_path": "./pretrained_weights/sd-image-variations-diffusers",
            "pretrained_vae_path": "./pretrained_weights/sd-vae-ft-mse",
            "denoising_unet_path": "./pretrained_weights/denoising_unet_acc.pth",
            "reference_unet_path": "./pretrained_weights/reference_unet.pth",
            "pose_encoder_path": "./pretrained_weights/pose_encoder.pth",
            "motion_module_path": "./pretrained_weights/motion_module_acc.pth",
            "audio_mapper_path": "./pretrained_weights/audio_mapper-50000.pth",
            "auido_guider_path": "./pretrained_weights/wav2vec2-base-960h",
            "auto_flow_path": "./pretrained_weights/AutoFlow",
            "audio_model_path": "./pretrained_weights/audio_processor/tiny.pt",
            "inference_config": "./configs/inference/inference_v2.yaml",
            "weight_dtype": "fp16",
            "test_cases": {
                request.ref_image_path: [
                    request.audio_path,
                    request.pose_dir,
                ]
            },
        }
        config_path.write_text(
            json.dumps(config_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return config_path

    def _resolve_output_video_path(self, workdir: Path, *, after_ts: float) -> Path | None:
        output_roots = [
            root for root in (workdir / "output", workdir / "outputs")
            if root.exists()
        ]
        if not output_roots:
            return None

        preferred_candidates: list[Path] = []
        fallback_candidates: list[Path] = []
        for root in output_roots:
            preferred_candidates.extend(
                path for path in root.rglob("*_sig.mp4")
                if path.is_file() and path.stat().st_mtime >= after_ts
            )
            fallback_candidates.extend(
                path for path in root.rglob("*.mp4")
                if path.is_file()
                and path.stat().st_mtime >= after_ts
                and not path.name.endswith("_sig.mp4")
            )

        if preferred_candidates:
            preferred_candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            return preferred_candidates[0]
        if not fallback_candidates:
            return None

        fallback_candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return fallback_candidates[0]


avatar_render_bridge = AvatarRenderBridge()
