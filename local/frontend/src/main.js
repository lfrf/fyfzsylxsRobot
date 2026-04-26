import "./styles.css";

import { sendChatRequest } from "./api/chat";
import { createAvatarPanel } from "./ui/AvatarPanel";
import { createChatPanel } from "./ui/ChatPanel";
import { createInputBar } from "./ui/InputBar";
import { createStatusBar } from "./ui/StatusBar";

const app = document.getElementById("app");

const DEFAULT_AVATAR_SESSION_ID = "demo_s1";
const DEFAULT_AVATAR_STREAM_ID = "demo_stream_1";

const configuredSessionId = (import.meta.env.VITE_AVATAR_SESSION_ID || "").trim();
const configuredStreamId = (import.meta.env.VITE_AVATAR_STREAM_ID || "").trim();

const state = {
  sessionId: configuredSessionId || DEFAULT_AVATAR_SESSION_ID,
  streamId: configuredStreamId || DEFAULT_AVATAR_STREAM_ID,
  nextTurnId: 1,
  transport: "Waiting for first message",
  remoteStatus: "Remote link pending",
  inputMode: "text",
  emotionStyle: "supportive",
  facialExpression: "neutral",
  headMotion: "steady",
  audioStatus: "Audio idle",
  videoStatus: "Camera disabled",
  isSending: false,
  cameraEnabled: false,
  avatarProfileId: "avatar_a",
};

let leftTopStack = null;

const avatarPanel = createAvatarPanel({
  onProfileChange: (profile) => {
    state.avatarProfileId = profile?.id || state.avatarProfileId;
  },
});
state.avatarProfileId = avatarPanel.getSelectedProfileId();
const chatPanel = createChatPanel();
const statusBar = createStatusBar();
const inputBar = createInputBar({
  onSend: handleSend,
  onStatusChange: (audioStatus) => {
    syncStatus({
      audioStatus,
    });
  },
  onVideoStatusChange: (videoStatus) => {
    syncStatus({
      videoStatus,
    });
  },
  onCameraModeChange: (cameraEnabled) => {
    state.cameraEnabled = cameraEnabled;
    syncLayout();
  },
});

app.innerHTML = `
  <div class="page-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">A22 Local Workspace</p>
        <h1>Emotion Support Digital Human Console</h1>
      </div>
      <div class="topbar-meta">
        <span class="chip">Local light processing</span>
        <span class="chip">Remote unified reasoning</span>
      </div>
    </header>
    <main class="workspace-grid">
      <section class="left-column">
        <section class="left-top-stack camera-off"></section>
        <section class="control-column panel"></section>
      </section>
      <section class="right-column">
        <section class="avatar-column"></section>
        <section class="status-column panel"></section>
      </section>
    </main>
  </div>
`;

leftTopStack = app.querySelector(".left-top-stack");
leftTopStack.append(inputBar.mediaElement, chatPanel.element);
app.querySelector(".control-column").append(inputBar.controlsElement);
app.querySelector(".avatar-column").appendChild(avatarPanel.element);
app.querySelector(".status-column").appendChild(statusBar.element);

chatPanel.addSystemMessage("Local UI is ready. Send text or record a short audio clip to start.");
syncStatus({
  remoteStatus: "Remote link pending",
  audioStatus: "Audio idle",
  videoStatus: "Camera disabled",
});
syncLayout();

function buildTextTurnTimeWindow(turnId) {
  const now = Date.now();
  return {
    window_id: `${state.sessionId}-turn-${turnId}`,
    source_clock: "browser_epoch_ms",
    transport_mode: "http_turn",
    stream_id: state.streamId,
    sequence_id: turnId,
    capture_started_at_ms: now,
    capture_ended_at_ms: now,
    window_duration_ms: 0,
  };
}

async function handleSend({ text, audio, video }) {
  if (state.isSending) {
    chatPanel.addSystemMessage("A request is already in progress. Please wait for the current reply.");
    return false;
  }

  const hasText = Boolean(text);
  const hasAudio = Boolean(audio?.audio_base64);
  const hasVideo = Boolean(video?.video_frames?.length || video?.video_meta);

  if (!hasText && !hasAudio) {
    chatPanel.addSystemMessage("Please enter text or record audio before sending.");
    return false;
  }

  const turnId = state.nextTurnId;
  const inputMode = hasAudio ? "audio" : "text";
  const userMessage = hasText ? text : "[Voice message]";

  chatPanel.addMessage({
    role: "user",
    text: userMessage,
    meta: `Turn ${turnId} · ${inputMode}`,
  });

  state.isSending = true;
  inputBar.setBusy(true);
  chatPanel.setLoading(true);
  syncStatus({
    transport: "Sending request to local edge-backend",
    remoteStatus: "Awaiting remote orchestrator response",
    inputMode,
    audioStatus: hasAudio ? `Audio attached (${audio.audio_duration_ms} ms)` : "Text only",
    videoStatus: hasVideo
      ? `Video attached (${video.video_frames?.length || video.video_meta?.sampled_frame_count || 0} key frames)`
      : state.videoStatus,
  });

  try {
    const baseTurnTimeWindow = video?.turn_time_window
      || (hasAudio ? audio.turn_time_window : buildTextTurnTimeWindow(turnId));
    const turnTimeWindow = {
      ...(baseTurnTimeWindow || {}),
      window_id: baseTurnTimeWindow?.window_id || `${state.sessionId}-turn-${turnId}`,
      source_clock: baseTurnTimeWindow?.source_clock || "browser_epoch_ms",
      transport_mode: baseTurnTimeWindow?.transport_mode || "http_turn",
      stream_id: state.streamId,
      sequence_id: turnId,
    };
    const requestPayload = {
      session_id: state.sessionId,
      turn_id: turnId,
      user_text: hasText ? text : undefined,
      input_type: inputMode,
      client_ts: Math.floor(Date.now() / 1000),
      turn_time_window: turnTimeWindow,
      avatar_profile_id: state.avatarProfileId,
    };

    if (hasAudio) {
      const { turn_time_window: _ignoredAudioWindow, ...audioPayload } = audio;
      Object.assign(requestPayload, audioPayload);
    }

    if (hasVideo) {
      const { turn_time_window: _ignoredVideoWindow, ...videoPayload } = video;
      Object.assign(requestPayload, videoPayload);
    }

    const response = await sendChatRequest(requestPayload);

    state.nextTurnId += 1;
    state.transport = "Request completed";

    chatPanel.addMessage({
      role: "assistant",
      text: response.reply_text,
      meta: `${response.emotion_style} · ${response.avatar_action.facial_expression} / ${response.avatar_action.head_motion}`,
    });
    avatarPanel.update(response);
    syncStatus({
      transport: "Remote reply received",
      remoteStatus: response.server_status === "ok" ? "Remote orchestrator connected" : "Remote orchestrator error",
      inputMode: response.input_mode || inputMode,
      emotionStyle: response.emotion_style,
      facialExpression: response.avatar_action.facial_expression,
      headMotion: response.avatar_action.head_motion,
      audioStatus: hasAudio ? "Audio processed by edge-backend" : "Text turn processed",
      videoStatus: hasVideo ? "Video key frames forwarded by edge-backend" : state.videoStatus,
    });
    return true;
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown request error";
    chatPanel.addSystemMessage(`Request failed: ${detail}`);
    syncStatus({
      transport: "Request failed",
      remoteStatus: "Check edge-backend and remote orchestrator",
      audioStatus: hasAudio ? "Audio send failed" : "Text send failed",
      videoStatus: hasVideo ? "Video send failed" : state.videoStatus,
    });
    return false;
  } finally {
    state.isSending = false;
    inputBar.setBusy(false);
    chatPanel.setLoading(false);
  }
}

function syncStatus(nextState) {
  state.transport = nextState.transport || state.transport;
  state.remoteStatus = nextState.remoteStatus || state.remoteStatus;
  state.inputMode = nextState.inputMode || state.inputMode;
  state.emotionStyle = nextState.emotionStyle || state.emotionStyle;
  state.facialExpression = nextState.facialExpression || state.facialExpression;
  state.headMotion = nextState.headMotion || state.headMotion;
  state.audioStatus = nextState.audioStatus || state.audioStatus;
  state.videoStatus = nextState.videoStatus || state.videoStatus;
  statusBar.update({
    sessionId: state.sessionId,
    streamId: state.streamId,
    nextTurnId: state.nextTurnId,
    transport: state.transport,
    remoteStatus: state.remoteStatus,
    inputMode: state.inputMode,
    emotionStyle: state.emotionStyle,
    facialExpression: state.facialExpression,
    headMotion: state.headMotion,
    audioStatus: state.audioStatus,
    videoStatus: state.videoStatus,
  });
}

function syncLayout() {
  if (!leftTopStack) {
    return;
  }
  leftTopStack.classList.toggle("camera-on", state.cameraEnabled);
  leftTopStack.classList.toggle("camera-off", !state.cameraEnabled);
}
