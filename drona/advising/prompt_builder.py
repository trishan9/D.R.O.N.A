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
from drona.utils.settings import settings

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

def _format_citations(
    citations: list[RetrievalCitation], char_budget: int | None = None
) -> str:
    """Format the retrieved documents, trimmed to fit a character budget.

    char_budget bounds the total size of the retrieval block so the prompt stays
    inside the model's context window (Devanagari is token-dense, so the Nepali
    model gets a smaller budget - see settings). Highest-priority tiers are kept
    first; lower-priority citations are dropped once the budget is exhausted,
    rather than truncating mid-citation.
    """
    if not citations:
        return "(No retrieved documents - answer only from general knowledge and flag uncertainty.)"

    # Sort: Nepal → Regional → International → Synthetic
    tier_order = {"nepal": 0, "regional": 1, "international": 2, "synthetic": 3}
    sorted_cits = sorted(citations, key=lambda c: tier_order.get(c.tier.value, 99))

    lines: list[str] = []
    used = 0
    for i, cit in enumerate(sorted_cits, start=1):
        tier_label = f"[{cit.tier.value.upper()}]"
        block = (
            f"[{i}] {tier_label} {cit.source_type} | id:{cit.source_id}\n"
            f"    {cit.excerpt.strip()}"
        )
        if char_budget is not None and used + len(block) > char_budget and lines:
            # Budget exhausted - keep what fits, note the rest exists.
            lines.append(f"... (+{len(sorted_cits) - i + 1} more sources omitted to fit context)")
            break
        lines.append(block)
        used += len(block)
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
    goal_names = {
        "employment": "get a job (employment)",
        "postgrad_abroad": "postgraduate study abroad (Master's/PhD)",
        "startup": "found a startup / join an accelerator",
        "research": "a research / academia career",
        "freelance": "freelance / remote contracting",
        "undecided": "still exploring (undecided)",
    }
    goal = getattr(p, "goal", "employment")
    parts.append(f"Primary goal: {goal_names.get(goal, goal)}")
    targets = getattr(p, "target_institutions", None)
    if targets:
        parts.append(f"Target institutions/programmes: {', '.join(targets)}")
    tl = getattr(p, "timeline_years", None)
    if tl is not None:
        parts.append(f"Timeline: ~{tl} year(s)")
    if p.aspirations:
        parts.append(f"Stated aspirations: {'; '.join(p.aspirations)}")
    if p.aspiration_geography != "any":
        parts.append(f"Preferred geography: {p.aspiration_geography}")
    return "\n".join(parts) if parts else "(No profile information provided)"


# ── Goal-specific advising instructions ───────────────────────────────────────

_GOAL_INSTRUCTIONS: dict[str, str] = {
    "postgrad_abroad": (
        "The student is aiming for postgraduate study abroad. Tailor pathways to "
        "graduate admissions, not just jobs: name what programmes weigh (academic "
        "record, a research-grade project, statement of purpose, recommendation "
        "letters, IELTS/TOEFL - GRE is often optional), and be honest that many "
        "CS PhDs are funded via assistantships and scholarships exist for Master's. "
        "Give concrete near-term steps (shortlist by faculty fit, email professors, "
        "turn the Individual Project into a writing sample)."
    ),
    "startup": (
        "The student wants to found a company. Tailor advice to building, not "
        "employment: start from a validated real problem and a small working "
        "product (the Individual Project is ideal), find a co-founder, get real "
        "users, and treat accelerators (Y Combinator, local incubators) as coming "
        "AFTER early traction. Acknowledge the Nepal ecosystem as a real first step."
    ),
    "research": (
        "The student wants a research career. Emphasise depth, a supervised "
        "research-grade project, reading recent papers, and targeting FUNDED PhD "
        "programmes; a PhD should not be self-financed."
    ),
    "freelance": (
        "The student wants freelance/remote work. Emphasise a sharp niche, a "
        "visible portfolio, delivered projects, and building a track record and "
        "runway before going full-time; income is variable."
    ),
    "undecided": (
        "The student is undecided. Deliberately broaden the options and help them "
        "compare across directions (job, further study, founding) rather than "
        "narrowing early."
    ),
}


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_BASE = """\
You are DRONA, an academic advising assistant at Softwarica College of IT and E-Commerce, \
Kathmandu, Nepal. You help BSc Computing students understand career pathways and how their \
coursework prepares them for the Nepali and international job markets.

You advise on ALL directions a student may take: employment, postgraduate study abroad \
(e.g. MIT, Stanford), founding a startup (e.g. Y Combinator), a research career, or freelancing. \
Tailor every answer to the student's stated goal, and stay aware of how AI is reshaping roles.

CORE RULES:
1. Always present {max_pathways} pathways/options unless fewer are genuinely supported by the evidence.
2. Tailor to the student's PRIMARY GOAL. For non-employment goals, the fields still apply but shift \
meaning: local_market_evidence -> the concrete requirements/first steps for that goal; \
international_context -> target programmes, accelerators, funding, or global context. Set each \
pathway's goal_type to one of: employment, postgrad_abroad, startup, research, freelance.
3. Lead with Nepal-relevant, honest evidence. Use international data as context, not the default.
4. Never invent salary figures, employer names, admission stats, or module details not in the retrieved documents.
5. If retrieved documents do not cover the question, say so clearly - do not hallucinate.
6. Every factual claim must be traceable to a [N] citation number.
7. Keep the speak_text field short (2-4 sentences) - this is what the robot says aloud.

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
      "confidence": "low|medium|high",
      "goal_type": "employment|postgrad_abroad|startup|research|freelance"
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

# Language instruction appended to the system prompt for Nepali turns. The JSON
# STRUCTURE stays identical (keys in English so parsing is unchanged); only the
# human-readable VALUES - rationale, steps, speak_text, summary - are Nepali.
_LANGUAGE_INSTRUCTIONS = {
    "ne": (
        "\nLANGUAGE:\n"
        "Respond to the student in NEPALI (Devanagari script). Keep the JSON keys "
        "exactly as specified in English, but write all human-readable VALUES - "
        "pathway titles, rationale, next steps, summary, and speak_text - in "
        "natural, respectful Nepali. Use everyday Nepali; keep well-known technical "
        "terms and company/module names in English where that is how students say "
        "them. The spoken 'speak_text' must sound warm and natural, not translated.\n"
        "BE CONCISE. Devanagari is token-dense, so a verbose answer gets cut off "
        "mid-JSON and is unusable. Keep each 'rationale' to 1-2 short sentences, "
        "each step to one short line, and omit 'local_market_evidence' / "
        "'international_context' unless they add something specific. Finishing the "
        "JSON matters more than detail."
    ),
    "en": "",
}


def build_prompt(
    query: AdvisingQuery,
    citations: list[RetrievalCitation],
    bias_flags: list[BiasFlag],
    language: str = "en",
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the LLM.

    Args:
        query: The AdvisingQuery with student profile.
        citations: Top-N reranked citations (already in order).
        bias_flags: Detected biases from BiasDetector.
        language: "en" or "ne" - controls the response-language instruction and
            the retrieval context budget (Nepali is token-dense, so it gets a
            smaller character budget to stay inside the model's window).

    Returns:
        (system_prompt, user_prompt) - both strings ready for the chat API.
    """
    system_parts = [_SYSTEM_BASE.format(max_pathways=query.max_pathways)]

    goal = getattr(query.profile, "goal", "employment")
    goal_instruction = _GOAL_INSTRUCTIONS.get(goal)
    if goal_instruction:
        system_parts.append(f"\nGOAL-SPECIFIC GUIDANCE ({goal}):\n{goal_instruction}")

    if bias_flags:
        system_parts.append(_BIAS_PREAMBLE)
        for flag in bias_flags:
            instruction = _BIAS_INSTRUCTIONS.get(flag.bias_type, "")
            if instruction:
                system_parts.append(f"- {flag.bias_type.upper()}: {instruction}")

    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(language, "")
    if lang_instruction:
        system_parts.append(lang_instruction)

    system_prompt = "\n".join(system_parts)

    budget = (
        settings.nepali_context_char_budget if language == "ne"
        else settings.english_context_char_budget
    )
    user_parts = [
        _RETRIEVAL_SECTION.format(citations=_format_citations(citations, char_budget=budget)),
        _QUERY_SECTION.format(
            profile=_format_profile(query),
            query_text=query.query_text,
        ),
    ]
    user_prompt = "\n".join(user_parts)

    return system_prompt, user_prompt
