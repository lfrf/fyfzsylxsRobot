export function createAudioPlayer() {
  let currentAudio = null;

  function stop() {
    if (!currentAudio) {
      return;
    }
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }

  return {
    play(audioCue) {
      stop();

      if (!audioCue?.audio_url) {
        return;
      }

      currentAudio = new Audio(audioCue.audio_url);
      currentAudio.play().catch(() => {
        currentAudio = null;
      });
    },
    stop,
  };
}
