import { createBrowserSpeechHintRecognizer } from "./browserSpeechHint";

function getAudioContextCtor() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.AudioContext || window.webkitAudioContext || null;
}

function mergePcmChunks(chunks, frameCount) {
  const merged = new Float32Array(frameCount);
  let offset = 0;

  chunks.forEach((chunk) => {
    merged.set(chunk, offset);
    offset += chunk.length;
  });

  return merged;
}

function clampSample(value) {
  return Math.max(-1, Math.min(1, value));
}

function writePcm16(view, offset, input) {
  for (let index = 0; index < input.length; index += 1) {
    const sample = clampSample(input[index]);
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }
}

function writeAscii(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function createWavBuffer(samples, sampleRate, channelCount) {
  const bytesPerSample = 2;
  const blockAlign = channelCount * bytesPerSample;
  const dataLength = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channelCount, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, dataLength, true);
  writePcm16(view, 44, samples);

  return buffer;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, offset + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return window.btoa(binary);
}

function buildTurnWindowId(startedAt) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `turn-${crypto.randomUUID()}`;
  }
  return `turn-${startedAt}`;
}

export function createAudioTurnRecorder({ speechLang = "zh-CN" } = {}) {
  const speechHintRecognizer = createBrowserSpeechHintRecognizer({ lang: speechLang });

  let mediaStream = null;
  let audioContext = null;
  let sourceNode = null;
  let processorNode = null;
  let pcmChunks = [];
  let totalFrames = 0;
  let sampleRate = 16000;
  let startedAt = 0;

  async function cleanup({ cancelSpeechHint = false } = {}) {
    if (cancelSpeechHint) {
      speechHintRecognizer.cancel();
    }

    if (processorNode) {
      processorNode.disconnect();
      processorNode.onaudioprocess = null;
      processorNode = null;
    }

    if (sourceNode) {
      sourceNode.disconnect();
      sourceNode = null;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }

    if (audioContext) {
      try {
        await audioContext.close();
      } catch {
        // Ignore browser-specific close failures.
      }
      audioContext = null;
    }
  }

  return {
    async start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support microphone capture.");
      }

      const AudioContextCtor = getAudioContextCtor();
      if (!AudioContextCtor) {
        throw new Error("This browser does not support Web Audio capture.");
      }

      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      audioContext = new AudioContextCtor();
      await audioContext.resume();

      pcmChunks = [];
      totalFrames = 0;
      sampleRate = audioContext.sampleRate;
      startedAt = Date.now();

      sourceNode = audioContext.createMediaStreamSource(mediaStream);
      processorNode = audioContext.createScriptProcessor(4096, 1, 1);
      processorNode.onaudioprocess = (event) => {
        const channelData = event.inputBuffer.getChannelData(0);
        const nextChunk = new Float32Array(channelData.length);
        nextChunk.set(channelData);
        pcmChunks.push(nextChunk);
        totalFrames += nextChunk.length;
      };

      sourceNode.connect(processorNode);
      processorNode.connect(audioContext.destination);
      speechHintRecognizer.start();

      return {
        sampleRate,
        channels: 1,
      };
    },
    async stop() {
      if (!mediaStream || !audioContext) {
        return null;
      }

      const transcriptPromise = speechHintRecognizer.stop();
      const merged = mergePcmChunks(pcmChunks, totalFrames);
      const wavBuffer = createWavBuffer(merged, sampleRate, 1);
      const transcriptHint = await transcriptPromise;
      const durationSeconds = totalFrames > 0 ? totalFrames / sampleRate : 0;
      const stoppedAt = Date.now();
      const windowDurationMs = Math.max(Math.round(durationSeconds * 1000), stoppedAt - startedAt);

      await cleanup();

      return {
        audio_base64: arrayBufferToBase64(wavBuffer),
        audio_format: "wav",
        audio_duration_ms: windowDurationMs,
        audio_sample_rate_hz: sampleRate,
        audio_channels: 1,
        client_asr_text: transcriptHint || undefined,
        client_asr_source: transcriptHint ? "browser_speech_api" : undefined,
        turn_time_window: {
          window_id: buildTurnWindowId(startedAt),
          source_clock: "browser_epoch_ms",
          transport_mode: "http_turn",
          capture_started_at_ms: startedAt,
          capture_ended_at_ms: stoppedAt,
          audio_started_at_ms: startedAt,
          audio_ended_at_ms: stoppedAt,
          window_duration_ms: windowDurationMs,
        },
      };
    },
    async cancel() {
      await cleanup({ cancelSpeechHint: true });
      pcmChunks = [];
      totalFrames = 0;
    },
  };
}
