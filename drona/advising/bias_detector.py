"""
Cognitive bias detector for D.R.O.N.A. - Research Contribution C2.

Operationalises six cognitive biases identified in academic advising contexts:

  1. availability_heuristic - student over-weights a salient recent example
     ("my friend got a job at X", "I heard AI pays well")
  2. anchoring - fixation on a specific number, company, or role to the
     exclusion of alternatives ("only Google", "exactly Rs 80,000")
  3. confirmation - seeks validation of a pre-formed belief rather than
     open exploration ("isn't Python the best?", "AI is the future right?")
  4. dunning_kruger - over- or under-estimates competence relative to
     observable evidence (self-rated 5/5 on a skill they have one module in,
     or blanket self-deprecation)
  5. loss_aversion - frames the query around avoiding negatives rather than
     pursuing positives ("I'm scared of being unemployed")
  6. consistency - commits to a path because of prior public declarations or
     sunk cost ("I've told everyone I'll be a data scientist")

Design:
  Pattern matching is intentionally conservative (high precision, lower recall).
  A false positive - telling a student their question shows bias when it doesn't -
  is more harmful than a false negative. We flag only when multiple signals align.

  The module is query-only. No training. No ML model. This is deliberate:
  a rule-based approach is auditable, explainable, and safe for a welfare-adjacent
  domain where wrong inferences have real consequences.

Usage:
    detector = BiasDetector()
    flags = detector.detect(query_text, profile)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from drona.contracts import BiasFlag, StudentProfile

if TYPE_CHECKING:
    pass


# ── Compiled patterns ─────────────────────────────────────────────────────────

# Availability heuristic: anchors on a named person, event, or recent story
_AVAILABILITY_PATTERNS = [
    re.compile(r"\bmy (friend|classmate|senior|cousin|colleague|brother|sister|roommate)\b", re.I),
    re.compile(r"\bi (heard|read|saw|was told|learned)\b", re.I),
    re.compile(r"\beveryone (is|says|told me|seems to)\b", re.I),
    re.compile(r"\bpeople (are|say|told me)\b", re.I),
    re.compile(r"\b(trending|viral|hot right now|blowing up|in demand)\b", re.I),
    re.compile(r"\b(recently|lately|these days|nowadays) .{0,30}(job|salary|hire|pay)\b", re.I),
    # MEDIA / AUTHORITY anecdotes. The patterns above catch a *personal* source
    # ("my friend"); students just as often generalise from one salient media
    # item ("a YouTuber said...", "I keep seeing news about AI layoffs").
    re.compile(r"\bi (keep|kept) (seeing|hearing|reading)\b", re.I),
    re.compile(r"\b(a |some |this )?(youtuber|influencer|tiktoker|blogger|podcaster)\b", re.I),
    re.compile(r"\b(saw|read|heard|watched) (it )?(on|in) (youtube|tiktok|linkedin|instagram|facebook|reddit|the news|an article|a video)\b", re.I),
    re.compile(r"\bnews (about|says|said|that)\b", re.I),
    re.compile(r"\beverywhere i (look|see|go)\b", re.I),
    # Nepali / code-switched: the advisor is bilingual, so debiasing must be too.
    re.compile(r"मेरो\s*(साथी|दाइ|दिदी|भाइ|बहिनी|सिनियर|कजिन)"),
    re.compile(r"(साथीले|दाइले|दिदीले|सिनियरले)"),
    re.compile(r"(सबैले|मान्छेहरूले)\s*भन"),
    re.compile(r"मैले\s*(सुनें|सुनेको|पढेको|देखें)"),
]

# Anchoring: fixation on a specific target that narrows the query artificially
_ANCHORING_PATTERNS = [
    re.compile(r"\bonly (want|interested in|considering|looking at)\b", re.I),
    re.compile(r"\b(just|only|exactly|specifically) (google|microsoft|facebook|meta|amazon|ncell|nepal telecom|fonepay|esewa|khalti|leapfrog|f1soft|yomari)\b", re.I),
    re.compile(r"\bexactly\s+(rs\.?|nrs\.?|npr\.?)?\s*[\d,]+\b", re.I),
    re.compile(r"\b(won't|will not|refuse to|not going to) (consider|look at|think about)\b", re.I),
    re.compile(r"\bno matter what\b", re.I),
    re.compile(r"\b(fixed|set|decided) on\b", re.I),
    # Narrowing to a single field/company: "should I focus only on AI?"
    re.compile(r"\b(focus|focusing|concentrate|concentrating|specialise|specialize) only on\b", re.I),
    # Fixating on one concrete salary figure heard from a single example -
    # a textbook numeric anchor ("...earning Rs 80,000. How do I get there?").
    re.compile(r"\b(rs\.?|nrs\.?|npr\.?)\s*[\d,]{4,}\b", re.I),
    # Nepali: मात्र/खाली = only (narrowing); रु + figure = numeric anchor
    re.compile(r"(मात्र|मात्रै|खाली)\s*\S{0,12}\s*(जान|गर्न|काम|चाहन्छु|मन)"),
    re.compile(r"(रु\.?|रुपैयाँ)\s*[\d,]{4,}"),
]

# Confirmation bias: seeking validation rather than exploration
_CONFIRMATION_PATTERNS = [
    re.compile(r"\bisn'?t (it|that|python|java|ai|ml|data science)\b.{0,40}(right|true|correct|better|best)\b", re.I),
    re.compile(r"\b(confirm|validate|tell me i('?m| am))\b", re.I),
    re.compile(r"\bi('?m| am) right (that|about)\b", re.I),
    re.compile(r"\b(don'?t you think|don'?t you agree|do you agree|wouldn'?t you agree|you'd agree)\b", re.I),
    # Appeal to consensus - presenting a received belief and inviting agreement
    # ("Everyone says cloud is the future. What do you think?").
    re.compile(r"\b(everyone|everybody|all my friends|most people) (says?|thinks?|believes?|agrees?)\b", re.I),
    re.compile(r"\b(python|java|javascript|ai|ml|data science) is (the best|definitely|obviously|clearly|undeniably)\b", re.I),
    re.compile(r"\bjust (tell|confirm|say) (me|that)\b", re.I),
    re.compile(r"\bi (already know|already decided|know for sure) .{0,30}(right|correct)\?", re.I),
    # Bare tag questions invite agreement rather than evidence ("…, isn't it?").
    re.compile(r"(,\s*|\s)(isn'?t it|right|correct)\s*\?\s*$", re.I),
    # Nepali
    re.compile(r"(होइन\s*र|हो\s*कि\s*होइन|ठीक\s*हो\s*नि)"),
]

# Loss aversion: query framed around avoiding negatives
_LOSS_AVERSION_PATTERNS = [
    re.compile(r"\b(scared|afraid|terrified|worried|anxious|nervous) (of|about)\b", re.I),
    re.compile(r"\b(don't|do not) (want to|end up|become)\b.{0,40}(unemployed|jobless|stuck|fail|broke|homeless)\b", re.I),
    re.compile(r"\bworst (case|scenario|outcome|thing)\b", re.I),
    re.compile(r"\b(avoid|prevent|not make|never make) (a )?(mistake|wrong choice|bad decision)\b", re.I),
    re.compile(r"\bwhat if (i (fail|can'?t|don'?t)|nothing works|it doesn'?t)\b", re.I),
    re.compile(r"\b(safe|safer|safest) (option|choice|path|career|job)\b", re.I),
    re.compile(r"\bplay it safe\b", re.I),
    # "what if I end up with nothing" - loss framing without the word 'fail'
    re.compile(r"\bwhat if i (end up|lose|waste|regret)\b", re.I),
    re.compile(r"\bend up with nothing\b", re.I),
    # Nepali
    re.compile(r"(डर\s*लाग्छ|डराउँछु|डर\s*छ)"),
    re.compile(r"(गुम्ने|खेर\s*जान्छ|बर्बाद)"),
]

# Consistency bias / sunk cost: committed due to prior statements or investment
_CONSISTENCY_PATTERNS = [
    re.compile(r"\b(already|always) (told|said|planned|decided|committed)\b", re.I),
    re.compile(r"\bi'?ve (always|been|already) (wanted|planned|said)\b", re.I),
    re.compile(r"\b(can'?t|cannot) (change|switch|pivot|go back)\b.{0,30}(now|anymore|at this point)\b", re.I),
    re.compile(r"\b(too (late|far|deep|invested)|sunk cost|gone too far)\b", re.I),
    re.compile(r"\beveryone (knows|expects) (me|i)\b", re.I),
    # "put two years into" is as common as "spent"; the trailing s in "years"
    # previously broke the word-boundary match.
    re.compile(r"\b(already )?(spent|wasted|invested|put)\b.{0,24}(year|month|semester|time|money)s?\b", re.I),
    # Allow the determiner in "I told my WHOLE family"; add promise framings.
    re.compile(r"\bi told (everyone|my (whole |entire )?(parents|family|friends|relatives))\b", re.I),
    re.compile(r"\bi (promised|announced|committed to)\b", re.I),
    re.compile(r"\b(people|everyone|they|my parents) expect me\b", re.I),
    # Nepali
    re.compile(r"(भनिसकें|भनिसकेको|वाचा गरें)"),
    re.compile(r"(ढिला|ढिलो)\s*(भइसक्यो|भयो)"),
]

# Dunning-Kruger patterns: handled with profile context, but also text signals
_DK_OVERCONFIDENCE_PATTERNS = [
    re.compile(r"\b(expert|master|professional|guru) (in|at|of)\b", re.I),
    re.compile(r"\bi (know|understand|have mastered) .{0,20}(very well|completely|perfectly|thoroughly|inside out)\b", re.I),
    re.compile(r"\bno (problem|issue|challenge|difficulty) with\b", re.I),
    re.compile(r"\b(can easily|easily (do|handle|build|create))\b", re.I),
    # Students rarely use the textbook phrasings above. These cover how
    # over-confidence is actually voiced ("I already know everything about X").
    re.compile(r"\bi (already )?know (everything|it all|all of it|all there is)\b", re.I),
    re.compile(r"\bi('?m| am) (already )?(an?\s+)?(expert|pro|master)\b", re.I),
    re.compile(r"\bnothing (more |left )?to learn\b", re.I),
    re.compile(r"\bi don'?t (need|have) to (learn|study)\b", re.I),
    # Nepali over-confidence: "I know everything" / "I can do it all"
    re.compile(r"(सबै\s*थाहा\s*छ|मलाई\s*सब\s*आउँछ|सिक्नु\s*पर्दैन)"),
]
_DK_UNDERCONFIDENCE_PATTERNS = [
    re.compile(r"\b(terrible|awful|horrible|useless|hopeless) (at|in|with)\b", re.I),
    # Allow hedging adverbs ("probably/maybe/just") between the pronoun and the
    # negation - "I'm probably not smart enough" is the common real phrasing.
    re.compile(r"\bi('?m| am) (\w+\s+){0,2}(not|never) (good|smart|capable|talented|clever) enough\b", re.I),
    re.compile(r"\bnot (good|smart|capable) enough (for|to)\b", re.I),
    re.compile(r"\bi (can'?t|cannot|don'?t) (understand|learn|do) (any|this|that|anything)\b", re.I),
    re.compile(r"\bi('?m| am) (too) (stupid|dumb|slow)\b", re.I),
    re.compile(r"\bi('?m| am) (just |only )?(average|mediocre|ordinary|nothing special)\b", re.I),
    re.compile(r"\bi'?ll never be (good|able|able to)\b", re.I),
    re.compile(r"\bno one would hire me\b", re.I),
    # Nepali under-confidence: "I'm not good" / "I can't do it"
    re.compile(r"(म\s*राम्रो\s*छैन|मलाई\s*आउँदैन|सक्दिनँ|सक्दिन)"),
    re.compile(r"(अरू\s*सबै\s*भन्दा\s*कमजोर|मबाट\s*हुँदैन)"),
]

# ── Mitigation messages ────────────────────────────────────────────────────────

_MITIGATIONS: dict[str, str] = {
    "availability_heuristic": (
        "Response will include base-rate evidence from the broader job market "
        "rather than only the salient examples mentioned, to counteract "
        "over-weighting of vivid anecdotes."
    ),
    "anchoring": (
        "Response will present multiple career pathways and salary ranges "
        "across the Nepali market to counteract fixation on a single target."
    ),
    "confirmation": (
        "Response will include evidence for and against the student's stated "
        "position rather than simply validating it, to support genuine exploration."
    ),
    "dunning_kruger_over": (
        "Response will acknowledge skills while surfacing realistic market "
        "requirements and the gap between self-assessment and employer expectations."
    ),
    "dunning_kruger_under": (
        "Response will highlight the student's demonstrated competencies and "
        "match them to concrete local opportunities to counteract self-deprecation."
    ),
    "loss_aversion": (
        "Response will reframe choices as pursuing positive goals rather than "
        "avoiding negatives, and will surface concrete low-risk stepping stones."
    ),
    "consistency": (
        "Response will normalize the idea that changing direction is common "
        "and rational, and will surface comparable paths to reduce transition cost."
    ),
}


# ── Detector class ─────────────────────────────────────────────────────────────

class BiasDetector:
    """Rule-based cognitive bias detector for advising queries.

    Operates on (query_text, StudentProfile). Returns at most one BiasFlag per
    bias type (deduplication is built in). All detection is local and stateless.
    """

    def detect(
        self,
        query_text: str,
        profile: StudentProfile | None = None,
    ) -> list[BiasFlag]:
        """Detect cognitive biases in a student's query.

        Args:
            query_text: The raw query string from the student.
            profile: Optional session profile; used for Dunning-Kruger detection.

        Returns:
            List of BiasFlag objects (may be empty). At most one per bias type.
        """
        flags: list[BiasFlag] = []

        flags.extend(self._check_availability(query_text))
        flags.extend(self._check_anchoring(query_text))
        flags.extend(self._check_confirmation(query_text))
        flags.extend(self._check_loss_aversion(query_text))
        flags.extend(self._check_consistency(query_text))
        flags.extend(self._check_dunning_kruger(query_text, profile))

        return flags

    # ── Individual bias checks ─────────────────────────────────────────────────

    def _check_availability(self, text: str) -> list[BiasFlag]:
        signals = _first_matches(text, _AVAILABILITY_PATTERNS)
        if not signals:
            return []
        return [BiasFlag(
            bias_type="availability_heuristic",
            detected_signal=f"Query contains salient anecdotal reference: {signals[0]!r}",
            mitigation_applied=_MITIGATIONS["availability_heuristic"],
        )]

    def _check_anchoring(self, text: str) -> list[BiasFlag]:
        signals = _first_matches(text, _ANCHORING_PATTERNS)
        if not signals:
            return []
        return [BiasFlag(
            bias_type="anchoring",
            detected_signal=f"Query exhibits narrowing anchor: {signals[0]!r}",
            mitigation_applied=_MITIGATIONS["anchoring"],
        )]

    def _check_confirmation(self, text: str) -> list[BiasFlag]:
        signals = _first_matches(text, _CONFIRMATION_PATTERNS)
        if not signals:
            return []
        return [BiasFlag(
            bias_type="confirmation",
            detected_signal=f"Query seeks validation rather than exploration: {signals[0]!r}",
            mitigation_applied=_MITIGATIONS["confirmation"],
        )]

    def _check_loss_aversion(self, text: str) -> list[BiasFlag]:
        signals = _first_matches(text, _LOSS_AVERSION_PATTERNS)
        if not signals:
            return []
        return [BiasFlag(
            bias_type="loss_aversion",
            detected_signal=f"Query framed around avoiding negatives: {signals[0]!r}",
            mitigation_applied=_MITIGATIONS["loss_aversion"],
        )]

    def _check_consistency(self, text: str) -> list[BiasFlag]:
        signals = _first_matches(text, _CONSISTENCY_PATTERNS)
        if not signals:
            return []
        return [BiasFlag(
            bias_type="consistency",
            detected_signal=f"Query shows sunk-cost or prior-commitment framing: {signals[0]!r}",
            mitigation_applied=_MITIGATIONS["consistency"],
        )]

    def _check_dunning_kruger(
        self, text: str, profile: StudentProfile | None
    ) -> list[BiasFlag]:
        over_signals = _first_matches(text, _DK_OVERCONFIDENCE_PATTERNS)
        under_signals = _first_matches(text, _DK_UNDERCONFIDENCE_PATTERNS)

        # Also check profile: extreme self-ratings (all 5s or all 1s) with thin evidence
        profile_over = False
        profile_under = False
        if profile is not None:
            ratings = list(profile.self_assessed_skill_levels.values())
            if ratings:
                avg = sum(ratings) / len(ratings)
                # High self-ratings with very few completed modules suggests overconfidence
                if avg >= 4.5 and len(profile.completed_modules) <= 2:
                    profile_over = True
                # All low ratings with completed modules suggests underconfidence
                if avg <= 1.5 and len(profile.completed_modules) >= 4:
                    profile_under = True

        flags: list[BiasFlag] = []

        if over_signals or profile_over:
            signal = over_signals[0] if over_signals else "self-rated skill levels inconsistent with completed modules"
            flags.append(BiasFlag(
                bias_type="dunning_kruger",
                detected_signal=f"Possible overconfidence: {signal!r}",
                mitigation_applied=_MITIGATIONS["dunning_kruger_over"],
            ))
        elif under_signals or profile_under:
            signal = under_signals[0] if under_signals else "low self-ratings despite substantial completed modules"
            flags.append(BiasFlag(
                bias_type="dunning_kruger",
                detected_signal=f"Possible underconfidence: {signal!r}",
                mitigation_applied=_MITIGATIONS["dunning_kruger_under"],
            ))

        return flags


# ── Helpers ────────────────────────────────────────────────────────────────────

def _first_matches(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    """Return the text of the first match for each pattern that fires (deduped)."""
    seen: set[str] = set()
    results: list[str] = []
    for pat in patterns:
        m = pat.search(text)
        if m:
            match_text = m.group(0).strip()
            if match_text not in seen:
                seen.add(match_text)
                results.append(match_text)
    return results
