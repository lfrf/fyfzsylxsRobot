function resolveSpeechRecognitionCtor() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function createBrowserSpeechHintRecognizer({ lang = "zh-CN" } = {}) {
  const RecognitionCtor = resolveSpeechRecognitionCtor();

  if (!RecognitionCtor) {
    return {
      isSupported: false,
      start() {},
      async stop() {
        return "";
      },
      cancel() {},
    };
  }

  const recognition = new RecognitionCtor();
  recognition.lang = lang;
  recognition.continuous = true;
  recognition.interimResults = true;

  let finalTranscript = "";
  let isActive = false;
  let stopPromise = null;
  let stopResolver = null;

  recognition.onresult = (event) => {
    let nextTranscript = "";

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      if (result.isFinal && result[0]?.transcript) {
        nextTranscript += result[0].transcript;
      }
    }

    if (nextTranscript) {
      finalTranscript = `${finalTranscript} ${nextTranscript}`.trim();
    }
  };

  recognition.onerror = () => {
    if (stopResolver) {
      stopResolver(finalTranscript.trim());
      stopResolver = null;
      stopPromise = null;
    }
  };

  recognition.onend = () => {
    isActive = false;
    if (stopResolver) {
      stopResolver(finalTranscript.trim());
      stopResolver = null;
      stopPromise = null;
    }
  };

  return {
    isSupported: true,
    start() {
      finalTranscript = "";
      stopPromise = null;
      stopResolver = null;

      try {
        recognition.start();
        isActive = true;
      } catch {
        isActive = false;
      }
    },
    async stop() {
      if (!isActive) {
        return finalTranscript.trim();
      }

      if (!stopPromise) {
        stopPromise = new Promise((resolve) => {
          stopResolver = resolve;
        });
      }

      try {
        recognition.stop();
      } catch {
        if (stopResolver) {
          stopResolver(finalTranscript.trim());
          stopResolver = null;
          stopPromise = null;
        }
      }

      return stopPromise;
    },
    cancel() {
      if (!isActive) {
        return;
      }

      try {
        recognition.abort();
      } catch {
        // Ignore browser-specific abort failures.
      }

      isActive = false;
      finalTranscript = "";
      if (stopResolver) {
        stopResolver("");
        stopResolver = null;
        stopPromise = null;
      }
    },
  };
}
