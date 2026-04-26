import { encodeVideoFrame } from "./frameEncoder";

function buildTurnWindowId(startedAt) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `turn-${crypto.randomUUID()}`;
  }
  return `turn-${startedAt}`;
}

function sleep(delayMs) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, delayMs);
  });
}

function buildFrameId(prefix, index, timestampMs) {
  return `${prefix || "camera-buffer"}-frame-${index + 1}-${timestampMs}`;
}

function pruneFrameBuffer(buffer, nowMs, maxBufferMs) {
  const lowerBound = nowMs - maxBufferMs;
  return buffer.filter((frame) => (frame.timestamp_ms || 0) >= lowerBound);
}

function downsampleFrames(frames, maxFrameCount) {
  if (frames.length <= maxFrameCount) {
    return frames;
  }

  const selected = [];
  const step = (frames.length - 1) / (maxFrameCount - 1);
  for (let index = 0; index < maxFrameCount; index += 1) {
    const sourceIndex = Math.round(index * step);
    selected.push(frames[sourceIndex]);
  }
  return selected;
}

function mergeTurnWindow(baseWindow, startedAt, endedAt) {
  const mergedWindow = {
    window_id: baseWindow?.window_id || buildTurnWindowId(startedAt),
    source_clock: baseWindow?.source_clock || "browser_epoch_ms",
    transport_mode: baseWindow?.transport_mode || "http_turn",
    capture_strategy: baseWindow?.capture_strategy || "event_window_keyframes",
    stream_id: baseWindow?.stream_id,
    sequence_id: baseWindow?.sequence_id,
    capture_started_at_ms: baseWindow?.capture_started_at_ms ?? startedAt,
    capture_ended_at_ms: Math.max(baseWindow?.capture_ended_at_ms ?? endedAt, endedAt),
    triggered_at_ms: baseWindow?.triggered_at_ms,
    pre_roll_ms: baseWindow?.pre_roll_ms,
    post_roll_ms: baseWindow?.post_roll_ms,
    audio_started_at_ms: baseWindow?.audio_started_at_ms,
    audio_ended_at_ms: baseWindow?.audio_ended_at_ms,
    video_started_at_ms: startedAt,
    video_ended_at_ms: endedAt,
  };

  if (
    typeof mergedWindow.capture_started_at_ms === "number"
    && typeof mergedWindow.capture_ended_at_ms === "number"
  ) {
    mergedWindow.window_duration_ms = Math.max(
      0,
      mergedWindow.capture_ended_at_ms - mergedWindow.capture_started_at_ms,
    );
  } else {
    mergedWindow.window_duration_ms = Math.max(0, endedAt - startedAt);
  }

  return mergedWindow;
}

export function createCameraTurnRecorder({
  sampleIntervalMs = 1400,
  bufferDurationMs = 12000,
  preRollMs = 4000,
  postRollMs = 800,
  maxEventFrames = 6,
  maxDimension = 480,
} = {}) {
  let mediaStream = null;
  let previewElement = null;
  let cameraEnabledAt = null;
  let frameBuffer = [];
  let samplingTimer = null;
  let backgroundFrameCount = 0;

  function bindPreview(element) {
    previewElement = element;
    if (!previewElement) {
      return;
    }
    previewElement.muted = true;
    previewElement.playsInline = true;
    previewElement.autoplay = true;
    previewElement.srcObject = mediaStream;
  }

  async function applyPreview() {
    if (!previewElement) {
      return;
    }
    previewElement.srcObject = mediaStream;
    if (mediaStream) {
      try {
        await previewElement.play();
      } catch {
        // Browser autoplay policies can reject here; the stream remains bound.
      }
    }
  }

  function captureCurrentFrame(prefix = "camera-buffer") {
    if (!previewElement || previewElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }

    const timestampMs = Date.now();
      const frame = {
        frame_id: buildFrameId(prefix, backgroundFrameCount, timestampMs),
        timestamp_ms: timestampMs,
        source: "browser_camera",
        ...encodeVideoFrame(previewElement, {
          mimeType: "image/jpeg",
          quality: 0.62,
          maxDimension,
        }),
      };
    backgroundFrameCount += 1;
    return frame;
  }

  function pushBufferedFrame(frame) {
    if (!frame) {
      return;
    }
    frameBuffer.push(frame);
    frameBuffer = pruneFrameBuffer(frameBuffer, frame.timestamp_ms || Date.now(), bufferDurationMs);
  }

  function startSamplingLoop() {
    if (samplingTimer || !previewElement) {
      return;
    }

    samplingTimer = window.setInterval(() => {
      try {
        const frame = captureCurrentFrame();
        pushBufferedFrame(frame);
      } catch {
        // Skip transient capture failures while preview is warming up.
      }
    }, sampleIntervalMs);
  }

  function stopSamplingLoop() {
    if (samplingTimer) {
      window.clearInterval(samplingTimer);
      samplingTimer = null;
    }
  }

  function buildEventWindow(baseTurnWindow, triggeredAt, eventStartedAt, eventEndedAt, nextPreRollMs, nextPostRollMs) {
    const nextWindow = mergeTurnWindow(baseTurnWindow, eventStartedAt, eventEndedAt);
    nextWindow.triggered_at_ms = triggeredAt;
    nextWindow.pre_roll_ms = nextPreRollMs;
    nextWindow.post_roll_ms = nextPostRollMs;
    nextWindow.capture_strategy = "event_window_keyframes";
    nextWindow.capture_started_at_ms = eventStartedAt;
    nextWindow.capture_ended_at_ms = eventEndedAt;
    nextWindow.window_duration_ms = Math.max(0, eventEndedAt - eventStartedAt);
    return nextWindow;
  }

  return {
    bindPreview,
    isEnabled() {
      return Boolean(mediaStream);
    },
    async enable() {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support camera capture.");
      }

      if (mediaStream) {
        await applyPreview();
        return {
          active: true,
          enabledAt: cameraEnabledAt,
        };
      }

      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 640 },
          height: { ideal: 360 },
        },
        audio: false,
      });

      cameraEnabledAt = Date.now();
      await applyPreview();
      startSamplingLoop();

      return {
        active: true,
        enabledAt: cameraEnabledAt,
      };
    },
    async disable() {
      stopSamplingLoop();
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = null;
      }

      if (previewElement) {
        previewElement.srcObject = null;
      }

      cameraEnabledAt = null;
      frameBuffer = [];
      backgroundFrameCount = 0;

      return {
        active: false,
      };
    },
    async captureTurn(baseTurnWindow = null) {
      if (!mediaStream || !previewElement) {
        return null;
      }

      if (previewElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        throw new Error("Camera preview is not ready for frame capture.");
      }

      const triggeredAt = Date.now();
      if (postRollMs > 0) {
        await sleep(postRollMs);
      }

      const postTriggerFrame = captureCurrentFrame("camera-trigger");
      pushBufferedFrame(postTriggerFrame);

      const turnWindowId = baseTurnWindow?.window_id || buildTurnWindowId(triggeredAt);
      const lowerBound = triggeredAt - preRollMs;
      const upperBound = triggeredAt + postRollMs;

      const candidateFrames = frameBuffer.filter((frame) => {
        const timestampMs = frame.timestamp_ms || 0;
        return timestampMs >= lowerBound && timestampMs <= upperBound;
      });

      const sampledFrames = downsampleFrames(candidateFrames, maxEventFrames).map((frame, index) => ({
        ...frame,
        frame_id: buildFrameId(turnWindowId, index, frame.timestamp_ms || triggeredAt),
      }));

      if (!sampledFrames.length) {
        return null;
      }

      const startedAt = sampledFrames[0].timestamp_ms || triggeredAt;
      const endedAt = sampledFrames[sampledFrames.length - 1].timestamp_ms || startedAt;
      const frameWidth = sampledFrames[0].width || previewElement.videoWidth || null;
      const frameHeight = sampledFrames[0].height || previewElement.videoHeight || null;
      const durationMs = Math.max(0, endedAt - startedAt);
      const bufferedFrameCount = frameBuffer.length;

      return {
        video_frames: sampledFrames,
        video_meta: {
          format: "jpeg_event_window",
          duration_ms: durationMs,
          buffer_duration_ms: bufferDurationMs,
          frame_count: sampledFrames.length,
          buffered_frame_count: bufferedFrameCount,
          sampled_frame_count: sampledFrames.length,
          width: frameWidth,
          height: frameHeight,
          fps: durationMs > 0 ? Number(((sampledFrames.length * 1000) / durationMs).toFixed(2)) : null,
          source: "browser_camera",
          keyframe_strategy: "rolling_buffer_event_window",
        },
        turn_time_window: buildEventWindow(
          baseTurnWindow,
          triggeredAt,
          startedAt,
          endedAt,
          preRollMs,
          postRollMs,
        ),
      };
    },
  };
}
