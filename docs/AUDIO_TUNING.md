# Audio Preprocessing Tuning Guide

## Overview

RaspiroBot includes local audio preprocessing to improve ASR input quality before sending to remote orchestrator. This guide explains the preprocessing pipeline, environment variables, and tuning recommendations.

## Architecture

The preprocessing pipeline is designed as a conservative, low-level enhancement layer:

1. **Noise Gate**: Mutes low-energy frames below a dynamic threshold
2. **Trimming**: Removes leading/trailing silence, preserves speech with padding
3. **Clean WAV Output**: Writes processed audio alongside raw recording

All failures gracefully fallback to raw audio without affecting the speech-to-text pipeline.

## Disabled by Default

Preprocessing is **disabled by default** for safety. Enable via:

```bash
export ROBOT_AUDIO_PREPROCESS_ENABLED=true
```

## Environment Variables

### Core Enable/Disable
- `ROBOT_AUDIO_PREPROCESS_ENABLED` (bool, default: `false`)  
  Master switch for audio preprocessing. Set to `true` to activate.

### Noise Gate
- `ROBOT_AUDIO_ENABLE_NOISE_GATE` (bool, default: `true`)  
  Enable dynamic noise gate to mute low-energy frames.

- `ROBOT_AUDIO_NOISE_GATE_RATIO` (float, default: `3.0`)  
  Multiplier for gate threshold. Recommended range: 2.0–5.0  
  - Lower (2.0–3.0): More aggressive gating, may cut fricatives (s, sh)
  - Higher (4.0–5.0): Less aggressive, may leave more background noise

- `ROBOT_AUDIO_MIN_RMS` (float, default: `80.0`)  
  Minimum RMS threshold for gate fallback. Prevents gate collapse on very quiet speech.

- `ROBOT_AUDIO_NOISE_CALIBRATION_MS` (int, default: `1000`)  
  Duration of initial audio to use for noise floor estimation.

### Trimming
- `ROBOT_AUDIO_ENABLE_TRIM` (bool, default: `true`)  
  Enable speech boundary detection and silence removal.

- `ROBOT_AUDIO_MIN_SPEECH_MS` (int, default: `400`)  
  Minimum speech duration required. Shorter utterances fallback to raw. Prevents trimming near-silent audio.

- `ROBOT_AUDIO_POST_SPEECH_PADDING_MS` (int, default: `150`)  
  Silence duration to preserve after last detected speech frame. Recommended: 100–200ms

### Frame Analysis
- `ROBOT_AUDIO_FRAME_MS` (int, default: `30`)  
  Analysis frame size in milliseconds. Recommended: 20–40ms. Do not change unless you understand energy-based VAD.

### Debug Output
- `ROBOT_AUDIO_SAVE_DEBUG_WAV` (bool, default: `true`)  
  Write debug JSON with detailed metrics. Set to `false` to disable (minimal overhead).

## File Output

When processing a raw recording `utterance-001.wav`:

- **Raw**: `utterance-001.wav` (original, never deleted)
- **Clean**: `utterance-001.clean.wav` (preprocessed, only if valid)
- **Debug**: `utterance-001.debug.json` (metrics, optional)

Payload sent to ASR uses:
- `utterance-001.clean.wav` if preprocessing succeeds
- `utterance-001.wav` if preprocessing fails or is disabled

## Tuning Recommendations

### Issue: Trailing Artifacts or Clipped End-of-Phrase

**Symptom**: ASR cuts off final words or misrecognizes endings.

**Solutions**:
1. Increase `ROBOT_AUDIO_POST_SPEECH_PADDING_MS` to 200–250ms
2. Decrease `ROBOT_AUDIO_NOISE_GATE_RATIO` to 2.5–3.0 (less aggressive gating)
3. Disable trimming temporarily to verify: `export ROBOT_AUDIO_ENABLE_TRIM=false`

### Issue: Background Noise Affecting ASR

**Symptom**: ASR misrecognizes or adds noise words.

**Solutions**:
1. Increase `ROBOT_AUDIO_NOISE_GATE_RATIO` to 4.0–5.0 (more aggressive gating)
2. Ensure microphone is at least 6 inches from user mouth
3. Check room noise level with debug script (see below)

### Issue: Preprocessing Crashes or Falls Back Too Often

**Symptom**: Clean WAV never created, always using raw.

**Solutions**:
1. Check `/tmp/raspirobot/preprocessor_debug/` for error JSON
2. Run debug script (see below) to identify problematic audio
3. Temporarily disable preprocessing to verify ASR still works
4. File issue with error details

### Issue: Processing Latency

**Symptom**: Delay between recording and ASR response.

**Solutions**:
1. Decrease `ROBOT_AUDIO_NOISE_CALIBRATION_MS` to 500ms (less noise analysis overhead)
2. Increase `ROBOT_AUDIO_FRAME_MS` to 40ms (larger frames = fewer computations)
3. Disable debug JSON: `export ROBOT_AUDIO_SAVE_DEBUG_WAV=false`

## Debug Script

Use `audio_capture_debug.py` to test preprocessing interactively:

### Capture and process microphone audio:
```bash
python -m raspirobot.scripts.audio_capture_debug capture --seconds 10 --gate-ratio 3.0
```

### Process existing WAV file:
```bash
python -m raspirobot.scripts.audio_capture_debug process --input /path/to/audio.wav --gate-ratio 4.0 --no-trim
```

### Output:
- Readable metrics (RMS levels, noise floor, gate threshold, trim amounts)
- Debug JSON with full result fields
- Clean WAV and debug artifacts in output directory

## Fallback Policy

Preprocessing is **never required** for robot operation:

- If preprocessing is disabled: raw audio sent directly to ASR
- If preprocessing fails (invalid audio, write error, validation error): fallback to raw audio
- If preprocessing produces invalid output: fallback to raw audio

All failures are logged with structured events:
- `audio_preprocess_started`: Preprocessing begins
- `audio_preprocess_done`: Preprocessing completes (clean or fallback)
- `audio_preprocess_failed`: Unrecoverable error with diagnostic details

## Production Recommended Defaults

For production robot deployments:

```bash
export ROBOT_AUDIO_PREPROCESS_ENABLED=true
export ROBOT_AUDIO_ENABLE_NOISE_GATE=true
export ROBOT_AUDIO_ENABLE_TRIM=true
export ROBOT_AUDIO_NOISE_GATE_RATIO=3.5        # Balanced gating
export ROBOT_AUDIO_POST_SPEECH_PADDING_MS=150  # Standard tail padding
export ROBOT_AUDIO_MIN_SPEECH_MS=400            # Avoid processing < 400ms
export ROBOT_AUDIO_SAVE_DEBUG_WAV=false         # Disable debug overhead
```

## Fallback on Session Failure

If the entire preprocessing session fails (e.g., audio device error), the robot:
1. Logs the error with `fallback_reason`
2. Uses raw audio for ASR request
3. Continues normally—no crash or user-facing interruption

## Related Files

- **Config**: `raspirobot/config.py` — AudioPreprocessConfig fields
- **Core Logic**: `raspirobot/audio/preprocessor.py` — Preprocessing implementation
- **Integration**: `raspirobot/core/turn_manager.py` — Payload selection logic
- **Tests**: `tests/test_audio_preprocessor.py` — Unit test cases
- **Debug Script**: `raspirobot/scripts/audio_capture_debug.py` — Interactive tool

## FAQ

**Q: Will preprocessing delay the ASR response?**
A: Minimal. Preprocessing runs while robot awaits ASR response. Debug JSON write is optional and non-blocking.

**Q: What if preprocessing corrupts audio?**
A: Impossible. Validation checks ensure output matches input format. On any error, fallback to raw.

**Q: Can I disable just the noise gate?**
A: Yes: `export ROBOT_AUDIO_ENABLE_NOISE_GATE=false`

**Q: Should I use trimming for always-on listening?**
A: Trimming is optional. For robust always-on: disable trimming, use noise gate only.

**Q: How do I verify preprocessing is working?**
A: Check for `.clean.wav` files in `/tmp/raspirobot/utterances/`. Use debug script to inspect metrics.
