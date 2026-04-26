export function applyVisemeSequence(faceElement, sequence) {
  const timers = [];
  faceElement.dataset.viseme = "sil";

  sequence.forEach((cue) => {
    const timerId = window.setTimeout(() => {
      faceElement.dataset.viseme = cue.label || "sil";
    }, cue.start_ms || 0);
    timers.push(timerId);
  });

  const resetId = window.setTimeout(() => {
    faceElement.dataset.viseme = "sil";
  }, sequence.length ? sequence[sequence.length - 1].end_ms || 0 : 0);
  timers.push(resetId);

  return () => {
    timers.forEach((timerId) => window.clearTimeout(timerId));
    faceElement.dataset.viseme = "sil";
  };
}
