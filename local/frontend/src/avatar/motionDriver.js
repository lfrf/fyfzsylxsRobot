const MOTION_ALIASES = {
  steady: "steady",
  idle: "steady",
  still: "steady",

  nod: "slow_nod",
  gentle_nod: "slow_nod",
  supportive_nod: "slow_nod",
  slow_nod: "slow_nod",

  attentive: "attentive_lean",
  attentive_lean: "attentive_lean",
  lean_forward: "attentive_lean",
  listen: "attentive_lean",

  tilt_left: "soft_tilt_left",
  soft_tilt_left: "soft_tilt_left",
  concern_tilt_left: "soft_tilt_left",

  tilt_right: "soft_tilt_right",
  soft_tilt_right: "soft_tilt_right",
  concern_tilt_right: "soft_tilt_right",

  open_gesture: "open_gesture",
  hand_open: "open_gesture",
  reassuring_open: "open_gesture",
};

function normalizeMotion(value, fallbackMotion) {
  const raw = String(value || fallbackMotion || "steady").trim().toLowerCase();
  return MOTION_ALIASES[raw] || "steady";
}

function resolveGesture(motionName) {
  if (motionName === "open_gesture") {
    return "open";
  }
  return "none";
}

function resolveStrength(cue) {
  const raw = Number(cue?.intensity);
  if (Number.isFinite(raw)) {
    const clamped = Math.max(0.2, Math.min(raw, 1.4));
    return clamped.toFixed(2);
  }
  return "1.00";
}

function applyMotionCue(faceElement, cue, fallbackMotion) {
  const motionName = normalizeMotion(cue?.motion, fallbackMotion);
  faceElement.dataset.motion = motionName;
  faceElement.dataset.gesture = resolveGesture(motionName);
  faceElement.dataset.motionStrength = resolveStrength(cue);
}

export function applyMotionSequence(faceElement, sequence, fallbackMotion) {
  const timers = [];
  applyMotionCue(faceElement, null, fallbackMotion);

  if (!sequence?.length) {
    return () => {
      applyMotionCue(faceElement, null, fallbackMotion);
    };
  }

  sequence.forEach((cue) => {
    const timerId = window.setTimeout(() => {
      applyMotionCue(faceElement, cue, fallbackMotion);
    }, cue.start_ms || 0);
    timers.push(timerId);
  });

  return () => {
    timers.forEach((timerId) => window.clearTimeout(timerId));
    applyMotionCue(faceElement, null, fallbackMotion);
  };
}
