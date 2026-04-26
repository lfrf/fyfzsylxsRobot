import { createAudioTurnRecorder } from "../audio/audioTurnRecorder";
import { VOICE_TURN_STATE } from "../audio/recorderStates";
import { createCameraTurnRecorder } from "../video/cameraTurnRecorder";

export function createInputBar({ onSend, onStatusChange, onVideoStatusChange, onCameraModeChange }) {
  const mediaElement = document.createElement("section");
  mediaElement.className = "capture-panel";
  mediaElement.innerHTML = `
    <div class="panel-heading">
      <div>
        <p class="eyebrow">C · Capture</p>
        <h2>Live Camera View</h2>
      </div>
      <span class="chip" data-role="camera-chip">Camera standby</span>
    </div>
    <div class="capture-stage" data-camera-state="disabled">
      <div class="capture-placeholder" data-role="capture-placeholder">
        <p class="capture-title">Camera preview is currently off</p>
        <p class="capture-copy">Enable the camera below to replace this area with a live preview. Text and voice turns will continue to work even if no video key frames are attached.</p>
      </div>
      <div class="camera-preview-shell hidden" data-role="camera-shell" data-state="disabled">
        <video class="camera-preview camera-preview-large" autoplay muted playsinline></video>
        <div class="camera-preview-overlay" data-role="camera-overlay">Camera off</div>
      </div>
    </div>
  `;

  const controlsElement = document.createElement("section");
  controlsElement.className = "input-panel compact-input-panel";
  controlsElement.innerHTML = `
    <div class="panel-heading compact-panel-heading">
      <div>
        <p class="eyebrow">C · Input</p>
        <h2>Conversation Controls</h2>
      </div>
      <span class="chip">Audio + video turns</span>
    </div>
    <form class="compact-input-form">
      <div class="compact-compose-row">
        <div class="message-input-shell" data-role="message-input-shell">
          <input id="message-box" class="message-input" type="text" placeholder="Type a supportive message or use the microphone." />
          <div class="recording-input-overlay hidden" data-role="recording-input-overlay" aria-live="polite">
            <span class="recording-overlay-text">正在录音中</span>
          </div>
        </div>
        <button type="submit" class="primary-button" data-role="send-button">Send</button>
      </div>
      <div class="compact-control-row">
        <button type="button" class="audio-turn-button audio-turn-button-compact" data-role="voice-button" aria-pressed="false">
          <span class="audio-turn-title" data-role="voice-title">Start voice input</span>
          <span class="audio-turn-meta" data-role="voice-meta">Click once to record and again to stop and submit.</span>
        </button>
        <button type="button" class="secondary-button camera-toggle-button" data-role="camera-toggle">Enable camera</button>
        <div class="camera-inline-status">
          <p class="camera-inline-title">Video turn window</p>
          <p class="camera-inline-meta" data-role="camera-meta">Camera disabled. No key frames will be attached.</p>
        </div>
      </div>
    </form>
  `;

  const form = controlsElement.querySelector(".compact-input-form");
  const messageInputShell = controlsElement.querySelector('[data-role="message-input-shell"]');
  const messageBox = controlsElement.querySelector("#message-box");
  const recordingInputOverlay = controlsElement.querySelector('[data-role="recording-input-overlay"]');
  const sendButton = controlsElement.querySelector('[data-role="send-button"]');
  const voiceButton = controlsElement.querySelector('[data-role="voice-button"]');
  const voiceTitle = controlsElement.querySelector('[data-role="voice-title"]');
  const voiceMeta = controlsElement.querySelector('[data-role="voice-meta"]');
  const cameraToggle = controlsElement.querySelector('[data-role="camera-toggle"]');
  const cameraMeta = controlsElement.querySelector('[data-role="camera-meta"]');
  const cameraChip = mediaElement.querySelector('[data-role="camera-chip"]');
  const captureStage = mediaElement.querySelector(".capture-stage");
  const capturePlaceholder = mediaElement.querySelector('[data-role="capture-placeholder"]');
  const cameraShell = mediaElement.querySelector('[data-role="camera-shell"]');
  const cameraOverlay = mediaElement.querySelector('[data-role="camera-overlay"]');
  const cameraPreview = mediaElement.querySelector(".camera-preview");

  const recorder = createAudioTurnRecorder();
  const cameraRecorder = createCameraTurnRecorder();
  cameraRecorder.bindPreview(cameraPreview);

  let isBusy = false;
  let voiceTurnState = VOICE_TURN_STATE.IDLE;
  let preservedDraft = "";
  let cameraEnabled = false;

  function setRecordingOverlay(visible) {
    messageInputShell.dataset.recording = visible ? "on" : "off";
    recordingInputOverlay.classList.toggle("hidden", !visible);
  }

  function setCameraPresentation(nextEnabled) {
    cameraEnabled = nextEnabled;
    captureStage.dataset.cameraState = nextEnabled ? "enabled" : "disabled";
    cameraShell.dataset.state = nextEnabled ? "enabled" : "disabled";
    cameraShell.classList.toggle("hidden", !nextEnabled);
    capturePlaceholder.classList.toggle("hidden", nextEnabled);
    cameraToggle.textContent = nextEnabled ? "Disable camera" : "Enable camera";
    cameraChip.textContent = nextEnabled ? "Camera live" : "Camera standby";
    cameraOverlay.textContent = nextEnabled ? "Live preview + event-window packaging" : "Camera off";
    onCameraModeChange?.(nextEnabled);
  }

  function syncControls() {
    const textLocked = isBusy || voiceTurnState !== VOICE_TURN_STATE.IDLE;

    messageBox.disabled = textLocked;
    sendButton.disabled = textLocked;
    sendButton.textContent = isBusy ? "Sending..." : "Send";
    cameraToggle.disabled = isBusy || voiceTurnState !== VOICE_TURN_STATE.IDLE;

    voiceButton.disabled = voiceTurnState === VOICE_TURN_STATE.PROCESSING
      || (isBusy && voiceTurnState !== VOICE_TURN_STATE.RECORDING);
    voiceButton.dataset.state = voiceTurnState;
    voiceButton.setAttribute("aria-pressed", String(voiceTurnState === VOICE_TURN_STATE.RECORDING));

    if (voiceTurnState === VOICE_TURN_STATE.RECORDING) {
      voiceTitle.textContent = "Stop voice input";
      voiceMeta.textContent = "Recording from the microphone. Text input is locked until this voice turn finishes.";
      messageBox.placeholder = "正在录音中，本轮将以语音发送。";
      setRecordingOverlay(true);
      return;
    }

    if (voiceTurnState === VOICE_TURN_STATE.PROCESSING) {
      voiceTitle.textContent = "Processing voice input";
      voiceMeta.textContent = "Preparing the recorded audio and sending the voice turn to the local edge-backend.";
      messageBox.placeholder = "正在处理语音输入…";
      setRecordingOverlay(false);
      return;
    }

    voiceTitle.textContent = "Start voice input";
    voiceMeta.textContent = "Use the microphone for one audio-only turn. Click again to stop and submit.";
    messageBox.placeholder = "Type a supportive message or use the microphone.";
    setRecordingOverlay(false);
  }

  function setCameraMeta(text) {
    cameraMeta.textContent = text;
  }

  async function captureOptionalVideoTurn(baseTurnWindow = null) {
    if (!cameraRecorder.isEnabled()) {
      return null;
    }

    onVideoStatusChange("Capturing buffered camera key frames for this turn.");

    try {
      const payload = await cameraRecorder.captureTurn(baseTurnWindow);

      if (payload?.video_frames?.length) {
        const count = payload.video_frames.length;
        const preRollMs = payload.turn_time_window?.pre_roll_ms || 0;
        const postRollMs = payload.turn_time_window?.post_roll_ms || 0;
        setCameraMeta(
          `Camera live. Attached ${count} key frames (${preRollMs} ms pre-roll, ${postRollMs} ms post-roll).`,
        );
        onVideoStatusChange(`Attached ${count} buffered camera key frames`);
      } else {
        setCameraMeta("Camera live, but this turn was sent without video key frames.");
        onVideoStatusChange("Camera was enabled, but no video frames were attached.");
      }

      return payload;
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Camera capture failed.";
      setCameraMeta(`Camera live, but this turn fell back to audio/text only. ${detail}`);
      onVideoStatusChange(`Camera capture unavailable for this turn: ${detail}`);
      onStatusChange(`Camera capture was skipped for this turn: ${detail}`);
      return null;
    }
  }

  async function startVoiceTurn() {
    preservedDraft = messageBox.value;
    voiceTurnState = VOICE_TURN_STATE.RECORDING;
    messageBox.value = "";
    syncControls();

    try {
      await recorder.start();
      onStatusChange("Recording audio from microphone. Text input is locked for this turn.");
    } catch (error) {
      voiceTurnState = VOICE_TURN_STATE.IDLE;
      messageBox.value = preservedDraft;
      preservedDraft = "";
      syncControls();

      const detail = error instanceof Error ? error.message : "Audio capture failed.";
      onStatusChange(detail);
    }
  }

  async function stopVoiceTurn() {
    voiceTurnState = VOICE_TURN_STATE.PROCESSING;
    syncControls();
    onStatusChange("Stopping microphone capture and preparing the voice turn.");

    try {
      const audioPayload = await recorder.stop();
      if (!audioPayload?.audio_base64) {
        throw new Error("No audio data was captured for this voice turn.");
      }

      const videoPayload = await captureOptionalVideoTurn(audioPayload.turn_time_window);
      const sent = await onSend({
        text: "",
        audio: audioPayload,
        video: videoPayload,
      });

      if (!sent) {
        messageBox.value = preservedDraft;
      }

      preservedDraft = "";
    } catch (error) {
      messageBox.value = preservedDraft;
      preservedDraft = "";

      const detail = error instanceof Error ? error.message : "Voice turn processing failed.";
      onStatusChange(detail);
    } finally {
      voiceTurnState = VOICE_TURN_STATE.IDLE;
      syncControls();
    }
  }

  function setBusy(nextBusy) {
    isBusy = nextBusy;
    syncControls();
  }

  cameraToggle.addEventListener("click", async () => {
    if (cameraToggle.disabled) {
      return;
    }

    try {
      if (!cameraEnabled) {
        await cameraRecorder.enable();
        setCameraPresentation(true);
        setCameraMeta("Camera preview is active. A rolling local buffer is collecting recent frames for event-window packaging.");
        onVideoStatusChange("Camera preview and local rolling buffer enabled");
        return;
      }

      await cameraRecorder.disable();
      setCameraPresentation(false);
      setCameraMeta("Camera disabled. Video key frames will not be attached to turns.");
      onVideoStatusChange("Camera disabled");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Camera capture failed.";
      setCameraPresentation(false);
      setCameraMeta(detail);
      onVideoStatusChange(detail);
      onStatusChange(detail);
    }
  });

  voiceButton.addEventListener("click", async () => {
    if (voiceTurnState === VOICE_TURN_STATE.RECORDING) {
      await stopVoiceTurn();
      return;
    }

    if (voiceTurnState === VOICE_TURN_STATE.IDLE) {
      await startVoiceTurn();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const videoPayload = await captureOptionalVideoTurn();
    const sent = await onSend({
      text: messageBox.value.trim(),
      audio: null,
      video: videoPayload,
    });
    if (sent) {
      messageBox.value = "";
      onStatusChange("Input cleared and ready for the next turn.");
    }
  });

  setCameraPresentation(false);
  setCameraMeta("Camera disabled. Video key frames will not be attached to turns.");
  onVideoStatusChange("Camera disabled");
  syncControls();

  return {
    mediaElement,
    controlsElement,
    setBusy,
  };
}
