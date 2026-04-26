export function createStatusBar() {
  const element = document.createElement("section");
  element.className = "status-panel";
  element.innerHTML = `
    <div class="panel-heading">
      <div>
        <p class="eyebrow">A · Status</p>
        <h2>Edge / Remote Runtime</h2>
      </div>
      <span class="chip">Session-aware</span>
    </div>
    <div class="status-scroll-shell">
      <dl class="status-grid">
        <div><dt>Session</dt><dd data-role="session-id"></dd></div>
        <div><dt>Stream</dt><dd data-role="stream-id"></dd></div>
        <div><dt>Next turn</dt><dd data-role="next-turn"></dd></div>
        <div><dt>Transport</dt><dd data-role="transport"></dd></div>
        <div><dt>Remote</dt><dd data-role="remote-status"></dd></div>
        <div><dt>Input mode</dt><dd data-role="input-mode"></dd></div>
        <div><dt>Emotion</dt><dd data-role="emotion-style"></dd></div>
        <div><dt>Expression</dt><dd data-role="facial-expression"></dd></div>
        <div><dt>Motion</dt><dd data-role="head-motion"></dd></div>
        <div><dt>Audio</dt><dd data-role="audio-status"></dd></div>
        <div><dt>Video</dt><dd data-role="video-status"></dd></div>
      </dl>
    </div>
  `;

  const refs = {
    sessionId: element.querySelector('[data-role="session-id"]'),
    streamId: element.querySelector('[data-role="stream-id"]'),
    nextTurnId: element.querySelector('[data-role="next-turn"]'),
    transport: element.querySelector('[data-role="transport"]'),
    remoteStatus: element.querySelector('[data-role="remote-status"]'),
    inputMode: element.querySelector('[data-role="input-mode"]'),
    emotionStyle: element.querySelector('[data-role="emotion-style"]'),
    facialExpression: element.querySelector('[data-role="facial-expression"]'),
    headMotion: element.querySelector('[data-role="head-motion"]'),
    audioStatus: element.querySelector('[data-role="audio-status"]'),
    videoStatus: element.querySelector('[data-role="video-status"]'),
  };

  return {
    element,
    update(snapshot) {
      refs.sessionId.textContent = snapshot.sessionId;
      refs.streamId.textContent = snapshot.streamId;
      refs.nextTurnId.textContent = snapshot.nextTurnId;
      refs.transport.textContent = snapshot.transport;
      refs.remoteStatus.textContent = snapshot.remoteStatus;
      refs.inputMode.textContent = snapshot.inputMode;
      refs.emotionStyle.textContent = snapshot.emotionStyle;
      refs.facialExpression.textContent = snapshot.facialExpression;
      refs.headMotion.textContent = snapshot.headMotion;
      refs.audioStatus.textContent = snapshot.audioStatus;
      refs.videoStatus.textContent = snapshot.videoStatus;
    },
  };
}
