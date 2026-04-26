import { encodeVideoFrame } from "./frameEncoder";

function sleep(delayMs) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, delayMs);
  });
}

function buildFrameId(turnWindowId, index) {
  return `${turnWindowId || "camera-turn"}-frame-${index + 1}`;
}

export async function sampleKeyFrames(
  videoElement,
  {
    turnWindowId,
    frameCount = 3,
    intervalMs = 120,
    mimeType = "image/jpeg",
    quality = 0.72,
    maxDimension = 640,
  } = {},
) {
  const frames = [];

  for (let index = 0; index < frameCount; index += 1) {
    const encoded = encodeVideoFrame(videoElement, {
      mimeType,
      quality,
      maxDimension,
    });

    frames.push({
      frame_id: buildFrameId(turnWindowId, index),
      timestamp_ms: Date.now(),
      source: "browser_camera",
      ...encoded,
    });

    if (index < frameCount - 1) {
      await sleep(intervalMs);
    }
  }

  return frames;
}
