export function createChatPanel() {
  const element = document.createElement("section");
  element.className = "chat-panel";
  element.innerHTML = `
    <div class="panel-heading">
      <div>
        <p class="eyebrow">B · Conversation</p>
        <h2>Chat Timeline</h2>
      </div>
      <span class="chip">Remote structured response</span>
    </div>
    <div class="chat-log" data-role="chat-log"></div>
    <div class="loading-indicator hidden" data-role="loading-indicator">Waiting for remote orchestrator...</div>
  `;

  const log = element.querySelector('[data-role="chat-log"]');
  const loadingIndicator = element.querySelector('[data-role="loading-indicator"]');

  return {
    element,
    addMessage({ role, text, meta }) {
      const item = document.createElement("article");
      item.className = `message-card ${role}`;
      item.innerHTML = `
        <div class="message-role">${role === "assistant" ? "Digital Human" : "User"}</div>
        <p class="message-text"></p>
        <div class="message-meta">${meta}</div>
      `;
      item.querySelector(".message-text").textContent = text;
      log.appendChild(item);
      log.scrollTop = log.scrollHeight;
    },
    addSystemMessage(text) {
      const item = document.createElement("article");
      item.className = "message-card system";
      item.innerHTML = `
        <div class="message-role">System</div>
        <p class="message-text"></p>
      `;
      item.querySelector(".message-text").textContent = text;
      log.appendChild(item);
      log.scrollTop = log.scrollHeight;
    },
    setLoading(isLoading) {
      loadingIndicator.classList.toggle("hidden", !isLoading);
    },
  };
}
