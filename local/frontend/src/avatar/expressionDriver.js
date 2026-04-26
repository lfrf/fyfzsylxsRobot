const EXPRESSION_ALIASES = {
  neutral: "neutral",
  calm: "neutral",

  neutral_smile: "warm_smile",
  smile: "warm_smile",
  gentle_smile: "warm_smile",
  reassuring_smile: "warm_smile",

  soft_concern: "soft_concern",
  concern: "soft_concern",
  empathetic_concern: "soft_concern",

  attentive: "attentive",
  focused: "attentive",
  listening: "attentive",
};

function normalizeExpression(value, fallbackExpression) {
  const raw = String(value || fallbackExpression || "neutral").trim().toLowerCase();
  return EXPRESSION_ALIASES[raw] || "neutral";
}

function applyExpression(faceElement, cue, fallbackExpression) {
  faceElement.dataset.expression = normalizeExpression(cue?.expression, fallbackExpression);
}

export function applyExpressionSequence(faceElement, sequence, fallbackExpression) {
  const timers = [];
  applyExpression(faceElement, null, fallbackExpression);

  if (!sequence?.length) {
    return () => {
      applyExpression(faceElement, null, fallbackExpression);
    };
  }

  sequence.forEach((cue) => {
    const timerId = window.setTimeout(() => {
      applyExpression(faceElement, cue, fallbackExpression);
    }, cue.start_ms || 0);
    timers.push(timerId);
  });

  return () => {
    timers.forEach((timerId) => window.clearTimeout(timerId));
    applyExpression(faceElement, null, fallbackExpression);
  };
}
