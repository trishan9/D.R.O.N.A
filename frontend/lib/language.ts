/**
 * Client-side language detection - mirrors drona/utils/language.py exactly.
 *
 * The backend already auto-detects the query language and routes Nepali to the
 * Nepali-specialised model, so this is purely so the UI can *show* the student
 * what is about to happen ("Nepali detected - answering in Nepali"). Keeping the
 * same rules and thresholds means the badge never disagrees with the server.
 *
 * Two signals, matching the backend:
 *   1. Devanagari script ratio.
 *   2. ROMANISED Nepali - Nepali typed in Latin script, which is how most
 *      students actually write it. That text has ratio 0.0, so script alone
 *      routed it to English.
 *
 * The marker list below is generated from _ROMAN_NEPALI_MARKERS in
 * drona/utils/language.py; tests/test_roman_nepali.py pins the behaviour, and
 * frontend and backend must be regenerated together if it changes.
 */

export type Language = "en" | "ne";

/** Devanagari Unicode block (U+0900-U+097F). */
function isDevanagari(ch: string): boolean {
  const c = ch.codePointAt(0) ?? 0;
  return c >= 0x0900 && c <= 0x097f;
}

/** Fraction of alphabetic characters that are Devanagari (0..1). */
export function devanagariRatio(text: string): number {
  const letters = [...text].filter((c) => /\p{L}/u.test(c));
  if (letters.length === 0) return 0;
  return letters.filter(isDevanagari).length / letters.length;
}

/**
 * "ne" if the text is (partly) Nepali. Threshold 0.10 matches the backend: low
 * on purpose so code-switched Nepali ("म backend engineer banna chahanchu,
 * कसरी?") is served in Nepali, while a lone Devanagari name inside a long
 * English sentence stays English.
 */
/**
 * High-frequency Romanised Nepali function words, curated for NON-COLLISION
 * with English. Content words are excluded: they are where the two languages
 * collide, and answering an English question in Nepali is more jarring to a
 * student than the reverse, so the detector errs toward English.
 */
const ROMAN_NEPALI_MARKERS = new Set([
  "aba", "abo", "agadi", "ahile", "aile", "ani", "athava", "athawa", "banna", "banne",
  "bata", "bhaeko", "bhanda", "bhaneko", "bhanne", "bhaye", "bhayo", "cha", "chahanchhu",
  "chahanchu", "chan", "chau", "chha", "chhan", "chhu", "chu", "dherai", "garcha",
  "garchha", "garchu", "gareko", "garna", "garne", "garnu", "hami", "hamilai", "hamro",
  "herchu", "herne", "hoina", "huncha", "hunchha", "hunna", "hunu", "jagir", "kaha",
  "kahile", "kasari", "kasle", "kasto", "kati", "ke", "kina", "kun", "lagi", "lai", "ma",
  "maile", "mailey", "malai", "matra", "mera", "mero", "milcha", "milchha", "naramro",
  "pachi", "padhai", "padhchu", "padhne", "pani", "parcha", "parchha", "ramro", "sakcha",
  "sakchha", "sakchu", "samma", "sanga", "sikchu", "sikne", "tapai", "tapailai", "tara",
  "thie", "thiyo", "thorai", "timi", "timro", "usko", "uslai"
]);

const ROMAN_MIN_MARKERS = 2;
const ROMAN_SHORT_QUERY_TOKENS = 6;

function tokens(text: string): string[] {
  return text.toLowerCase().split(/[^a-z]+/).filter(Boolean);
}

/** Which Romanised-Nepali markers appear (used by the UI hint). */
export function romanNepaliMarkers(text: string): string[] {
  return tokens(text).filter((t) => ROMAN_NEPALI_MARKERS.has(t));
}

/** True if Latin-script text looks like Nepali rather than English. */
export function isRomanNepali(text: string): boolean {
  const toks = tokens(text);
  if (toks.length === 0) return false;
  const hits = toks.filter((t) => ROMAN_NEPALI_MARKERS.has(t));
  if (hits.length >= ROMAN_MIN_MARKERS) return true;
  return hits.length > 0 && toks.length <= ROMAN_SHORT_QUERY_TOKENS;
}

export function detectLanguage(text: string, threshold = 0.1): Language {
  if (devanagariRatio(text) >= threshold) return "ne";
  return isRomanNepali(text) ? "ne" : "en";
}

export const LANGUAGE_LABEL: Record<Language, string> = {
  en: "English",
  ne: "नेपाली",
};

/** Example prompts, so students discover that Nepali is supported. */
export const SAMPLE_PROMPTS: { lang: Language; text: string }[] = [
  { lang: "en", text: "How do I get into data science from BSc Computing?" },
  { lang: "ne", text: "मलाई डेटा साइन्समा जान मन छ, कहाँबाट सुरु गरौं?" },
  { lang: "ne", text: "म backend engineer banna chahanchu, कसरी?" },
  { lang: "ne", text: "malai data science ramro lagcha, kun module ramro cha?" },
];
