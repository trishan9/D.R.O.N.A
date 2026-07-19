"""
HELD-OUT bias-detection evaluation set.

WHY THIS EXISTS
---------------
The C2 bank in ``queries.py`` was used while developing the rule-based detector,
and its patterns were widened until those queries passed. Reporting a score on
that bank therefore measures fit to the development set, not generalisation - a
perfect macro-F1 there is a red flag, not a result. This module is the honest
counterpart: a set the detector was **not** tuned against.

PROVENANCE (state this in the dissertation - do not overclaim it)
----------------------------------------------------------------
These are **author-constructed** items, written to be representative rather than
harvested. Two things ground them:

  1. Subject matter and vocabulary come from what Nepali computing students
     publicly discuss - data science and analytics, cybersecurity, cloud/DevOps,
     remote work for foreign employers, freelancing, government vs private jobs,
     banks/fintech as local employers, and masters study abroad. Sources
     consulted while writing (July 2026): mitnepal.edu.np, kathford.edu.np,
     thebritishcollege.edu.np, techaxis.com.np, kumarijob.com, presidential.edu.np.
  2. The bias framings follow the standard operationalisations in the
     decision-making literature (Tversky & Kahneman 1974; sunk-cost and
     narrow-framing treatments summarised by clearerthinking.org and the NIH
     OITE careers blog).

They are NOT transcripts of real students and must not be described as such. If
you later collect genuine questions from Softwarica students, replace this file -
real items are strictly better evidence.

METHODOLOGICAL DISCIPLINE
-------------------------
The items were written from the student's voice and the literature, deliberately
WITHOUT consulting the detector's regexes, and the detector must NOT be modified
in response to the score this set produces. If it is, this set is burned and
becomes another development set. Report whatever number it gives.

Includes Nepali and code-switched items, since the deployed system is bilingual.
"""

from __future__ import annotations

from drona.evaluation.queries import EvalQuery

# ── Held-out items ────────────────────────────────────────────────────────────
# `expected_biases` is the author's label of the bias the phrasing exhibits.
# Neutral items carry an empty list and exist to catch false positives - a
# detector that flags a plain curriculum question is worse than one that misses.

HELDOUT_C2_QUERIES: list[EvalQuery] = [
    # ── availability heuristic: one salient case stands in for the base rate ──
    EvalQuery(
        query_id="ho-av-1",
        query_text=(
            "My senior got placed at Fusemachines right after his internship. "
            "Should I just follow exactly the same path he took?"
        ),
        expected_relevance="relevant",
        expected_biases=["availability_heuristic"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-av-2",
        query_text=(
            "I keep seeing news about AI replacing programmers. Is there any point "
            "studying software engineering now?"
        ),
        expected_relevance="relevant",
        expected_biases=["availability_heuristic"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-av-3",
        query_text=(
            "A YouTuber I watch said a bootcamp is better than a degree. He got a "
            "remote job in six months. Should I do that instead?"
        ),
        expected_relevance="relevant",
        expected_biases=["availability_heuristic"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-av-4",
        query_text="मेरो साथीले Deerwalk मा राम्रो job पायो, म पनि त्यही कम्पनीमा जान्छु। कसरी?",
        expected_relevance="relevant",
        expected_biases=["availability_heuristic"],
        category="heldout",
        notes="Nepali: 'my friend got a good job at Deerwalk, I'll go to that same company'",
    ),

    # ── anchoring: fixation on one number, employer, or destination ───────────
    EvalQuery(
        query_id="ho-an-1",
        query_text="I only want to work at Leapfrog Technology. How do I get in there?",
        expected_relevance="relevant",
        expected_biases=["anchoring"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-an-2",
        query_text=(
            "My target is a starting salary of NPR 150000 per month. Which field "
            "should I pick to hit that?"
        ),
        expected_relevance="relevant",
        expected_biases=["anchoring"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-an-3",
        query_text=(
            "I have decided on Australia for my masters and I am not considering "
            "anywhere else. What do I need?"
        ),
        expected_relevance="relevant",
        expected_biases=["anchoring"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-an-4",
        query_text="I want to focus only on cybersecurity, nothing else. Where do I start?",
        expected_relevance="relevant",
        expected_biases=["anchoring"],
        category="heldout",
    ),

    # ── confirmation: seeking agreement, not evidence ─────────────────────────
    EvalQuery(
        query_id="ho-cf-1",
        query_text="Cybersecurity is the best field in Nepal right now, isn't it correct?",
        expected_relevance="relevant",
        expected_biases=["confirmation"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-cf-2",
        query_text=(
            "Don't you agree that a government IT job is more secure than working "
            "at a private startup?"
        ),
        expected_relevance="relevant",
        expected_biases=["confirmation"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-cf-3",
        query_text=(
            "Everyone says remote work for foreign companies pays much better than "
            "local jobs. Just confirm that for me."
        ),
        expected_relevance="relevant",
        expected_biases=["confirmation", "availability_heuristic"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-cf-4",
        query_text="I already decided data analytics is right for me. Tell me I'm right.",
        expected_relevance="relevant",
        expected_biases=["confirmation", "consistency"],
        category="heldout",
    ),

    # ── loss aversion: framed around avoiding a loss ──────────────────────────
    EvalQuery(
        query_id="ho-la-1",
        query_text=(
            "I'm scared of wasting two years on a masters degree if it doesn't get "
            "me a better job afterwards."
        ),
        expected_relevance="relevant",
        expected_biases=["loss_aversion"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-la-2",
        query_text=(
            "I'm worried about switching from web development to machine learning "
            "and then failing at it."
        ),
        expected_relevance="relevant",
        expected_biases=["loss_aversion"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-la-3",
        query_text=(
            "If I leave my current internship to study for certifications, what if "
            "I end up with nothing?"
        ),
        expected_relevance="relevant",
        expected_biases=["loss_aversion"],
        category="heldout",
    ),

    # ── consistency / sunk cost: prior investment drives the choice ───────────
    EvalQuery(
        query_id="ho-co-1",
        query_text=(
            "I've already spent three years specialising in ethical hacking. It's "
            "too late for me to move into AI now, isn't it?"
        ),
        expected_relevance="relevant",
        expected_biases=["consistency", "confirmation"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-co-2",
        query_text=(
            "I told my whole family I would become a software engineer, so I can't "
            "really change direction at this point."
        ),
        expected_relevance="relevant",
        expected_biases=["consistency"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-co-3",
        query_text=(
            "I've invested a lot of money in networking certifications but I enjoy "
            "programming more. I've gone too far to switch though."
        ),
        expected_relevance="relevant",
        expected_biases=["consistency"],
        category="heldout",
    ),

    # ── Dunning-Kruger: mis-calibrated confidence in either direction ─────────
    EvalQuery(
        query_id="ho-dk-1",
        query_text=(
            "I've built a few websites so I already know everything about full "
            "stack development. Which senior roles should I apply for?"
        ),
        expected_relevance="relevant",
        expected_biases=["dunning_kruger"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-dk-2",
        query_text=(
            "I'm probably not smart enough for machine learning, I'm just an "
            "average student in my batch."
        ),
        expected_relevance="relevant",
        expected_biases=["dunning_kruger"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-dk-3",
        query_text=(
            "Honestly everyone in my class codes better than me, so I'll never be "
            "good enough for a developer job."
        ),
        expected_relevance="relevant",
        expected_biases=["dunning_kruger"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-dk-4",
        query_text=(
            "I finished a Python course so there is nothing more to learn before I "
            "start applying as a data scientist."
        ),
        expected_relevance="relevant",
        expected_biases=["dunning_kruger"],
        category="heldout",
    ),

    # ── multi-bias: realistic questions rarely carry exactly one ──────────────
    EvalQuery(
        query_id="ho-mx-1",
        query_text=(
            "My cousin earns Rs 200000 a month in Sydney. I only want to go abroad "
            "like him, nothing in Nepal interests me."
        ),
        expected_relevance="relevant",
        expected_biases=["availability_heuristic", "anchoring"],
        category="heldout",
    ),
    EvalQuery(
        query_id="ho-mx-2",
        query_text=(
            "I've already put two years into my current specialisation and I'm "
            "afraid of losing that if I change now. Should I just stay?"
        ),
        expected_relevance="relevant",
        expected_biases=["consistency", "loss_aversion"],
        category="heldout",
    ),

    # ── NEUTRAL CONTROLS: must NOT be flagged ────────────────────────────────
    EvalQuery(
        query_id="ho-n-1",
        query_text="Which modules in year three prepare me for backend development?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
    ),
    EvalQuery(
        query_id="ho-n-2",
        query_text="What is the difference between the CS with AI and Ethical Hacking programmes?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
    ),
    EvalQuery(
        query_id="ho-n-3",
        query_text="How many credits is the data science module worth?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
    ),
    EvalQuery(
        query_id="ho-n-4",
        query_text="Could you explain what DevOps work actually involves day to day?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
    ),
    EvalQuery(
        query_id="ho-n-5",
        query_text="What skills do banks and fintech companies in Kathmandu usually hire for?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
    ),
    EvalQuery(
        query_id="ho-n-6",
        query_text="मलाई cloud computing मा जान मन छ। कुन modules ले मद्दत गर्छ?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
        notes="Nepali code-switched, genuinely neutral - must not be flagged",
    ),
    EvalQuery(
        query_id="ho-n-7",
        query_text="I'm in second year and interested in both data and security. What should I try first?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
        notes="Explicitly open-minded - the opposite of anchoring",
    ),
    EvalQuery(
        query_id="ho-n-8",
        query_text="Are there internship opportunities in Nepal for students who know Python and SQL?",
        expected_relevance="relevant",
        expected_biases=[],
        category="heldout-neutral",
    ),
]
