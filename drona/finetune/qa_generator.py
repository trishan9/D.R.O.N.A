"""
Synthetic advising Q&A generator for LoRA fine-tuning (Phase 3).

Produces ~500 (question → gold JSON answer) pairs grounded in REAL anchors
(career pathways, curriculum modules, job postings). The questions are templated
to span the six cognitive biases (C2) plus clean/no-bias cases, and the gold
answers follow the exact JSON contract the advising LLM must emit, with
bias-appropriate framing baked in (so the fine-tune teaches the bias-aware
style, not just the format).

Two modes:
  - RULE-BASED (default, deterministic, offline) — recombines anchor attributes
    into questions and gold answers. Fully reproducible (seeded).
  - LLM-AUGMENTED (optional, offline only) — paraphrase questions with the local
    Phi-3.5 or the Gemini API (offline eval/data creation use only).

Every pair is labelled is_synthetic=True with anchor_ids for provenance.
"""

from __future__ import annotations

import hashlib
import random

from loguru import logger

from drona.contracts import (
    CareerPathway,
    CurriculumModule,
    DataTier,
    JobPosting,
    RetrievalCitation,
    StudentProfile,
)
from drona.finetune.qa_schema import AdvisingQAPair

# Bias labels (None = clean). Mirrors contracts.BiasFlag.bias_type.
_BIASES: list[str | None] = [
    None,
    "availability_heuristic",
    "anchoring",
    "confirmation",
    "dunning_kruger",
    "loss_aversion",
    "consistency",
]

# Question templates keyed by bias. {field}/{employer}/{role}/{skill} filled from anchors.
_TEMPLATES: dict[str | None, list[str]] = {
    None: [
        "What career pathways suit a BSc Computing student interested in {field}?",
        "How does my coursework prepare me for a career in {field} in Nepal?",
        "I enjoy {field}. What are realistic options after graduation here?",
    ],
    "availability_heuristic": [
        "I heard {field} pays really well these days. Should I switch to it?",
        "My friend got a great job in {field}. Should I do the same?",
    ],
    "anchoring": [
        "I only want to work at {employer}, nowhere else. Is that realistic?",
        "I'm set on becoming a {role}. That's the only path I'll consider.",
    ],
    "confirmation": [
        "{skill} is the best skill to have, right? Just confirm it for me.",
        "Everyone says {field} is the only smart choice. That's true, isn't it?",
    ],
    "dunning_kruger": [
        "I know {skill} really well, can I get a senior {role} job already?",
        "I'm not sure I'm good enough for any {field} job. Am I hopeless?",
    ],
    "loss_aversion": [
        "I'm scared of being unemployed after graduation. What's the safest path?",
        "I don't want to waste my degree. Which {field} path has the least risk?",
    ],
    "consistency": [
        "I already told my parents I'd be a {role}. I can't change now, can I?",
        "I've spent two years aiming at {field}. It's too late to switch, right?",
    ],
}

# Short bias-aware framing notes embedded into the gold summary (teaches style).
_BIAS_FRAMING: dict[str | None, str] = {
    None: "Here are several evidence-based pathways to consider.",
    "availability_heuristic": (
        "Rather than going on a single anecdote, here is what the broader market "
        "evidence suggests across several pathways."
    ),
    "anchoring": (
        "It's worth looking beyond a single target. Here are several pathways, "
        "including some you may not have considered."
    ),
    "confirmation": (
        "Here is balanced evidence — both where it supports that view and where it "
        "complicates it — across multiple pathways."
    ),
    "dunning_kruger": (
        "Let's ground the skill picture in concrete employer requirements rather "
        "than self-assessment, across a few realistic pathways."
    ),
    "loss_aversion": (
        "Here are pathways framed around what you gain, each with a low-risk first "
        "step you can take soon."
    ),
    "consistency": (
        "Changing direction mid-degree is common and rational. Here is your stated "
        "direction alongside solid alternatives."
    ),
}


def _stable_id(seed: str) -> str:
    return "qa_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:14]


def _citation_from_pathway(pw: CareerPathway, score: float) -> RetrievalCitation:
    return RetrievalCitation(
        source_type="career_pathway",
        source_id=pw.pathway_id,
        tier=pw.tier,
        excerpt=f"{pw.title}: {pw.description[:200]}" if pw.description else pw.title,
        relevance_score=score,
    )


def _citation_from_posting(p: JobPosting, score: float) -> RetrievalCitation:
    skills = ", ".join(p.skills_required[:6])
    return RetrievalCitation(
        source_type="job_posting",
        source_id=p.posting_id,
        tier=p.tier,
        excerpt=f"{p.title} at {p.employer or 'a Nepali employer'} — skills: {skills}",
        relevance_score=score,
    )


def _citation_from_module(m: CurriculumModule, score: float) -> RetrievalCitation:
    return RetrievalCitation(
        source_type="curriculum",
        source_id=m.module_code,
        tier=DataTier.NEPAL,
        excerpt=f"{m.module_code} {m.title}: {m.description[:160]}",
        relevance_score=score,
    )


def _build_target(
    bias: str | None,
    chosen: list[CareerPathway],
    citations: list[RetrievalCitation],
    modules: list[CurriculumModule],
) -> dict:
    """Construct the gold JSON advising response for a set of chosen pathways."""
    module_codes = [m.module_code for m in modules[:3]]
    pathways_json = []
    # Citation indices are 1-based into the `citations` list (LLM-client convention).
    for i, pw in enumerate(chosen, start=1):
        local = next(
            (c.excerpt for c in citations if c.tier == DataTier.NEPAL and c.source_id != pw.pathway_id),
            None,
        )
        pathways_json.append(
            {
                "pathway_title": pw.title,
                "rationale": (
                    f"Your coursework and interests align with {pw.title}. "
                    + _BIAS_FRAMING[bias]
                ),
                "matched_softwarica_modules": module_codes,
                "local_market_evidence": local or "Local demand exists for this role in Kathmandu.",
                "international_context": (
                    "International salaries are higher but are not directly comparable to Nepal."
                    if pw.tier != DataTier.NEPAL
                    else None
                ),
                "next_concrete_steps": [
                    f"Build a small portfolio project related to {pw.title}.",
                    "Talk to a final-year student or alum working in this area.",
                ],
                "citations": [i],
                "confidence": "medium",
            }
        )

    titles = ", ".join(pw.title for pw in chosen)
    return {
        "summary": f"{_BIAS_FRAMING[bias]} Options: {titles}.",
        "pathways": pathways_json,
        "speak_text": (
            f"I found {len(chosen)} pathways that fit your interests. "
            f"The details are on the screen."
        ),
    }


def generate_qa_pairs(
    pathways: list[CareerPathway],
    modules: list[CurriculumModule] | None = None,
    postings: list[JobPosting] | None = None,
    target_count: int = 500,
    pathways_per_answer: int = 3,
    seed: int = 230352,
) -> list[AdvisingQAPair]:
    """Generate grounded synthetic advising Q&A pairs.

    Args:
        pathways: Real career pathways (the answer anchors). Required, non-empty.
        modules: Curriculum modules for module-matching evidence.
        postings: Job postings for local-market evidence.
        target_count: Approximate number of pairs to generate.
        pathways_per_answer: How many pathways each gold answer recommends.
        seed: RNG seed for reproducibility.

    Returns:
        List of AdvisingQAPair (length ~target_count).
    """
    if not pathways:
        raise ValueError("Need at least one real CareerPathway anchor to generate Q&A.")
    modules = modules or []
    postings = postings or []
    rng = random.Random(seed)

    # Field/role/skill vocabularies drawn from real anchors.
    fields = [pw.title for pw in pathways]
    roles = fields
    skills = sorted({s for pw in pathways for s in pw.typical_skills} | {"Python", "SQL"})
    employers = sorted({p.employer for p in postings if p.employer}) or ["a top Nepali tech company"]

    pairs: list[AdvisingQAPair] = []
    idx = 0
    while len(pairs) < target_count:
        bias = _BIASES[idx % len(_BIASES)]
        template = rng.choice(_TEMPLATES[bias])
        field = rng.choice(fields)
        role = rng.choice(roles)
        skill = rng.choice(skills)
        employer = rng.choice(employers)
        question = template.format(field=field, role=role, skill=skill, employer=employer)

        # Choose pathways for the gold answer; ensure the anchored/clean field is included.
        anchor_pw = next((pw for pw in pathways if pw.title == field), pathways[0])
        others = [pw for pw in pathways if pw.pathway_id != anchor_pw.pathway_id]
        rng.shuffle(others)
        chosen = [anchor_pw, *others[: max(0, pathways_per_answer - 1)]]
        # Anti-anchoring: when anchoring bias, don't put the anchored option first.
        if bias == "anchoring" and len(chosen) > 1:
            chosen = chosen[1:] + chosen[:1]

        citations: list[RetrievalCitation] = [
            _citation_from_pathway(pw, score=0.1 - 0.01 * i) for i, pw in enumerate(chosen)
        ]
        if postings:
            citations.append(_citation_from_posting(rng.choice(postings), score=0.05))
        if modules:
            citations.append(_citation_from_module(rng.choice(modules), score=0.04))

        target = _build_target(bias, chosen, citations, modules)
        anchor_ids = [pw.pathway_id for pw in chosen]

        pair = AdvisingQAPair(
            id=_stable_id(f"{idx}|{question}|{bias}"),
            question=question,
            profile=StudentProfile(
                session_id=f"synthetic-{idx}",
                year_of_study=rng.randint(1, 4),
                declared_interests=[field],
                declared_skills=rng.sample(skills, min(3, len(skills))),
                aspiration_geography=rng.choice(["nepal", "any", "international"]),
            ),
            bias_type=bias,
            context_citations=citations,
            target_response=target,
            anchor_ids=anchor_ids,
        )
        pairs.append(pair)
        idx += 1

    logger.success(
        f"Generated {len(pairs)} synthetic advising Q&A pairs "
        f"(biases balanced across {len(_BIASES)} classes)"
    )
    return pairs
