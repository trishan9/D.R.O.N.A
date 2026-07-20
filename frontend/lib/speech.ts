/**
 * Browser speech in and out, for the web counselling session.
 *
 * WHY THE BROWSER AND NOT THE ROBOT'S TTS
 * ---------------------------------------
 * The robot speaks through speech_node (espeak / piper / ElevenLabs) inside WSL.
 * The web counsellor cannot use that: it would need audio piped out of WSL, and
 * a student opening the dashboard on their own laptop has no ROS2 at all. The
 * Web Speech API is already in the browser, needs no key, no network and no
 * install, and gives Nepali students a voice session on any Chromium browser.
 *
 * SUPPORT IS UNEVEN AND THAT IS HANDLED, NOT HIDDEN
 * -------------------------------------------------
 * SpeechRecognition is Chromium-only (Chrome, Edge) and is prefixed. Firefox and
 * Safari have no recognition at all. Nepali (ne-NP) recognition exists on some
 * platforms and not others, and Nepali synthesis voices are rarer still. Rather
 * than pretend, `speechSupport()` reports exactly what this browser can do so
 * the UI can say so and fall back to typing.
 */

export type SpeechLang = "en-US" | "ne-NP" | "hi-IN";

interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
  onend: (() => void) | null;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<
    ArrayLike<{ transcript: string; confidence: number }> & { isFinal: boolean }
  >;
}

type RecognitionCtor = new () => SpeechRecognitionLike;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface SpeechSupport {
  recognition: boolean;
  synthesis: boolean;
  /** Voice locales the browser can actually speak, e.g. ["en-US", "ne-NP"]. */
  voiceLangs: string[];
  hasNepaliVoice: boolean;
}

export function speechSupport(): SpeechSupport {
  if (typeof window === "undefined") {
    return { recognition: false, synthesis: false, voiceLangs: [], hasNepaliVoice: false };
  }
  const synthesis = "speechSynthesis" in window;
  const voices = synthesis ? window.speechSynthesis.getVoices() : [];
  const voiceLangs = [...new Set(voices.map((v) => v.lang))].sort();
  return {
    recognition: recognitionCtor() !== null,
    synthesis,
    voiceLangs,
    hasNepaliVoice: voiceLangs.some((l) => l.toLowerCase().startsWith("ne")),
  };
}

/**
 * Start listening. Returns a stop function, or null if unsupported.
 *
 * `onPartial` fires with interim text so the student sees words appear as they
 * speak - without it, holding the mic feels broken.
 */
export function listen(opts: {
  lang: SpeechLang;
  onPartial: (text: string) => void;
  onFinal: (text: string) => void;
  onError?: (err: string) => void;
  onEnd?: () => void;
}): (() => void) | null {
  const Ctor = recognitionCtor();
  if (!Ctor) return null;

  const rec = new Ctor();
  rec.lang = opts.lang;
  rec.continuous = false;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  let finalText = "";
  rec.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i += 1) {
      const r = e.results[i];
      const chunk = r[0]?.transcript ?? "";
      if (r.isFinal) finalText += chunk;
      else interim += chunk;
    }
    if (interim) opts.onPartial(finalText + interim);
  };
  rec.onerror = (e) => opts.onError?.(e.error ?? "speech recognition failed");
  rec.onend = () => {
    if (finalText.trim()) opts.onFinal(finalText.trim());
    opts.onEnd?.();
  };

  try {
    rec.start();
  } catch {
    return null;
  }
  return () => {
    try {
      rec.stop();
    } catch {
      /* already stopped */
    }
  };
}

/**
 * Speak text aloud, picking the best available voice for the language.
 *
 * Falls back through ne -> hi -> default: Devanagari read by a Hindi voice is
 * imperfect but far closer than an English voice attempting Nepali, and many
 * systems ship hi-IN without ne-NP.
 */
export function speak(
  text: string,
  lang: "en" | "ne",
  onEnd?: () => void,
): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  if (!text.trim()) return false;

  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  const voices = window.speechSynthesis.getVoices();

  const pick = (prefix: string) =>
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix));

  const voice =
    lang === "ne" ? (pick("ne") ?? pick("hi") ?? voices[0]) : (pick("en") ?? voices[0]);

  if (voice) {
    utt.voice = voice;
    utt.lang = voice.lang;
  } else {
    utt.lang = lang === "ne" ? "ne-NP" : "en-US";
  }
  // Slightly slower than default: advice with module codes and numbers in it is
  // hard to follow at the browser's default rate.
  utt.rate = 0.95;
  utt.pitch = 1.0;
  if (onEnd) utt.onend = onEnd;

  window.speechSynthesis.speak(utt);
  return true;
}

export function stopSpeaking(): void {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

/** Which recognition locale to listen in, given the student's language choice. */
export function recognitionLang(pref: "auto" | "en" | "ne"): SpeechLang {
  // "auto" listens in English: Nepali students code-switch heavily and Chromium's
  // en-US model transcribes Romanised Nepali words far more usefully than ne-NP
  // handles embedded English. The transcript is then language-detected as text,
  // which is where the real routing decision happens.
  if (pref === "ne") return "ne-NP";
  return "en-US";
}
