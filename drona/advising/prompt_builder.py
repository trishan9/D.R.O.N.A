"""
Prompt builder for D.R.O.N.A.'s advising engine.

Constructs the system + user prompt sent to the local LLM. Key design decisions:

  Anti-anchoring: Always asks for multiple pathways (default 3). Presenting
  only one option is itself an anchoring effect - the first answer shapes
  all subsequent thinking (Tversky & Kahneman 1974).

  Bias-aware instructions: If the bias detector fired, the system prompt
  includes explicit counter-instructions keyed to each detected bias type.
  These are short, precise, and placed before the retrieval context so they
  prime the model before it sees the evidence.

  Nepal-first ordering: Citations are presented in tier order (Nepal → Regional
  → International → Synthetic) so the model's attention falls on local evidence
  first (anti-anchoring: C4 contribution).

  Structured output: The system prompt instructs the model to respond as a
  JSON object matching AdvisingResponseRaw, which the LLM client then
  validates. This avoids free-form parsing and gives consistent fields.

  No hallucination loophole: The prompt explicitly forbids inventing salary
  numbers, employer names, or module details not in the retrieved citations.
"""

from __future__ import annotations

from drona.contracts import AdvisingQuery, BiasFlag, RetrievalCitation

# ── Bias-specific counter-instructions ────────────────────────────────────────

_BIAS_INSTRUCTIONS: dict[str, str] = {
    "availability_heuristic": (
        "The student may be over-weighting a specific example they have heard "
        "about recently. Ground your response in broad market statistics from "
        "the retrieved documents. Do not mirror the anecdote back - cite the "
        "base rate instead."
    ),
    "anchoring": (
        "The student appears anchored on a specific company, role, or salary. "
        "Present at least three distinct pathways including ones they have not "
        "mentioned. Do not start with their stated target - introduce it in the "
        "middle or end of the list so the first option they read is different."
    ),
    "confirmation": (
        "The student is seeking validation of a belief they already hold. Do "
        "not simply confirm it. Present balanced evidence - where the retrieved "
        "data supports their belief, say so; where it challenges it, say that "
        "too. Phrase this supportively, not confrontationally."
    ),
    "dunning_kruger": (
        "Be careful to neither reinforce overconfidence nor dismiss "
        "underconfidence. Cite specific retrieved evidence (employer skill "
        "requirements, module outcomes) to ground the skill assessment in "
        "observable facts rather than self-report."
    ),
    "loss_aversion": (
        "The student's query is framed around avoiding negatives. Reframe your "
        "response around pursuing positive goals. For each pathway, lead with "
        "what they gain, not what they avoid. Include one concrete 'next step' "
        "that is low-cost and low-risk to reduce the perceived barrier."
    ),
    "consistency": (
        "The student may be committed to a path due to prior declarations or "
        "sunk cost. Normalise the idea that changing direction mid-degree is "
        "common and rational. Present the pathway they mentioned alongside "
        "alternatives, without dismissing their stated direction."
    ),
}

# ── Citation formatter ────────────────────────────────────────────────────────

def _format_citations(citations: list[RetrievalCitation]) -> str:
    if not citations:
        return "(No retrieved documents - answer only from general knowledge and flag uncertainty.)"

    # Sort: Nepal → Regional → International → Synthetic
    tier_order = {"nepal": 0, "regional": 1, "international": 2, "synthetic": 3}
    sorted_cits = sorted(citations, key=lambda c: tier_order.get(c.tier.value, 99))

    lines: list[str] = []
    for i, cit in enumerate(sorted_cits, start=1):
        tier_label = f"[{cit.tier.value.upper()}]"
        lines.append(
            f"[{i}] {tier_label} {cit.source_type} | id:{cit.source_id}\n"
            f"    {cit.excerpt.strip()}"
        )
    return "\n\n".join(lines)


# ── Profile formatter ─────────────────────────────────────────────────────────

def _format_profile(query: AdvisingQuery) -> str:
    p = query.profile
    parts: list[str] = []
    programme_names = {
        "software_engineering": "BSc (Hons) Software Engineering (formerly Computing)",
        "ethical_hacking": "BSc (Hons) Ethical Hacking and Cybersecurity",
        "csai": "BSc (Hons) Computer Science with Artificial Intelligence",
    }
    prog = getattr(p, "programme", "software_engineering")
    parts.append(f"Enrolled programme: {programme_names.get(prog, prog)}")
    if p.year_of_study:
        parts.append(f"Year of study: {p.year_of_study}")
    if p.completed_modules:
        parts.append(f"Completed modules: {', '.join(p.completed_modules)}")
    if p.declared_skills:
        skill_lines = []
        for sk in p.declared_skills:
            level = p.self_assessed_skill_levels.get(sk)
            if level:
                skill_lines.append(f"{sk} (self-rated {level}/5)")
            else:
                skill_lines.append(sk)
        parts.append(f"Self-declared skills: {', '.join(skill_lines)}")
    if p.aspirations:
        parts.append(f"Stated aspirations: {'; '.join(p.aspirations)}")
    if p.aspiration_geography != "any":
        parts.append(f"Preferred geography: {p.aspiration_geography}")
    return "\n".join(parts) if parts else "(No profile information provided)"


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_BASE = """\
You are DRONA, an academic advising assistant at Softwarica College of IT and E-Commerce, \
Kathmandu, Nepal. You help BSc Computing students understand career pathways and how their \
coursework prepares them for the Nepali and international job markets.

CORE RULES:
1. Always present {max_pathways} career pathways unless fewer are genuinely supported by the evidence.
2. Lead with Nepal-market evidence. Use international data only to provide context.
3. Never invent salary figures, employer names, or module details not in the retrieved documents.
4. If retrieved documents do not cover the question, say so clearly - do not hallucinate.
5. Every factual claim must be traceable to a [N] citation number.
6. Keep the speak_text field short (2-4 sentences) - this is what the robot says aloud.

RESPONSE FORMAT:
Respond with a single JSON object using exactly these fields:
{{
  "summary": "<2-3 sentence top-line answer>",
  "pathways": [
    {{
      "pathway_title": "<title>",
      "rationale": "<why this fits the student>",
      "matched_softwarica_modules": ["<code>", ...],
      "local_market_evidence": "<what Nepali job postings or O*NET local data say>",
      "international_context": "<optional international comparison>",
      "next_concrete_steps": ["<step 1>", "<step 2>", ...],
      "citations": [<N>, ...],
      "confidence": "low|medium|high"
    }},
    ...
  ],
  "speak_text": "<2-4 sentences for robot speech>"
}}
Do not include any text outside the JSON object.
"""

_BIAS_PREAMBLE = "\nBIAS MITIGATION INSTRUCTIONS (apply these before constructing your response):\n"

_RETRIEVAL_SECTION = "\nRETRIEVED DOCUMENTS (cite by number [N]):\n{citations}\n"

_QUERY_SECTION = "\nSTUDENT PROFILE:\n{profile}\n\nSTUDENT QUESTION:\n{query_text}\n"


# ── Public API ────────────────────────────────────────────────────────────────

def build_prompt(
    query: AdvisingQuery,
    citations: list[RetrievalCitation],
    bias_flags: list[BiasFlag],
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the LLM.

    Args:
        query: The AdvisingQuery with student profile.
        citations: Top-N reranked citations (already in order).
        bias_flags: Detected biases from BiasDetector.

    Returns:
        (system_prompt, user_prompt) - both strings ready for the chat API.
    """
    system_parts = [_SYSTEM_BASE.format(max_pathways=query.max_pathways)]

    if bias_flags:
        system_parts.append(_BIAS_PREAMBLE)
        for flag in bias_flags:
            instruction = _BIAS_INSTRUCTIONS.get(flag.bias_type, "")
            if instruction:
                system_parts.append(f"- {flag.bias_type.upper()}: {instruction}")

    system_prompt = "\n".join(system_parts)

    user_parts = [
        _RETRIEVAL_SECTION.format(citations=_format_citations(citations)),
        _QUERY_SECTION.format(
            profile=_format_profile(query),
            query_text=query.query_text,
        ),
    ]
    user_prompt = "\n".join(user_parts)

    return system_prompt, user_prompt
