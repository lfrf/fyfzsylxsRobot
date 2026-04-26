# TTS Style Mapper Interface

## Purpose

`tts_style_mapper.py` is the interface layer between the upstream orchestration
logic and the downstream TTS runtime.

It converts a high-level upstream style decision such as `emotion_style`
into a concrete TTS render plan that can be sent to `remote/avatar-service`.

The design goal is to keep:

- upstream logic focused on dialog intent and emotion policy
- TTS runtime focused on waveform generation
- style mapping centralized and configurable


## File Location

```text
remote/orchestrator/services/tts_style_mapper.py
```


## Main Responsibility

The mapper receives upstream semantic style information and outputs TTS-ready
parameters:

- `tts_instruct_text`
- `tts_speed`
- `tts_speaker_id`

These parameters are then forwarded by `avatar_client` to `avatar-service`.


## Current Call Chain

```text
/chat
  -> dialog_service
  -> policy_service.select_emotion_style(...)
  -> llm_client.generate_reply(...)
  -> tts_style_mapper.build_plan(...)
  -> avatar_client.generate(...)
  -> avatar-service /generate
  -> tts_runtime.synthesize(...)
```


## Interface Objects

### `TTSStylePreset`

Represents one reusable TTS style preset.

Fields:

- `instruct_text: str`
- `speed: float`
- `speaker_id: str | None`


### `TTSRenderPlan`

Represents the final resolved TTS plan for one reply turn.

Fields:

- `emotion_style: str`
- `tts_instruct_text: str`
- `tts_speed: float`
- `tts_speaker_id: str | None`

Methods:

- `to_avatar_payload() -> dict`
- `to_dict() -> dict`


## Mapper API

### `build_plan(...)`

Current signature:

```python
build_plan(
    *,
    emotion_style: str | None,
    reply_text: str,
    override_instruct_text: str | None = None,
    override_speed: float | None = None,
    override_speaker_id: str | None = None,
) -> TTSRenderPlan
```

### Input meaning

- `emotion_style`
  upstream abstract style label, usually produced by `policy_service`
- `reply_text`
  final LLM-generated text that will be spoken by TTS
- `override_instruct_text`
  optional explicit override for prompt-like TTS style control
- `override_speed`
  optional explicit speed override
- `override_speaker_id`
  optional explicit speaker override

### Resolution priority

The mapper resolves values using this priority:

1. request or caller override
2. matched preset for `emotion_style`
3. mapper default preset


## Current Preset Table

Current built-in presets:

- `gentle`
- `supportive`
- `neutral`
- `attentive`
- `listening`
- `encouraging`

Each preset currently defines:

- one Chinese `tts_instruct_text`
- one default `tts_speed`
- one default `tts_speaker_id`


## Why This Interface Exists

Without this layer:

- `emotion_style` would be passed directly into TTS with no concrete meaning
- TTS prompt engineering would leak into `dialog_service` or `avatar-service`
- future TTS model replacement would be harder

With this layer:

- upstream stays model-agnostic
- TTS control becomes centralized
- style presets can be tuned without changing the main chat logic


## Upstream and Downstream Boundary

### Upstream side

Upstream should decide:

- what emotional style the reply should have
- what textual reply should be spoken

Upstream should not directly care about waveform-level implementation details.


### Downstream side

`avatar-service` and `tts_runtime` should consume explicit parameters:

- `reply_text`
- `tts_instruct_text`
- `tts_speed`
- `tts_speaker_id`

Downstream should not infer business emotion policy on its own.


## Example

Example upstream style:

```python
emotion_style = "gentle"
reply_text = "我在这里陪着你，我们可以慢慢来。"
```

Example resolved render plan:

```python
TTSRenderPlan(
    emotion_style="gentle",
    tts_instruct_text="请用温柔、低刺激、带安抚感的女声朗读...",
    tts_speed=0.82,
    tts_speaker_id="中文女",
)
```

Example avatar payload:

```python
{
    "emotion_style": "gentle",
    "tts_instruct_text": "...",
    "tts_speed": 0.82,
    "tts_speaker_id": "中文女",
}
```


## Recommended Future Extensions

- add preset config loading from a JSON or YAML file
- add locale-aware speaker routing
- add prosody controls beyond `speed`
- add explicit `pause_strength` or `intonation_profile`
- expose render plan details in observability logs


## Current Limitation

The mapper currently uses a static preset table.

That means:

- mapping is deterministic
- tuning is manual
- there is no per-user personalization yet

This is acceptable for the current demo and integration stage.
