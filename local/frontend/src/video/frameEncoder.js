function stripDataUrlPrefix(dataUrl) {
  const marker = "base64,";
  const markerIndex = dataUrl.indexOf(marker);
  if (markerIndex === -1) {
    return dataUrl;
  }
  return dataUrl.slice(markerIndex + marker.length);
}

export function encodeVideoFrame(videoElement, { mimeType = "image/jpeg", quality = 0.62, maxDimension = 480 } = {}) {
  const sourceWidth = videoElement.videoWidth;
  const sourceHeight = videoElement.videoHeight;

  if (!sourceWidth || !sourceHeight) {
    throw new Error("Camera preview is not ready yet.");
  }

  const scale = Math.min(1, maxDimension / Math.max(sourceWidth, sourceHeight));
  const width = Math.max(1, Math.round(sourceWidth * scale));
  const height = Math.max(1, Math.round(sourceHeight * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d", { alpha: false });
  if (!context) {
    throw new Error("This browser does not support canvas frame capture.");
  }

  context.drawImage(videoElement, 0, 0, width, height);
  const dataUrl = canvas.toDataURL(mimeType, quality);

  return {
    image_base64: stripDataUrlPrefix(dataUrl),
    mime_type: mimeType,
    width,
    height,
  };
}
