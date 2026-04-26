export function createCameraPanel({ onToggle }) {
  const element = document.createElement("section");
  element.className = "camera-panel";
  element.innerHTML = `
    <div class="camera-panel-header">
      <div>
        <p class="camera-panel-title">Camera input</p>
        <p class="camera-panel-meta" data-role="camera-meta">Camera disabled. No local rolling buffer is active.</p>
      </div>
      <button type="button" class="secondary-button" data-role="camera-toggle">Enable camera</button>
    </div>
    <div class="camera-preview-shell" data-state="disabled">
      <video class="camera-preview" autoplay muted playsinline></video>
      <div class="camera-preview-overlay" data-role="camera-overlay">Camera off</div>
    </div>
  `;

  const toggleButton = element.querySelector('[data-role="camera-toggle"]');
  const meta = element.querySelector('[data-role="camera-meta"]');
  const overlay = element.querySelector('[data-role="camera-overlay"]');
  const previewShell = element.querySelector(".camera-preview-shell");
  const preview = element.querySelector(".camera-preview");

  let enabled = false;
  let busy = false;

  function sync() {
    toggleButton.disabled = busy;
    toggleButton.textContent = enabled ? "Disable camera" : "Enable camera";
    previewShell.dataset.state = enabled ? "enabled" : "disabled";
    overlay.textContent = enabled ? "Live preview + rolling buffer" : "Camera off";
  }

  toggleButton.addEventListener("click", async () => {
    if (busy) {
      return;
    }

    busy = true;
    sync();
    try {
      const nextEnabled = await onToggle(!enabled);
      enabled = nextEnabled;
    } finally {
      busy = false;
      sync();
    }
  });

  sync();

  return {
    element,
    preview,
    setEnabled(nextEnabled) {
      enabled = nextEnabled;
      sync();
    },
    setBusy(nextBusy) {
      busy = nextBusy;
      sync();
    },
    setMeta(text) {
      meta.textContent = text;
    },
  };
}
