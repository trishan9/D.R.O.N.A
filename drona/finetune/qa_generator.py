"""
Synthetic advising Q&A generator for LoRA fine-tuning (Phase 3).

Produces grounded (question -> gold JSON answer) pairs anchored in REAL data
(career pathways, curriculum modules, job postings, and the curated aspiration
guides GUIDE-GRAD / GUIDE-STARTUP / GUIDE-AIROLES).

Two axes of coverage, generated in a balanced cross-product:

  GOAL TRACK - the student's post-graduation direction. The advisor must give
  track-appropriate guidance, not one-size-fits-all employment advice:
    employment      - get a job (Nepal-first)
    postgrad_abroad - Master's/PhD abroad (MIT, Stanford, ETH, ...)
    startup         - found a company / accelerator (Y Combinator, ...)
    research        - research / academia career
    freelance       - independent / remote contracting
    ai_era          - modern AI roles + "how is AI changing X?" (employment goal,
                      AI-focused; grounds on GUIDE-AIROLES)

  BIAS - the six cognitive biases (C2) plus clean/no-bias. Applied on top of the
  goal so the fine-tune learns e.g. "anchoring on MIT" or "loss aversion about
  startup risk", teaching bias-aware framing for every track.

Gold answers follow the exact JSON contract the advising LLM must emit, now with
an optional per-pathway ``goal_type`` label. Every pair is is_synthetic=True with
anchor_ids for provenance. Rule-based and fully reproducible (seeded).
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

# Goal tracks the generator balances across. "ai_era" is an employment-goal track
# focused on AI roles / AI's impact (grounded on GUIDE-AIROLES).
_GOALS: list[str] = [
    "employment", "postgrad_abroad", "startup", "research", "freelance", "ai_era",
]

# Maps a generator goal track to the StudentProfile.goal enum value.
_PROFILE_GOAL = {
    "employment": "employment",
    "ai_era": "employment",
    "postgrad_abroad": "postgrad_abroad",
    "startup": "startup",
    "research": "research",
    "freelance": "freelance",
}

# Natural interest phrases for the {field} question slot. Reads far better than
# raw O*NET titles ("a product in Penetration Testers") and multiplies question
# diversity; the gold answer still anchors on a matched REAL pathway.
_INTEREST_FIELDS = [
    "machine learning", "artificial intelligence", "data science", "data engineering",
    "web development", "mobile app development", "cybersecurity", "ethical hacking",
    "cloud computing", "DevOps", "software engineering", "game development",
    "computer networks", "database systems", "UI/UX design", "blockchain",
    "computer vision", "natural language processing", "robotics", "fintech",
]

# Keyword hints so a natural interest phrase maps to a plausible real pathway.
_FIELD_KEYWORDS = {
    "machine learning": ["research scientist", "data scient", "software"],
    "artificial intelligence": ["research scientist", "data scient", "software"],
    "data science": ["data scient", "statistic", "analyst"],
    "data engineering": ["database", "data", "systems"],
    "web development": ["web", "software", "developer"],
    "mobile app development": ["software", "developer", "applications"],
    "cybersecurity": ["security", "information security", "penetration"],
    "ethical hacking": ["penetration", "security"],
    "cloud computing": ["network", "systems", "architect"],
    "DevOps": ["systems", "network", "administrat"],
    "software engineering": ["software", "developer"],
    "game development": ["software", "developer", "designer"],
    "computer networks": ["network"],
    "database systems": ["database", "data"],
    "UI/UX design": ["designer", "web and digital", "interface"],
    "blockchain": ["blockchain", "software"],
    "computer vision": ["research scientist", "data scient"],
    "natural language processing": ["research scientist", "data scient"],
    "robotics": ["research scientist", "engineer", "software"],
    "fintech": ["software", "analyst", "database"],
}

# Concrete target institutions per goal (grounds the {inst} slot honestly).
_INSTITUTIONS = {
    "postgrad_abroad": [
        "MIT", "Stanford", "Carnegie Mellon", "ETH Zurich",
        "the University of Melbourne", "a strong UK university", "TU Munich",
    ],
    "research": [
        "MIT", "Carnegie Mellon", "EPFL", "the University of Edinburgh",
        "a well-funded PhD programme",
    ],
    "startup": [
        "Y Combinator", "Techstars", "a Kathmandu incubator",
        "a local accelerator",
    ],
    "freelance": ["Upwork", "Toptal", "a global remote team", "international clients"],
}

# ── Question templates ────────────────────────────────────────────────────────
# Keyed by (goal, bias). {field}/{employer}/{role}/{skill}/{inst} filled from anchors.
# Only bias-relevant variants are provided per goal; the clean (None) set is the
# fallback used whenever a goal lacks a template for the current bias.

_TEMPLATES: dict[str, dict[str | None, list[str]]] = {
    "employment": {
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
    },
    "postgrad_abroad": {
        None: [
            "I want to do a Master's abroad in {field}. How do I get there from Softwarica?",
            "How do I prepare for graduate study at {inst} after my BSc?",
            "What should I do in my degree to get into a good MS programme abroad for {field}?",
        ],
        "anchoring": [
            "I will only go to {inst}, nothing else counts. Is that realistic?",
            "It's {inst} or nothing for my Master's. How do I get in?",
        ],
        "loss_aversion": [
            "Studying abroad feels too expensive and risky. Is a Master's even worth it?",
            "I'm afraid I'll waste money on a Master's abroad and it won't pay off.",
        ],
        "confirmation": [
            "A degree from Nepal can't get me into {inst}, right? Just confirm it.",
        ],
        "dunning_kruger": [
            "My marks are okay, so I can definitely get into {inst}, can't I?",
            "I don't think I'm smart enough for {inst}. Should I not even try?",
        ],
    },
    "startup": {
        None: [
            "I want to build my own startup in {field} after graduation. Where do I begin?",
            "How can my degree help me found a {field} company in Nepal?",
            "I have an idea for a {field} product. What are my first real steps?",
            "Is founding a {field} startup realistic for a student like me?",
        ],
        "availability_heuristic": [
            "I saw a founder raise millions. Should I drop everything and start a startup?",
        ],
        "anchoring": [
            "I only want to get into {inst}. That's the only way to succeed, right?",
            "My plan is {inst} or bust. How do I get my startup in?",
        ],
        "loss_aversion": [
            "Starting a company feels too risky. Should I just take a safe job instead?",
            "I'm scared my startup will fail and I'll have nothing. Is it worth it?",
        ],
        "consistency": [
            "I already told everyone I'm going to be a founder. I can't back out now, right?",
        ],
    },
    "research": {
        None: [
            "I want a research career in {field}. What path leads there from here?",
            "How do I move toward a PhD and research work in {field}?",
            "Is research in {field} a realistic goal for a Softwarica student?",
        ],
        "loss_aversion": [
            "A PhD takes years with low pay. Is a research path too risky for me?",
        ],
        "dunning_kruger": [
            "I read a few papers on {field}, am I ready for a PhD already?",
        ],
    },
    "freelance": {
        None: [
            "I want to freelance and work with international clients in {field}. How?",
            "Can I build a remote freelance career in {field} from Nepal?",
            "What do I need to start freelancing in {field} while I study?",
        ],
        "availability_heuristic": [
            "I heard freelancers earn way more than employees. Should I just freelance?",
        ],
        "loss_aversion": [
            "Freelancing has no steady salary. Is it too unstable to rely on?",
        ],
    },
    "ai_era": {
        None: [
            "Should I become an AI or machine-learning engineer? Is it a good path for me?",
            "How is AI changing careers in {field}, and what should I learn?",
            "What modern AI-era roles fit a BSc Computing student, and how do I prepare?",
            "I'm interested in {field}. How is AI reshaping that, and what should I focus on?",
            "Which AI-era skills matter most if I want to work in {field}?",
        ],
        "availability_heuristic": [
            "Everyone says do AI now. Should I drop {field} and only focus on AI?",
        ],
        "loss_aversion": [
            "Will AI replace developers and make my degree worthless?",
            "I'm scared AI will take all the jobs in {field}. Is there any point?",
        ],
        "dunning_kruger": [
            "I use AI tools every day, so I'm basically an AI engineer already, right?",
        ],
        "confirmation": [
            "AI is the only field worth going into now, isn't it? Just confirm it.",
        ],
    },
}

# Short bias-aware framing notes embedded into the gold summary (teaches style).
_BIAS_FRAMING: dict[str | None, str] = {
    None: "Here are several evidence-based options to consider.",
    "availability_heuristic": (
        "Rather than going on a single anecdote, here is what the broader evidence "
        "suggests across several options."
    ),
    "anchoring": (
        "It's worth looking beyond a single target. Here are several options, "
        "including some you may not have considered."
    ),
    "confirmation": (
        "Here is balanced evidence - both where it supports that view and where it "
        "complicates it."
    ),
    "dunning_kruger": (
        "Let's ground this in concrete requirements rather than self-assessment."
    ),
    "loss_aversion": (
        "Here are options framed around what you gain, each with a low-risk first step."
    ),
    "consistency": (
        "Changing direction is common and rational. Here is your stated direction "
        "alongside solid alternatives."
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
        excerpt=f"{p.title} at {p.employer or 'a Nepali employer'} - skills: {skills}",
        relevance_score=score,
    )


def _citation_from_module(m: CurriculumModule, score: float) -> RetrievalCitation:
    body = m.description or m.content or ""
    return RetrievalCitation(
        source_type="curriculum",
        source_id=m.module_code,
        tier=DataTier.NEPAL,
        excerpt=f"{m.module_code} {m.title}: {body[:160]}",
        relevance_score=score,
    )


# ── Per-goal gold pathway builders ────────────────────────────────────────────
# Each returns the pathway dict for the gold answer. `cite` is the 1-based index
# list this pathway is allowed to cite (its own pathway citation + the goal guide
# citation when present).

def _pathway_employment(pw, bias, module_codes, cite, local_evidence):
    return {
        "pathway_title": pw.title,
        "rationale": (f"Your coursework and interests align with {pw.title}. "
                      + _BIAS_FRAMING[bias]),
        "matched_softwarica_modules": module_codes,
        "local_market_evidence": local_evidence
        or "Local demand exists for this role in Kathmandu.",
        "international_context": (
            "International salaries are higher but are not directly comparable to Nepal."
            if pw.tier != DataTier.NEPAL else None),
        "next_concrete_steps": [
            f"Build a small portfolio project related to {pw.title}.",
            "Talk to a final-year student or alum working in this area.",
        ],
        "citations": cite,
        "confidence": "medium",
        "goal_type": "employment",
    }


def _pathway_postgrad(pw, bias, module_codes, cite, inst):
    return {
        "pathway_title": f"Postgraduate study abroad ({inst}) toward {pw.title}",
        "rationale": (
            f"A Master's or PhD abroad is a strong route into {pw.title}. Your "
            f"final-year Individual Project and quantitative modules build the "
            f"research profile admissions committees look for. {_BIAS_FRAMING[bias]}"),
        "matched_softwarica_modules": module_codes,
        "local_market_evidence": (
            "From Nepal this is well-trodden: a strong academic record, a focused "
            "statement of purpose naming specific faculty, 2-3 recommendation letters, "
            "and IELTS/TOEFL are the core requirements; the GRE is optional at many "
            "CS programmes now."),
        "international_context": (
            f"Programmes like {inst} fund most CS PhD students through research or "
            "teaching assistantships, so cost is not the automatic blocker it seems; "
            "scholarships (Fulbright, Chevening, DAAD, Erasmus Mundus) exist for Master's."),
        "next_concrete_steps": [
            "Shortlist 6-8 programmes by matching faculty research to your interest.",
            "Turn your Individual Project into a writing sample or short paper.",
            "Email 3-5 professors with a specific, informed question about their work.",
            "Sit IELTS/TOEFL early and draft your statement of purpose this semester.",
        ],
        "citations": cite,
        "confidence": "medium",
        "goal_type": "postgrad_abroad",
    }


def _pathway_startup(pw, bias, module_codes, cite, inst):
    return {
        "pathway_title": f"Founding a startup ({pw.title} space)",
        "rationale": (
            f"Building your own company in the {pw.title} space is realistic if you "
            f"start from a real problem and a small working product rather than an "
            f"idea alone. {_BIAS_FRAMING[bias]}"),
        "matched_softwarica_modules": module_codes,
        "local_market_evidence": (
            "The Nepal path is real: local incubators, hackathons, and university "
            "networks are where most founders start, and revenue from real Nepali "
            "users is more fundable than a slide deck. Your Individual Project is an "
            "ideal vehicle for a first MVP."),
        "international_context": (
            f"Global accelerators like {inst} fund small teams that already have a "
            "working product and some usage - traction first, then apply."),
        "next_concrete_steps": [
            "Interview 10 potential users this week; write down what they do today.",
            "Turn a course or Individual Project into a usable MVP with 5-10 real users.",
            "Find a co-founder with complementary skills.",
            "Bootstrap to traction locally before applying to a global accelerator.",
        ],
        "citations": cite,
        "confidence": "medium",
        "goal_type": "startup",
    }


def _pathway_research(pw, bias, module_codes, cite, inst):
    return {
        "pathway_title": f"Research career in {pw.title}",
        "rationale": (
            f"A research path in {pw.title} typically runs through a funded PhD. It "
            f"rewards depth, reading, and a supervised project more than certificates. "
            f"{_BIAS_FRAMING[bias]}"),
        "matched_softwarica_modules": module_codes,
        "local_market_evidence": (
            "Start now: join or form a reading group, do a research-grade Individual "
            "Project under a supervisor, and aim for a workshop paper or preprint."),
        "international_context": (
            f"Reputable PhD offers (e.g. at {inst}) are funded with a stipend through "
            "research/teaching assistantships - a PhD should not be self-financed."),
        "next_concrete_steps": [
            "Pick a narrow topic and read 10 recent papers on it.",
            "Ask a lecturer to supervise a small research project.",
            "Email professors whose work matches yours with a specific question.",
            "Sit IELTS/TOEFL and target funded programmes.",
        ],
        "citations": cite,
        "confidence": "medium",
        "goal_type": "research",
    }


def _pathway_freelance(pw, bias, module_codes, cite, inst):
    return {
        "pathway_title": f"Freelance / remote work in {pw.title}",
        "rationale": (
            f"A remote freelance career in {pw.title} is achievable from Nepal, but it "
            f"rewards a sharp niche, a visible portfolio, and reliability more than a "
            f"broad skill list. {_BIAS_FRAMING[bias]}"),
        "matched_softwarica_modules": module_codes,
        "local_market_evidence": (
            "Many Nepali developers already earn in foreign currency through remote "
            "contracts; a strong public portfolio and a few delivered projects open "
            "the door more than a CV."),
        "international_context": (
            f"Platforms like {inst} reward specialisation and consistent delivery; "
            "income is variable, so build a runway before going full-time."),
        "next_concrete_steps": [
            "Pick one niche and build two portfolio projects that prove it.",
            "Take a few small contracts while studying to build a track record.",
            "Set up a clean profile and ask early clients for reviews.",
        ],
        "citations": cite,
        "confidence": "medium",
        "goal_type": "freelance",
    }


def _pathway_ai_era(pw, bias, module_codes, cite):
    return {
        "pathway_title": f"AI-era role: {pw.title}",
        "rationale": (
            f"AI is mostly augmenting roles like {pw.title}, not deleting them: it "
            f"raises the baseline and shifts value toward judgement, system design, and "
            f"understanding the problem. Build fundamentals first, then applied AI. "
            f"{_BIAS_FRAMING[bias]}"),
        "matched_softwarica_modules": module_codes,
        "local_market_evidence": (
            "Data and ML-adjacent roles are among the most-hired in Nepal's own market; "
            "'can use AI tools well' is becoming a baseline skill, not a specialisation."),
        "international_context": (
            "New roles (ML engineer, LLM/GenAI application engineer, MLOps, AI product, "
            "AI safety) have grown globally, but all sit on the same fundamentals."),
        "next_concrete_steps": [
            "Get solid at data structures, algorithms, and one language first.",
            "Ship one real end-to-end project that uses ML or an LLM.",
            "Learn to specify, verify, and integrate AI output - not just prompt it.",
        ],
        "citations": cite,
        "confidence": "medium",
        "goal_type": "employment",
    }


_GOAL_BUILDERS = {
    "postgrad_abroad": _pathway_postgrad,
    "startup": _pathway_startup,
    "research": _pathway_research,
    "freelance": _pathway_freelance,
}


def _speak_text(goal: str, n: int) -> str:
    verb = {
        "postgrad_abroad": "graduate-study routes",
        "startup": "founder routes",
        "research": "research routes",
        "freelance": "freelance routes",
        "ai_era": "AI-era options",
        "employment": "pathways",
    }[goal]
    return (f"I found {n} {verb} that fit your goal. The details are on the screen.")


def _select_modules(pw, modules, rng, k: int = 3) -> list[str]:
    """Pick up to k REAL teaching modules whose skills relate to the pathway.

    Skips institutional/aspiration guide docs (INFO-*, GUIDE-*) so matched
    modules are actual coursework, and prefers modules whose skills_developed
    overlap the pathway's typical_skills.
    """
    teaching = [m for m in modules
                if not m.module_code.startswith(("GUIDE-", "INFO-"))]
    if not teaching:
        teaching = list(modules)
    if not teaching:
        return []
    pw_skills = {s.lower() for s in pw.typical_skills}
    relevant = [m for m in teaching
                if pw_skills & {s.lower() for s in m.skills_developed}]
    pool = relevant if len(relevant) >= k else relevant + [
        m for m in teaching if m not in relevant]
    picks = pool[:k] if relevant else rng.sample(teaching, min(k, len(teaching)))
    return [m.module_code for m in picks[:k]]


def _build_target(goal, bias, chosen, citations, module_codes, inst, guide_idx):
    """Construct the gold JSON advising response for a set of chosen pathways."""
    local_evidence = next(
        (c.excerpt for c in citations if c.tier == DataTier.NEPAL), None)
    pathways_json = []
    for i, pw in enumerate(chosen, start=1):
        cite = [i] + ([guide_idx] if guide_idx else [])
        if goal in _GOAL_BUILDERS:
            pw_json = _GOAL_BUILDERS[goal](pw, bias, module_codes, cite, inst)
        elif goal == "ai_era":
            pw_json = _pathway_ai_era(pw, bias, module_codes, cite)
        else:
            pw_json = _pathway_employment(pw, bias, module_codes, cite, local_evidence)
        pathways_json.append(pw_json)

    titles = ", ".join(pw.title for pw in chosen)
    return {
        "summary": f"{_BIAS_FRAMING[bias]} Options: {titles}.",
        "pathways": pathways_json,
        "speak_text": _speak_text(goal, len(chosen)),
    }


def _pick_template(goal: str, bias: str | None, rng: random.Random) -> str:
    goal_templates = _TEMPLATES[goal]
    variants = goal_templates.get(bias) or goal_templates[None]
    return rng.choice(variants)


def generate_qa_pairs(
    pathways: list[CareerPathway],
    modules: list[CurriculumModule] | None = None,
    postings: list[JobPosting] | None = None,
    target_count: int = 500,
    pathways_per_answer: int = 3,
    seed: int = 230352,
) -> list[AdvisingQAPair]:
    """Generate grounded synthetic advising Q&A pairs across goals x biases.

    Args:
        pathways: Real career pathways (the answer anchors). Required, non-empty.
        modules: Curriculum modules (incl. GUIDE-* aspiration guides) for evidence.
        postings: Job postings for local-market evidence.
        target_count: Approximate number of pairs to generate.
        pathways_per_answer: How many pathways each gold answer recommends.
        seed: RNG seed for reproducibility.

    Returns:
        List of AdvisingQAPair (length ~target_count), balanced across the six
        goal tracks and the seven bias classes.
    """
    if not pathways:
        raise ValueError("Need at least one real CareerPathway anchor to generate Q&A.")
    modules = modules or []
    postings = postings or []
    rng = random.Random(seed)

    # Role/skill vocabularies drawn from real anchors; question topics come from
    # the curated natural-interest list (readability + diversity).
    roles = [pw.title for pw in pathways]
    skills = sorted({s for pw in pathways for s in pw.typical_skills} | {"Python", "SQL"})
    employers = sorted({p.employer for p in postings if p.employer}) or [
        "a top Nepali tech company"]

    def _anchor_for(field_phrase: str) -> CareerPathway:
        """Pick a real pathway whose title/skills plausibly match the interest."""
        hints = _FIELD_KEYWORDS.get(field_phrase, [field_phrase])
        matches = [pw for pw in pathways
                   if any(h in (pw.title + " " + " ".join(pw.typical_skills)).lower()
                          for h in hints)]
        return rng.choice(matches) if matches else rng.choice(pathways)

    # Aspiration guide modules -> reusable citation anchors per goal.
    by_code = {m.module_code: m for m in modules}
    guide_for_goal = {
        "postgrad_abroad": by_code.get("GUIDE-GRAD"),
        "research": by_code.get("GUIDE-GRAD"),
        "startup": by_code.get("GUIDE-STARTUP"),
        "ai_era": by_code.get("GUIDE-AIROLES"),
    }

    pairs: list[AdvisingQAPair] = []
    idx = 0
    while len(pairs) < target_count:
        # Cross-product cycling so both axes stay balanced.
        goal = _GOALS[idx % len(_GOALS)]
        bias = _BIASES[(idx // len(_GOALS)) % len(_BIASES)]

        field = rng.choice(_INTEREST_FIELDS)
        role = rng.choice(roles)
        skill = rng.choice(skills)
        employer = rng.choice(employers)
        inst_pool = _INSTITUTIONS.get(goal, ["a strong programme"])
        inst = rng.choice(inst_pool)
        template = _pick_template(goal, bias, rng)
        question = template.format(
            field=field, role=role, skill=skill, employer=employer, inst=inst)

        # Choose pathways for the gold answer; anchor on a pathway matching the interest.
        anchor_pw = _anchor_for(field)
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
        # Prefer a topical module; fall back to any module.
        topical = [m for m in modules if not m.module_code.startswith("GUIDE-")]
        if topical:
            citations.append(_citation_from_module(rng.choice(topical), score=0.04))

        # Attach the goal's aspiration guide as a citable anchor (1-based index).
        guide = guide_for_goal.get(goal)
        guide_idx = None
        if guide is not None:
            citations.append(_citation_from_module(guide, score=0.06))
            guide_idx = len(citations)

        module_codes = _select_modules(anchor_pw, topical or modules, rng)
        target = _build_target(goal, bias, chosen, citations, module_codes,
                               inst, guide_idx)
        anchor_ids = [pw.pathway_id for pw in chosen]
        if guide is not None:
            anchor_ids.append(guide.module_code)

        pair = AdvisingQAPair(
            id=_stable_id(f"{idx}|{question}|{goal}|{bias}"),
            question=question,
            profile=StudentProfile(
                session_id=f"synthetic-{idx}",
                year_of_study=rng.randint(1, 4),
                declared_interests=[field],
                declared_skills=rng.sample(skills, min(3, len(skills))),
                aspiration_geography=rng.choice(["nepal", "any", "international"]),
                goal=_PROFILE_GOAL[goal],
                target_institutions=([inst] if goal in _INSTITUTIONS else []),
                timeline_years=rng.choice([None, 1, 2, 3]),
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
        f"(balanced across {len(_GOALS)} goal tracks x {len(_BIASES)} bias classes)"
    )
    return pairs
