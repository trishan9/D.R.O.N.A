"use client";

/**
 * Renders a bias flag's evidence: the student's own question with the words that
 * triggered the flag highlighted in place.
 *
 * The shipped detector (rules ∪ RAG-LLM) requires every flag to quote the exact
 * span that caused it, and verifies that quote against the question before the
 * flag is accepted. Those quotes arrive in `detected_signal` wrapped in double
 * quotes. When one is present and really occurs in the question, showing it in
 * context is far better explainability than "matched a pattern" - the student can
 * see precisely which of their own words the system reacted to, and disagree.
 *
 * Rule-based flags describe a pattern rather than quoting one, so they fall back
 * to plain text. Both cases are expected; neither is an error.
 */

import * as React from "react";

/** Pull the quoted span out of a detected_signal, if it is one. */
export function extractQuotedSpan(signal: string): string | null {
  const m = signal.match(/^"(.+)"$/s);
  if (!m) return null;
  const span = m[1].trim();
  return span.length > 0 ? span : null;
}

/**
 * Locate `needle` inside `haystack`, ignoring case and whitespace differences.
 *
 * Matching is done with a whitespace-flexible regex against the ORIGINAL string,
 * so the offsets it returns already refer to the original and never need to be
 * remapped from a normalised copy. That remapping was the only fiddly part of
 * this component, and this avoids it entirely.
 */
export function findSpan(
  haystack: string,
  needle: string,
): { start: number; end: number } | null {
  const trimmed = needle.trim();
  if (!trimmed) return null;

  // Escape regex metacharacters, then let any whitespace run match any other.
  const pattern = trimmed
    .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\s+/g, "\\s+");

  const match = new RegExp(pattern, "i").exec(haystack);
  return match ? { start: match.index, end: match.index + match[0].length } : null;
}

export function EvidenceSpan({
  signal,
  queryText,
  className,
}: {
  signal: string;
  queryText?: string | null;
  className?: string;
}) {
  const span = extractQuotedSpan(signal);

  // No quoted span (a rule-based pattern description), or no question to show it
  // in - render the signal as-is rather than pretending to have evidence.
  if (!span || !queryText) {
    return <span className={className}>{signal}</span>;
  }

  const hit = findSpan(queryText, span);
  if (!hit) {
    // The span did not occur in this question. The detector's grounding check
    // should prevent this, so show the quote plainly rather than mis-highlighting.
    return <span className={className}>&ldquo;{span}&rdquo;</span>;
  }

  return (
    <span className={className}>
      <span className="text-muted-foreground">{queryText.slice(0, hit.start)}</span>
      <mark className="rounded bg-amber-500/25 px-0.5 font-medium text-foreground">
        {queryText.slice(hit.start, hit.end)}
      </mark>
      <span className="text-muted-foreground">{queryText.slice(hit.end)}</span>
    </span>
  );
}

/** Badge distinguishing a verified quote from a pattern match. */
export function EvidenceKindBadge({ signal }: { signal: string }) {
  const quoted = extractQuotedSpan(signal) !== null;
  return (
    <span
      className={
        quoted
          ? "rounded bg-tier-nepal/15 px-1.5 py-0.5 text-[10px] font-medium text-tier-nepal"
          : "rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
      }
      title={
        quoted
          ? "The model quoted these exact words and the quote was verified against your question"
          : "Matched a hand-written linguistic pattern"
      }
    >
      {quoted ? "verified quote" : "pattern match"}
    </span>
  );
}
