"""
Synthetic job-posting generator for D.R.O.N.A.

Why synthetic data exists: manual Nepali posting collection is small (~150–200),
so we augment the *career* index with synthetic postings to improve retrieval
robustness. Every synthetic record is:

  - flagged ``is_synthetic=True`` (and ``DataTier.SYNTHETIC``),
  - anchored to real postings via ``synthetic_anchor_ids`` (provenance),
  - NEVER silently mixed with real data (the retriever applies a tier penalty).

This honours the proposal's data-ethics stance and the build prompt's hard rule:
"Do not silently mix synthetic and real data."

Two modes:
  1. RULE-BASED (default, deterministic, offline, fully testable) - recombines
     attributes of real anchor postings with realistic Nepali employer/location
     pools and bounded salary jitter.
  2. LLM-AUGMENTED (optional) - paraphrases descriptions with the LOCAL Phi-3.5
     model (drona.advising.llm_client) or, for offline eval-set creation only,
     the Gemini API. Gemini is gated behind settings and never used in the live
     advising request path.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from loguru import logger

from drona.contracts import DataTier, JobPosting
from drona.data_pipeline.data_card import DataCard

# Real Nepali tech employers (public knowledge) used to diversify synthetic
# postings. These are anchors only; no posting is attributed falsely because
# synthetic records are explicitly labelled.
_NEPAL_EMPLOYERS = [
    "Leapfrog Technology", "Cotiviti Nepal", "Fusemachines", "Deerwalk",
    "F1Soft", "Verisk Nepal", "CloudFactory", "Khalti", "eSewa", "LIS Nepal",
    "Young Innovations", "Cedar Gate Nepal", "Logpoint", "Yarsa Labs",
]
_NEPAL_LOCATIONS = [
    "Kathmandu", "Lalitpur", "Bhaktapur", "Pokhara", "Kathmandu (Hybrid)",
    "Lalitpur (Remote-friendly)",
]


def _stable_id(seed: str) -> str:
    return "syn_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def generate_from_anchors(
    anchors: list[JobPosting],
    n_per_anchor: int = 2,
    seed: int = 230352,  # student ID - reproducible runs
) -> list[JobPosting]:
    """Deterministically generate synthetic postings from real anchors.

    Args:
        anchors: Real job postings to vary (non-synthetic only are used).
        n_per_anchor: How many synthetic variants to emit per anchor.
        seed: RNG seed for reproducibility.

    Returns:
        List of clearly-labelled synthetic JobPosting objects.
    """
    rng = random.Random(seed)
    real_anchors = [a for a in anchors if not a.is_synthetic]
    if not real_anchors:
        logger.warning("No real anchors provided - cannot generate synthetic postings")
        return []

    out: list[JobPosting] = []
    for anchor in real_anchors:
        for k in range(n_per_anchor):
            employer = rng.choice(_NEPAL_EMPLOYERS)
            location = rng.choice(_NEPAL_LOCATIONS)
            # Bounded salary jitter (±20%) around the anchor, if present.
            smin = anchor.salary_min_npr
            smax = anchor.salary_max_npr
            if smin:
                smin = int(smin * rng.uniform(0.8, 1.2))
            if smax:
                smax = int(max(smax * rng.uniform(0.8, 1.2), (smin or 0) + 5000))
            # Skill subset (keep ≥1) to vary the embedding signal.
            skills = anchor.skills_required[:]
            if len(skills) > 2:
                keep = rng.randint(2, len(skills))
                skills = rng.sample(skills, keep)

            seed_str = f"{anchor.posting_id}|{employer}|{location}|{k}"
            posting = JobPosting(
                posting_id=_stable_id(seed_str),
                source="synthetic_rule",
                tier=DataTier.SYNTHETIC,
                title=anchor.title,
                employer=employer,
                location=location,
                skills_required=skills,
                skills_preferred=anchor.skills_preferred[:],
                experience_years_min=anchor.experience_years_min,
                salary_min_npr=smin,
                salary_max_npr=smax,
                description=(
                    f"[SYNTHETIC] {anchor.title} role inspired by a real Nepali "
                    f"posting. Responsibilities resemble typical {anchor.title} work "
                    f"in the local market. Generated for retrieval robustness; "
                    f"not a real vacancy."
                ),
                is_synthetic=True,
                synthetic_anchor_ids=[anchor.posting_id],
            )
            out.append(posting)

    logger.success(
        f"Generated {len(out)} synthetic postings from {len(real_anchors)} anchors "
        f"(n_per_anchor={n_per_anchor})"
    )
    return out


def augment_description_with_llm(
    posting: JobPosting, use_gemini: bool = False
) -> JobPosting:
    """Optionally rewrite a synthetic posting's description with an LLM.

    By default uses the LOCAL Phi-3.5 client. Gemini is allowed ONLY for offline
    dataset creation and is hard-gated by settings.allow_gemini_in_request_path
    being irrelevant here (this is offline), but we still require an explicit
    opt-in flag and a configured key.
    """
    if not posting.is_synthetic:
        raise ValueError("Refusing to LLM-rewrite a non-synthetic posting")

    prompt = (
        "Rewrite this job description in 2-3 neutral sentences for the Nepali tech "
        f"market. Keep it generic and clearly hypothetical.\n\nRole: {posting.title}\n"
        f"Skills: {', '.join(posting.skills_required)}\n"
    )

    try:
        if use_gemini:
            new_desc = _gemini_complete(prompt)
        else:
            from drona.advising.llm_client import LLMClient

            new_desc = LLMClient().complete(prompt)  # type: ignore[attr-defined]
        new_desc = f"[SYNTHETIC] {new_desc.strip()}"
        return posting.model_copy(update={"description": new_desc})
    except Exception as e:
        logger.warning(f"LLM augmentation failed ({e}); keeping rule-based description")
        return posting


def _gemini_complete(prompt: str) -> str:
    """Offline-only Gemini completion for synthetic data / eval sets."""
    from drona.utils.settings import settings

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    import google.generativeai as genai  # type: ignore

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)
    return model.generate_content(prompt).text


def build_data_card(postings: list[JobPosting], output_path: Path) -> DataCard:
    """Create and write the synthetic-postings data card (YAML + Markdown)."""
    anchors = sorted({aid for p in postings for aid in p.synthetic_anchor_ids})
    card = DataCard(
        name="synthetic_job_postings",
        source_name="DRONA synthetic generator",
        source_url=None,
        license="N/A (generated)",
        tier="synthetic",
        collection_method="synthetic_rule",
        record_count=len(postings),
        fields=list(JobPosting.model_fields.keys()),
        description=(
            "Synthetic Nepali job postings generated by recombining attributes of "
            "real anchor postings. Every record is labelled is_synthetic=True and "
            "carries synthetic_anchor_ids. Used to improve career-index retrieval "
            "robustness; penalised at retrieval time so it never outranks real data."
        ),
        known_limitations=[
            "Not real vacancies - must never be presented as live jobs",
            "Diversity bounded by the anchor set and employer/location pools",
        ],
        contains_synthetic=True,
        synthetic_fraction=1.0,
        derived_from=[f"anchor:{a}" for a in anchors[:50]],
        output_files=[str(output_path)],
        notes="Rule-based mode is deterministic (seeded). LLM mode is offline-only.",
    )
    card.write(output_path.parent / "synthetic_job_postings_data_card.yaml")
    logger.info("Synthetic data card written")
    return card
