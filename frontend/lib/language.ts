/**
 * Client-side language detection - mirrors drona/utils/language.py exactly.
 *
 * The backend already auto-detects the query language and routes Nepali to the
 * Nepali-specialised model, so this is purely so the UI can *show* the student
 * what is about to happen ("Nepali detected - answering in Nepali"). Keeping the
 * same Devanagari-ratio rule and threshold means the badge never disagrees with
 * what the server actually does.
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
export function detectLanguage(text: string, threshold = 0.1): Language {
  return devanagariRatio(text) >= threshold ? "ne" : "en";
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
];
