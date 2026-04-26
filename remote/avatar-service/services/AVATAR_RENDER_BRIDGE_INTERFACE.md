# Avatar Render Bridge Interface

## Purpose

`avatar_render_bridge.py` is the interface layer between:

- upstream audio generation, such as TTS output
- downstream digital human video generation, currently based on EchoMimic v2

Its role is to make the boundary explicit and file-based:

- TTS outputs a real audio file
- the bridge converts that audio file into a render request
- EchoMimic consumes the request inputs and produces a video file


## File Location

```text
remote/avatar-service/services/avatar_render_bridge.py
```


## Why This Layer Exists

Without this layer, the TTS side and the digital human side would be tightly
coupled to each other's implementation details.

With this bridge:

- TTS only needs to output `audio_path`
- EchoMimic only needs an explicit render request
- pose preset selection becomes centralized
- future avatar renderer replacement becomes easier


## Current Intended Flow

```text
reply_text
  -> TTS runtime
  -> reply.wav
  -> AvatarRenderBridge.build_request(...)
  -> EchoMimic infer.py
  -> output video
```


## Core Interface Objects

### `AvatarPosePreset`

Represents one reusable pose preset entry.

Fields:

- `pose_dir`
- `description`


### `AvatarRenderRequest`

Represents the full request needed to render a digital human video.

Fields:

- `session_id`
- `turn_id`
- `audio_path`
- `ref_image_path`
- `pose_dir`
- `emotion_style`
- `width`
- `height`
- `length`
- `steps`
- `sample_rate`
- `cfg`
- `fps`
- `context_frames`
- `context_overlap`
- `seed`
- `metadata`


### `AvatarRenderResult`

Represents the expected output from the renderer.

Fields:

- `video_path`
- `audio_path`
- `ref_image_path`
- `pose_dir`
- `renderer`
- `fps`
- `frame_count`
- `duration_ms`
- `metadata`


## Mapper Responsibilities

The bridge currently provides three responsibilities:

### 1. Build a normalized render request

```python
build_request(...)
```

This resolves:

- normalized `emotion_style`
- fallback `pose_dir` by style preset
- standard renderer arguments


### 2. Build EchoMimic CLI arguments

```python
build_cli_args(request, infer_script="infer.py")
```

This converts a normalized request into command-line arguments for
`infer.py`.


### 3. Build a normalized render result

```python
build_expected_result(...)
```

This is a helper to normalize output metadata after the video is rendered.


## Current Default Pose Strategy

At the current stage, pose selection is intentionally simple.

The bridge contains a preset table:

- `gentle`
- `supportive`
- `neutral`
- `attentive`
- `listening`
- `encouraging`

All of them currently default to the same base pose preset:

```text
assets/halfbody_demo/pose/01
```

This is a temporary placeholder strategy suitable for integration work.

Later this can be upgraded to map different styles to different pose preset
directories.


## EchoMimic Input Assumption

The current EchoMimic v2 inference path requires:

- one reference image path
- one audio file path
- one pose directory containing frame-wise `*.npy` pose files

That means the bridge is not only passing audio through. It also has to decide
which pose preset directory should be used.


## Example

Example request:

```python
request = avatar_render_bridge.build_request(
    session_id="demo-001",
    turn_id=1,
    audio_path="/tmp/reply.wav",
    ref_image_path="assets/halfbody_demo/refimag/natural_bk_openhand/0035.png",
    emotion_style="gentle",
)
```

Example generated CLI arguments:

```python
[
    "python",
    "infer.py",
    "-W", "768",
    "-H", "768",
    "-L", "120",
    "--steps", "30",
    "--cfg", "2.5",
    "--sample_rate", "16000",
    "--fps", "24",
    "--context_frames", "12",
    "--context_overlap", "3",
    "--seed", "-1",
    "--ref_images_dir", "...",
    "--audio_dir", "...",
    "--pose_dir", "...",
    "--refimg_name", "...",
    "--audio_name", "reply.wav",
    "--pose_name", "01",
]
```


## Design Choice

This bridge is intentionally placed under `avatar-service`, not under
`orchestrator`.

Reason:

- the bridge belongs to the digital human rendering layer
- TTS and avatar video generation are both presentation-side concerns
- upstream orchestration should not depend on EchoMimic command-line details


## Recommended Future Extensions

- add renderer-specific presets for different avatar backends
- add explicit pose preset config file
- add automatic output path planning
- add direct subprocess execution wrapper for EchoMimic
- add duration-based pose trimming logic
- add speaking-style to pose-preset mapping


## Current Limitation

The bridge currently defines the contract and command-building logic only.

It does **not** yet:

- launch the subprocess
- validate file existence
- infer audio duration automatically
- choose a pose preset based on strong semantic logic

Those behaviors should be added only after the contract is agreed.
