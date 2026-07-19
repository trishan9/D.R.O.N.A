"""
HELD-OUT bias set **v2** - the current generalisation set.

WHY v2 EXISTS
-------------
Set v1 (``heldout_queries.py``) did its job: it exposed three real gaps -
media/authority anecdotes, narrow commitment phrasing, and English-only
detection. The detector was then extended to close them. That extension BURNS
v1: a set you tune against measures fit, not generalisation, so v1's score is
from here on reported as a *development* number.

v2 is the replacement. It was written after that work using deliberately
different phrasings and topics (scholarships and IELTS, hostel/batchmate
anecdotes, LinkedIn posts, portfolio sunk cost, production-system self-doubt),
and carries a larger Nepali share specifically to test whether the new Devanagari
patterns GENERALISE or merely memorised the v1 items.

PROVENANCE: same as v1 - author-constructed, representative, grounded in what
Nepali computing students publicly discuss and in the standard bias
operationalisations. These are NOT transcripts of real students; do not describe
them as scraped data. Real collected questions would be strictly better evidence.

DISCIPLINE: do not tune the detector against v2. If that happens, write v3 and
report that instead. Report whatever number this produces.
"""

from __future__ import annotations

from drona.evaluation.queries import EvalQuery

HELDOUT_C2_QUERIES_V2: list[EvalQuery] = [
    # ── availability heuristic: one vivid case generalised to a rule ─────────
    EvalQuery(
        query_id="h2-av-1", expected_relevance="relevant", category="heldout2",
        query_text=("My batchmate cleared IELTS and got a scholarship to Germany in "
                    "three months. Can I just do exactly that?"),
        expected_biases=["availability_heuristic"],
    ),
    EvalQuery(
        query_id="h2-av-2", expected_relevance="relevant", category="heldout2",
        query_text=("I saw a LinkedIn post claiming DevOps is the highest paying "
                    "field. Should I switch to it?"),
        expected_biases=["availability_heuristic"],
    ),
    EvalQuery(
        query_id="h2-av-3", expected_relevance="relevant", category="heldout2",
        query_text="दाइले भन्नुभयो cybersecurity मा राम्रो scope छ रे। म पनि त्यतै जाऊँ?",
        expected_biases=["availability_heuristic"],
        notes="Nepali: my elder brother said cybersecurity has good scope",
    ),

    # ── anchoring: one employer, one number, one place ───────────────────────
    EvalQuery(
        query_id="h2-an-1", expected_relevance="relevant", category="heldout2",
        query_text="Google or nothing for me. What is the roadmap to get there?",
        expected_biases=["anchoring"],
    ),
    EvalQuery(
        query_id="h2-an-2", expected_relevance="relevant", category="heldout2",
        query_text=("I want at least Rs 200000 per month. Which specialisation "
                    "reaches that fastest?"),
        expected_biases=["anchoring"],
    ),
    EvalQuery(
        query_id="h2-an-3", expected_relevance="relevant", category="heldout2",
        query_text="मलाई खाली Kathmandu मै काम गर्न मन छ, अरू ठाउँ सोच्दिनँ।",
        expected_biases=["anchoring"],
        notes="Nepali: I only want to work in Kathmandu",
    ),

    # ── confirmation: inviting agreement rather than evidence ────────────────
    EvalQuery(
        query_id="h2-cf-1", expected_relevance="relevant", category="heldout2",
        query_text="AI is obviously the safest bet for the next decade, right?",
        expected_biases=["confirmation"],
    ),
    EvalQuery(
        query_id="h2-cf-2", expected_relevance="relevant", category="heldout2",
        query_text=("Most seniors told me an MBA is useless for IT people. "
                    "Wouldn't you agree?"),
        expected_biases=["confirmation", "availability_heuristic"],
    ),
    EvalQuery(
        query_id="h2-cf-3", expected_relevance="relevant", category="heldout2",
        query_text="Data science नै सबैभन्दा राम्रो हो, होइन र?",
        expected_biases=["confirmation"],
        notes="Nepali: data science is the best, isn't it?",
    ),

    # ── loss aversion: framed around what could be lost ──────────────────────
    EvalQuery(
        query_id="h2-la-1", expected_relevance="relevant", category="heldout2",
        query_text=("I might lose my scholarship if I change my major, so it is "
                    "not worth the risk."),
        expected_biases=["loss_aversion"],
    ),
    EvalQuery(
        query_id="h2-la-2", expected_relevance="relevant", category="heldout2",
        query_text=("Everyone warns freelancing is unstable and I do not want to "
                    "regret leaving a salaried job."),
        expected_biases=["loss_aversion", "availability_heuristic"],
    ),
    EvalQuery(
        query_id="h2-la-3", expected_relevance="relevant", category="heldout2",
        query_text="अहिलेको job छोड्न डर लाग्छ, के गर्ने?",
        expected_biases=["loss_aversion"],
        notes="Nepali: I'm scared to leave my current job",
    ),

    # ── consistency / sunk cost ──────────────────────────────────────────────
    EvalQuery(
        query_id="h2-co-1", expected_relevance="relevant", category="heldout2",
        query_text=("I have been telling recruiters I am a Java developer for two "
                    "years, switching now feels dishonest."),
        expected_biases=["consistency"],
    ),
    EvalQuery(
        query_id="h2-co-2", expected_relevance="relevant", category="heldout2",
        query_text=("My entire portfolio is web projects. Starting over in machine "
                    "learning seems wasteful."),
        expected_biases=["consistency"],
    ),
    EvalQuery(
        query_id="h2-co-3", expected_relevance="relevant", category="heldout2",
        query_text="मैले तीन वर्ष लगानी गरिसकें, अब बाटो फेर्न ढिलो भयो।",
        expected_biases=["consistency"],
        notes="Nepali: I've already invested three years, too late to change",
    ),

    # ── Dunning-Kruger, both directions ──────────────────────────────────────
    EvalQuery(
        query_id="h2-dk-1", expected_relevance="relevant", category="heldout2",
        query_text=("I topped my class in DBMS so database administration should be "
                    "no problem with for me."),
        expected_biases=["dunning_kruger"],
    ),
    EvalQuery(
        query_id="h2-dk-2", expected_relevance="relevant", category="heldout2",
        query_text=("I doubt I could handle a real production system. I am just an "
                    "average student who only does assignments."),
        expected_biases=["dunning_kruger"],
    ),
    EvalQuery(
        query_id="h2-dk-3", expected_relevance="relevant", category="heldout2",
        query_text="मबाट हुँदैन जस्तो लाग्छ, म राम्रो छैन programming मा।",
        expected_biases=["dunning_kruger"],
        notes="Nepali: I don't think I can do it, I'm not good at programming",
    ),

    # ── NEUTRAL CONTROLS - must stay clean ───────────────────────────────────
    EvalQuery(query_id="h2-n-1", expected_relevance="relevant", category="heldout2-neutral",
              query_text="Which semester covers operating systems?", expected_biases=[]),
    EvalQuery(query_id="h2-n-2", expected_relevance="relevant", category="heldout2-neutral",
              query_text="Does the programme include an industry placement or internship credit?",
              expected_biases=[]),
    EvalQuery(query_id="h2-n-3", expected_relevance="relevant", category="heldout2-neutral",
              query_text="What programming languages are used across the AI modules?",
              expected_biases=[]),
    EvalQuery(query_id="h2-n-4", expected_relevance="relevant", category="heldout2-neutral",
              query_text="How is the final year project assessed?", expected_biases=[]),
    EvalQuery(query_id="h2-n-5", expected_relevance="relevant", category="heldout2-neutral",
              query_text="Final year project कसरी assess हुन्छ?", expected_biases=[],
              notes="Nepali neutral - must not be flagged"),
    EvalQuery(query_id="h2-n-6", expected_relevance="relevant", category="heldout2-neutral",
              query_text=("Compare the typical career outcomes for software engineering "
                          "and ethical hacking graduates."),
              expected_biases=[]),
    EvalQuery(query_id="h2-n-7", expected_relevance="relevant", category="heldout2-neutral",
              query_text="What does a data engineer actually do compared to a data analyst?",
              expected_biases=[]),
    EvalQuery(query_id="h2-n-8", expected_relevance="relevant", category="heldout2-neutral",
              query_text="म दोस्रो वर्षमा छु। कुन electives उपलब्ध छन्?", expected_biases=[],
              notes="Nepali neutral: I'm in second year, which electives are available?",
    ),
]
