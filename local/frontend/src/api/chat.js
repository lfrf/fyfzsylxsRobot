function resolveChatEndpoint() {
  const directApiBase = import.meta.env.VITE_USE_DIRECT_API === "true"
    ? import.meta.env.VITE_API_BASE
    : "";

  if (directApiBase) {
    return `${directApiBase.replace(/\/$/, "")}/chat`;
  }

  return "/api/chat";
}

export async function sendChatRequest(payload) {
  const response = await fetch(resolveChatEndpoint(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || `The server returned HTTP ${response.status}.`;
    throw new Error(detail);
  }

  return data;
}
