import { createAvatarRenderer } from "../avatar/renderer";

const STREAM_URL_STORAGE_KEY = "a22.avatar.external_stream_url";
const AVATAR_PROFILE_STORAGE_KEY = "a22.avatar.profile_id";
const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

function normalizeStreamUrl(raw) {
  return String(raw || "").trim();
}

function readBooleanFlag(rawValue) {
  return TRUE_VALUES.has(String(rawValue || "").trim().toLowerCase());
}

function isLikelyMediaUrl(url) {
  const lower = String(url || "").toLowerCase();
  if (!lower) {
    return false;
  }
  if (lower.startsWith("blob:") || lower.startsWith("data:video/")) {
    return true;
  }
  return [".mp4", ".webm", ".m3u8", ".mov", ".ogg", ".ogv"].some((suffix) => lower.includes(suffix));
}

function readInitialStreamUrl() {
  try {
    const queryUrl = new URLSearchParams(window.location.search).get("avatar_stream");
    if (queryUrl) {
      return normalizeStreamUrl(queryUrl);
    }
  } catch {
    // Ignore malformed query string and keep fallback behavior.
  }

  try {
    return normalizeStreamUrl(localStorage.getItem(STREAM_URL_STORAGE_KEY) || "");
  } catch {
    return "";
  }
}

function persistStreamUrl(url) {
  try {
    if (url) {
      localStorage.setItem(STREAM_URL_STORAGE_KEY, url);
      return;
    }
    localStorage.removeItem(STREAM_URL_STORAGE_KEY);
  } catch {
    // Ignore storage failures in private mode / restricted environments.
  }
}

function readInitialAvatarProfileId() {
  try {
    const queryProfileId = new URLSearchParams(window.location.search).get("avatar_profile_id");
    if (queryProfileId) {
      return String(queryProfileId).trim();
    }
  } catch {
    // Ignore malformed query string and keep fallback behavior.
  }

  try {
    return String(localStorage.getItem(AVATAR_PROFILE_STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

function persistAvatarProfileId(profileId) {
  try {
    if (profileId) {
      localStorage.setItem(AVATAR_PROFILE_STORAGE_KEY, profileId);
      return;
    }
    localStorage.removeItem(AVATAR_PROFILE_STORAGE_KEY);
  } catch {
    // Ignore storage failures in private mode / restricted environments.
  }
}

function readSourceControlsEnabled() {
  const envValue = import.meta.env.VITE_SHOW_AVATAR_SOURCE_CONTROLS;
  if (readBooleanFlag(envValue)) {
    return true;
  }

  try {
    const queryValue = new URLSearchParams(window.location.search).get("avatar_source_controls");
    return readBooleanFlag(queryValue);
  } catch {
    return false;
  }
}

function readDefaultPortraitUrl() {
  const envUrl = String(import.meta.env.VITE_AVATAR_PORTRAIT_URL || "").trim();
  if (envUrl) {
    return envUrl;
  }
  // Add a cache buster so replacing public/avatar-portrait.png takes effect immediately.
  return "./avatar-portrait.png?v=20260421";
}

function readAvatarProfiles(defaultPortraitUrl) {
  const defaultProfileId = String(import.meta.env.VITE_AVATAR_PROFILE_DEFAULT_ID || "avatar_a").trim() || "avatar_a";
  const defaultProfileName = String(import.meta.env.VITE_AVATAR_PROFILE_DEFAULT_NAME || "Digital Human A").trim()
    || "Digital Human A";

  const altProfileId = String(import.meta.env.VITE_AVATAR_PROFILE_ALT_ID || "avatar_b").trim() || "avatar_b";
  const altProfileName = String(import.meta.env.VITE_AVATAR_PROFILE_ALT_NAME || "Digital Human B").trim()
    || "Digital Human B";
  const altPortraitUrl = String(
    import.meta.env.VITE_AVATAR_PROFILE_ALT_PORTRAIT_URL || "./avatar-portrait-alt.png?v=20260421",
  ).trim();

  const profiles = [
    { id: defaultProfileId, name: defaultProfileName, portraitUrl: defaultPortraitUrl },
  ];

  if (altProfileId && altProfileId !== defaultProfileId && altPortraitUrl) {
    profiles.push({ id: altProfileId, name: altProfileName, portraitUrl: altPortraitUrl });
  }

  return profiles;
}

export function createAvatarPanel({ onProfileChange } = {}) {
  const sourceControlsEnabled = readSourceControlsEnabled();
  const defaultPortraitUrl = readDefaultPortraitUrl();
  const avatarProfiles = readAvatarProfiles(defaultPortraitUrl);
  const element = document.createElement("section");
  element.className = "avatar-panel";
  if (sourceControlsEnabled) {
    element.classList.add("avatar-panel--show-source-controls");
  }
  element.innerHTML = `
    <div class="avatar-profile-controls">
      <div class="avatar-profile-heading">
        <p class="eyebrow">Avatar Profile</p>
        <span class="chip" data-role="avatar-profile-chip">Pending</span>
      </div>
      <div class="avatar-profile-row">
        <p class="avatar-profile-name" data-role="avatar-profile-name">-</p>
        <button type="button" class="secondary-button avatar-profile-button" data-role="avatar-profile-toggle">
          Switch Avatar
        </button>
      </div>
    </div>
    <div class="avatar-source-controls">
      <div class="avatar-source-heading">
        <p class="eyebrow">D - Avatar Source</p>
        <span class="chip" data-role="avatar-source-chip">Portrait fallback</span>
      </div>
      <div class="avatar-source-row">
        <input
          class="avatar-source-input"
          data-role="avatar-source-input"
          type="text"
          placeholder="Paste UE URL (media URL or Pixel Streaming page URL)"
        />
        <button type="button" class="secondary-button avatar-source-button" data-role="avatar-source-connect">
          Connect
        </button>
        <button type="button" class="secondary-button avatar-source-button" data-role="avatar-source-disconnect">
          Disconnect
        </button>
      </div>
      <p class="avatar-source-meta" data-role="avatar-source-meta">
        Using portrait fallback. Connect a UE URL to show the real digital human.
      </p>
    </div>
    <div class="avatar-stage avatar-stage--portrait-only">
      <div
        class="avatar-face avatar-face--portrait"
        data-expression="neutral"
        data-motion="steady"
        data-viseme="sil"
        data-gesture="none"
        data-motion-strength="1.00"
        data-emotion-style="supportive"
      >
        <div class="avatar-halo"></div>
        <div class="avatar-portrait-shell">
          <img
            class="avatar-portrait-image"
            src="${defaultPortraitUrl}"
            alt="Digital human portrait"
          />
          <video
            class="avatar-video hidden"
            muted
            playsinline
            autoplay
          ></video>
          <iframe
            class="avatar-embed-frame hidden"
            data-role="avatar-embed-frame"
            title="External avatar stream"
            allow="autoplay; fullscreen; camera; microphone; clipboard-read; clipboard-write"
            referrerpolicy="no-referrer"
          ></iframe>
          <div class="avatar-gesture-overlay" aria-hidden="true">
            <span class="gesture-orb gesture-orb-left"></span>
            <span class="gesture-orb gesture-orb-right"></span>
          </div>
        </div>
      </div>
    </div>
  `;

  const face = element.querySelector(".avatar-face");
  const streamInput = element.querySelector('[data-role="avatar-source-input"]');
  const connectButton = element.querySelector('[data-role="avatar-source-connect"]');
  const disconnectButton = element.querySelector('[data-role="avatar-source-disconnect"]');
  const sourceChip = element.querySelector('[data-role="avatar-source-chip"]');
  const sourceMeta = element.querySelector('[data-role="avatar-source-meta"]');
  const profileChip = element.querySelector('[data-role="avatar-profile-chip"]');
  const profileName = element.querySelector('[data-role="avatar-profile-name"]');
  const profileToggleButton = element.querySelector('[data-role="avatar-profile-toggle"]');
  const portraitImage = element.querySelector(".avatar-portrait-image");
  const avatarVideo = element.querySelector(".avatar-video");
  const embedFrame = element.querySelector('[data-role="avatar-embed-frame"]');

  const renderer = createAvatarRenderer({
    faceElement: face,
    readouts: null,
  });

  let selectedAvatarProfile = avatarProfiles[0] || {
    id: "avatar_a",
    name: "Digital Human A",
    portraitUrl: defaultPortraitUrl,
  };

  face.dataset.externalPage = "off";

  function updateProfileUi(profile) {
    if (!profile) {
      return;
    }
    profileChip.textContent = profile.id;
    profileName.textContent = profile.name;
    profileToggleButton.disabled = avatarProfiles.length <= 1;
  }

  function applyProfilePortrait(profile) {
    if (!portraitImage || !profile?.portraitUrl) {
      return;
    }
    portraitImage.src = profile.portraitUrl;
  }

  function applyAvatarProfile(profile, { persist = true, notify = true } = {}) {
    if (!profile) {
      return;
    }
    // Force portrait mode when switching profile so a previously playing reply video
    // does not keep covering the new portrait.
    renderer.cleanup();
    selectedAvatarProfile = profile;
    updateProfileUi(profile);
    applyProfilePortrait(profile);
    portraitImage?.classList.remove("hidden");

    if (persist) {
      persistAvatarProfileId(profile.id);
    }
    if (notify) {
      onProfileChange?.({
        id: profile.id,
        name: profile.name,
        portraitUrl: profile.portraitUrl,
      });
    }
  }

  function setSourceUi({ chipText, metaText, connected }) {
    sourceChip.textContent = chipText;
    sourceMeta.textContent = metaText;
    connectButton.disabled = connected;
    disconnectButton.disabled = !connected;
  }

  function setEmbedFrame(url) {
    const safeUrl = normalizeStreamUrl(url);
    if (!embedFrame) {
      return;
    }
    if (!safeUrl) {
      embedFrame.classList.add("hidden");
      embedFrame.removeAttribute("src");
      return;
    }
    embedFrame.classList.remove("hidden");
    embedFrame.src = safeUrl;
  }

  function connectExternalStream(rawUrl) {
    const url = normalizeStreamUrl(rawUrl);
    if (!url) {
      setSourceUi({
        chipText: "Portrait fallback",
        metaText: "Please provide a non-empty URL before connecting.",
        connected: false,
      });
      return false;
    }

    if (isLikelyMediaUrl(url)) {
      face.dataset.externalPage = "off";
      setEmbedFrame("");
      const applied = renderer.setPinnedVideoSource(url);
      if (!applied) {
        setSourceUi({
          chipText: "Portrait fallback",
          metaText: "Failed to bind the media URL. Check format and try again.",
          connected: false,
        });
        return false;
      }

      streamInput.value = url;
      persistStreamUrl(url);
      setSourceUi({
        chipText: "External media",
        metaText: `Connecting media stream: ${url}`,
        connected: true,
      });
      return true;
    }

    renderer.clearPinnedVideoSource();
    face.dataset.externalPage = "on";
    setEmbedFrame(url);
    if (streamInput) {
      streamInput.value = url;
    }
    persistStreamUrl(url);
    setSourceUi({
      chipText: "External page",
      metaText: `Embedding external page: ${url}`,
      connected: true,
    });
    return true;
  }

  function disconnectExternalStream(message = "External source disconnected. Switched back to portrait fallback.") {
    renderer.clearPinnedVideoSource();
    face.dataset.externalPage = "off";
    setEmbedFrame("");
    persistStreamUrl("");
    setSourceUi({
      chipText: "Portrait fallback",
      metaText: message,
      connected: false,
    });
  }

  profileToggleButton.addEventListener("click", () => {
    if (avatarProfiles.length <= 1) {
      return;
    }
    const currentIndex = avatarProfiles.findIndex((item) => item.id === selectedAvatarProfile.id);
    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % avatarProfiles.length : 0;
    const nextProfile = avatarProfiles[nextIndex];
    applyAvatarProfile(nextProfile);
  });

  portraitImage?.addEventListener("error", () => {
    if (!selectedAvatarProfile) {
      return;
    }
    if (selectedAvatarProfile.portraitUrl === defaultPortraitUrl) {
      return;
    }
    applyProfilePortrait({ portraitUrl: defaultPortraitUrl });
    setSourceUi({
      chipText: "Portrait fallback",
      metaText: `Failed to load ${selectedAvatarProfile.portraitUrl}. Fallback portrait is used.`,
      connected: false,
    });
  });

  connectButton.addEventListener("click", () => {
    connectExternalStream(streamInput.value);
  });

  disconnectButton.addEventListener("click", () => {
    disconnectExternalStream();
  });

  streamInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    connectExternalStream(streamInput.value);
  });

  avatarVideo?.addEventListener("loadeddata", () => {
    if (!renderer.hasPinnedVideoSource()) {
      return;
    }
    const activeUrl = renderer.getPinnedVideoSource();
    setSourceUi({
      chipText: "External media",
      metaText: `External media stream connected: ${activeUrl}`,
      connected: true,
    });
  });

  avatarVideo?.addEventListener("error", () => {
    if (!renderer.hasPinnedVideoSource()) {
      return;
    }
    const activeUrl = renderer.getPinnedVideoSource();
    setSourceUi({
      chipText: "External media error",
      metaText: `Failed to load ${activeUrl}. Check CORS/URL and stream availability.`,
      connected: true,
    });
  });

  embedFrame?.addEventListener("load", () => {
    if (face.dataset.externalPage !== "on") {
      return;
    }
    const activeUrl = normalizeStreamUrl(streamInput.value);
    setSourceUi({
      chipText: "External page",
      metaText: `External page loaded: ${activeUrl}`,
      connected: true,
    });
  });

  embedFrame?.addEventListener("error", () => {
    if (face.dataset.externalPage !== "on") {
      return;
    }
    const activeUrl = normalizeStreamUrl(streamInput.value);
    setSourceUi({
      chipText: "External page error",
      metaText: `Failed to load ${activeUrl}. Try opening this URL in a new tab first.`,
      connected: true,
    });
  });

  setSourceUi({
    chipText: "Portrait fallback",
    metaText: "Using portrait fallback. Connect a UE URL to show the real digital human.",
    connected: false,
  });
  const initialProfileId = readInitialAvatarProfileId();
  const initialProfile = avatarProfiles.find((item) => item.id === initialProfileId) || avatarProfiles[0];
  applyAvatarProfile(initialProfile, { persist: false, notify: true });

  const initialUrl = readInitialStreamUrl();
  if (sourceControlsEnabled && initialUrl) {
    if (streamInput) {
      streamInput.value = initialUrl;
    }
    connectExternalStream(initialUrl);
  }
  if (!sourceControlsEnabled) {
    disconnectExternalStream("Using portrait fallback mode.");
  }

  const api = {
    element,
    currentEmotionStyle: "supportive",
    currentFacialExpression: "neutral",
    currentHeadMotion: "steady",
    getSelectedProfileId() {
      return selectedAvatarProfile?.id || avatarProfiles[0]?.id || "avatar_a";
    },
    update(response) {
      api.currentEmotionStyle = response.emotion_style || api.currentEmotionStyle;
      api.currentFacialExpression = response.avatar_action?.facial_expression || api.currentFacialExpression;
      api.currentHeadMotion = response.avatar_action?.head_motion || api.currentHeadMotion;
      renderer.render(response);
    },
  };

  return api;
}
