import { createAudioPlayer } from "./audioPlayer";
import { applyExpressionSequence } from "./expressionDriver";
import { applyMotionSequence } from "./motionDriver";
import { applyVisemeSequence } from "./visemeDriver";

function resolveBackendMediaUrl(rawUrl) {
  const url = String(rawUrl || "").trim();
  if (!url) {
    return "";
  }

  const lower = url.toLowerCase();
  if (lower.startsWith("http://") || lower.startsWith("https://") || lower.startsWith("data:") || lower.startsWith("blob:")) {
    return url;
  }

  const directApiEnabled = import.meta.env.VITE_USE_DIRECT_API === "true";
  const directApiBase = directApiEnabled
    ? String(import.meta.env.VITE_API_BASE || "").trim().replace(/\/$/, "")
    : "";
  if (!directApiBase) {
    return url;
  }

  if (url.startsWith("/")) {
    return `${directApiBase}${url}`;
  }
  return `${directApiBase}/${url}`;
}

async function resolveStreamFirstChunkUrl(streamManifestUrl) {
  const startedAt = Date.now();
  const timeoutMs = 120000;
  const pollIntervalMs = 600;

  while (Date.now() - startedAt <= timeoutMs) {
    const manifestResponse = await fetch(streamManifestUrl, {
      cache: "no-store",
    }).catch(() => null);
    if (!manifestResponse || !manifestResponse.ok) {
      await waitFor(pollIntervalMs);
      continue;
    }

    const manifest = await manifestResponse.json().catch(() => null);
    const chunks = Array.isArray(manifest?.chunks) ? manifest.chunks : [];
    if (chunks.length) {
      const firstChunkUrl = typeof chunks[0]?.url === "string" ? chunks[0].url : "";
      return resolveBackendMediaUrl(firstChunkUrl);
    }
    if (manifest?.complete) {
      return "";
    }
    await waitFor(pollIntervalMs);
  }

  return "";
}

function waitFor(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function createAvatarRenderer({ faceElement, readouts }) {
  const audioPlayer = createAudioPlayer();
  const portraitImage = faceElement.querySelector(".avatar-portrait-image");
  const videoElement = faceElement.querySelector(".avatar-video");
  const portraitDefaultSrc = portraitImage?.getAttribute("src") || "";
  let stopExpression = () => {};
  let stopMotion = () => {};
  let stopViseme = () => {};
  let renderToken = 0;
  let detachVideoListeners = () => {};
  let pinnedVideoSource = "";

  function setExternalStreamFlag(enabled) {
    faceElement.dataset.externalStream = enabled ? "on" : "off";
  }

  function freezeCurrentVideoFrame() {
    if (!portraitImage || !videoElement) {
      return;
    }
    if (videoElement.classList.contains("hidden")) {
      if (portraitDefaultSrc && !portraitImage.getAttribute("src")) {
        portraitImage.setAttribute("src", portraitDefaultSrc);
      }
      return;
    }
    const width = videoElement.videoWidth;
    const height = videoElement.videoHeight;
    if (!width || !height) {
      return;
    }
    try {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) {
        return;
      }
      context.drawImage(videoElement, 0, 0, width, height);
      portraitImage.setAttribute("src", canvas.toDataURL("image/jpeg", 0.92));
    } catch {
      if (portraitDefaultSrc) {
        portraitImage.setAttribute("src", portraitDefaultSrc);
      }
    }
  }

  function resetVideoElement({ removeSource = true } = {}) {
    if (!videoElement) {
      return;
    }
    detachVideoListeners();
    videoElement.pause();
    videoElement.currentTime = 0;
    if (removeSource) {
      videoElement.removeAttribute("src");
      videoElement.removeAttribute("data-source-url");
      videoElement.removeAttribute("data-source-type");
      videoElement.load();
    }
    videoElement.classList.add("hidden");
  }

  function cleanup({ preserveVideo = false } = {}) {
    renderToken += 1;
    stopExpression();
    stopMotion();
    stopViseme();
    audioPlayer.stop();
    if (!preserveVideo) {
      // Keep the currently selected portrait image stable.
      // Do not overwrite it with the previous reply video's last frame,
      // otherwise profile switching appears one-turn delayed.
      resetVideoElement();
      if (portraitImage) {
        portraitImage.classList.remove("hidden");
      }
    }
  }

  function armVideoTransition(currentToken) {
    if (!videoElement) {
      return;
    }

    const revealVideo = () => {
      if (renderToken !== currentToken) {
        return;
      }
      videoElement.classList.remove("hidden");
      portraitImage?.classList.add("hidden");
    };

    const handleReady = () => {
      cleanupListeners();
      revealVideo();
      void videoElement.play().catch(() => {
        if (renderToken !== currentToken) {
          return;
        }
        resetVideoElement();
        portraitImage?.classList.remove("hidden");
      });
    };

    const handleError = () => {
      cleanupListeners();
      if (renderToken !== currentToken) {
        return;
      }
      resetVideoElement();
      portraitImage?.classList.remove("hidden");
    };

    const cleanupListeners = () => {
      videoElement.removeEventListener("loadeddata", handleReady);
      videoElement.removeEventListener("canplay", handleReady);
      videoElement.removeEventListener("error", handleError);
      detachVideoListeners = () => {};
    };

    detachVideoListeners = cleanupListeners;
    videoElement.addEventListener("loadeddata", handleReady, { once: true });
    videoElement.addEventListener("canplay", handleReady, { once: true });
    videoElement.addEventListener("error", handleError, { once: true });
  }

  function startVideoSource({ url, currentToken, muted, loop, sourceType }) {
    if (!videoElement || !url) {
      return false;
    }
    renderToken = currentToken;
    videoElement.muted = Boolean(muted);
    videoElement.playsInline = true;
    videoElement.loop = Boolean(loop);
    videoElement.preload = "auto";
    videoElement.currentTime = 0;
    videoElement.classList.add("hidden");
    portraitImage?.classList.remove("hidden");
    armVideoTransition(currentToken);
    videoElement.dataset.sourceUrl = url;
    videoElement.dataset.sourceType = sourceType;
    videoElement.src = url;
    videoElement.load();
    return true;
  }

  function ensurePinnedVideoPlaying(currentToken) {
    if (!videoElement || !pinnedVideoSource) {
      return false;
    }
    const currentSource = videoElement.dataset.sourceUrl || "";
    const currentType = videoElement.dataset.sourceType || "";
    const visible = !videoElement.classList.contains("hidden");
    if (visible && currentType === "external" && currentSource === pinnedVideoSource) {
      return true;
    }
    return startVideoSource({
      url: pinnedVideoSource,
      currentToken,
      muted: true,
      loop: true,
      sourceType: "external",
    });
  }

  setExternalStreamFlag(false);

  return {
    setPinnedVideoSource(url) {
      const next = String(url || "").trim();
      if (!next) {
        pinnedVideoSource = "";
        setExternalStreamFlag(false);
        cleanup();
        return false;
      }

      pinnedVideoSource = next;
      setExternalStreamFlag(true);
      const currentToken = renderToken + 1;
      cleanup();
      return startVideoSource({
        url: pinnedVideoSource,
        currentToken,
        muted: true,
        loop: true,
        sourceType: "external",
      });
    },
    clearPinnedVideoSource() {
      pinnedVideoSource = "";
      setExternalStreamFlag(false);
      cleanup();
    },
    getPinnedVideoSource() {
      return pinnedVideoSource;
    },
    hasPinnedVideoSource() {
      return Boolean(pinnedVideoSource);
    },
    render(response) {
      const externalStreamPinned = Boolean(pinnedVideoSource);
      const currentToken = renderToken + 1;
      cleanup({ preserveVideo: externalStreamPinned });

      const fallbackExpression = response.avatar_action?.facial_expression || "neutral";
      const fallbackMotion = response.avatar_action?.head_motion || "steady";
      const avatarOutput = response.avatar_output;

      const emotionStyle = avatarOutput?.emotion_style || response.emotion_style || "supportive";
      const expressionSeq = avatarOutput?.expression_seq || [];
      const motionSeq = avatarOutput?.motion_seq || [];
      const visemeSeq = avatarOutput?.viseme_seq || [];
      faceElement.dataset.emotionStyle = String(emotionStyle).toLowerCase();

      if (readouts) {
        readouts.emotionStyle.textContent = emotionStyle;
        readouts.facialExpression.textContent = expressionSeq[0]?.expression || fallbackExpression;
        readouts.headMotion.textContent = motionSeq[0]?.motion || fallbackMotion;
      }

      if (externalStreamPinned) {
        setExternalStreamFlag(true);
        stopExpression = () => {};
        stopMotion = () => {};
        stopViseme = () => {};
        ensurePinnedVideoPlaying(currentToken);
        audioPlayer.play(avatarOutput?.audio);
        return;
      }

      setExternalStreamFlag(false);
      stopExpression = applyExpressionSequence(faceElement, expressionSeq, fallbackExpression);
      stopMotion = applyMotionSequence(faceElement, motionSeq, fallbackMotion);
      stopViseme = applyVisemeSequence(faceElement, visemeSeq);
      const audioCue = avatarOutput?.audio;
      // Always play reply.wav (avatar_output.audio); keep video as visual-only track.
      audioPlayer.play(audioCue);

      const replyVideoUrl = resolveBackendMediaUrl(response.reply_video_url);
      if (videoElement && replyVideoUrl) {
        startVideoSource({
          url: replyVideoUrl,
          currentToken,
          muted: true,
          loop: false,
          sourceType: "reply",
        });
        return;
      }

      const replyVideoStreamUrl = resolveBackendMediaUrl(response.reply_video_stream_url);
      if (videoElement && replyVideoStreamUrl) {
        void resolveStreamFirstChunkUrl(replyVideoStreamUrl)
          .then((chunkUrl) => {
            if (renderToken !== currentToken) {
              return;
            }
            if (chunkUrl) {
              startVideoSource({
                url: chunkUrl,
                currentToken,
                muted: true,
                loop: false,
                sourceType: "reply",
              });
            }
          })
          .catch(() => {});
        return;
      }
    },
    cleanup,
  };
}
