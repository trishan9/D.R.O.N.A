"""
Reusable UI component helpers for the D.R.O.N.A. dashboard.

Two layers:

  Pure data functions (no Streamlit imports) — safe to call in unit tests:
    format_bias_summary()
    format_pathway_markdown()
    format_citation_text()
    confidence_emoji()
    tier_label()
    bias_colour()

  Streamlit rendering functions (import streamlit) — not testable in CI:
    render_bias_flags()
    render_pathway_columns()
    render_citation_expander()
    render_session_stats()
    render_refusal_banner()

The split lets tests cover all formatting logic without needing a browser.
"""

from __future__ import annotations

from drona.contracts import (
    AdvisingResponse,
    BiasFlag,
    DataTier,
    PathwayRecommendation,
    RetrievalCitation,
)

# ── Tier helpers ──────────────────────────────────────────────────────────────

_TIER_LABELS: dict[str, str] = {
    "nepal": "🇳🇵 Nepal",
    "regional": "🌏 Regional",
    "international": "🌐 International",
    "synthetic": "🔬 Synthetic",
}

_TIER_COLOURS: dict[str, str] = {
    "nepal": "#1a7f37",        # green — local data prioritised
    "regional": "#0969da",     # blue
    "international": "#6e7781", # grey
    "synthetic": "#cf222e",    # red — always flagged
}

_BIAS_COLOURS: dict[str, str] = {
    "availability_heuristic": "#d97706",   # amber
    "anchoring":              "#b45309",   # brown-amber
    "confirmation":           "#7c3aed",   # purple
    "dunning_kruger":         "#dc2626",   # red
    "loss_aversion":          "#0891b2",   # teal
    "consistency":            "#059669",   # green-grey
}

_BIAS_LABELS: dict[str, str] = {
    "availability_heuristic": "Availability Heuristic",
    "anchoring":              "Anchoring Bias",
    "confirmation":           "Confirmation Bias",
    "dunning_kruger":         "Dunning-Kruger Effect",
    "loss_aversion":          "Loss Aversion",
    "consistency":            "Consistency Bias",
}

_CONFIDENCE_EMOJI: dict[str, str] = {
    "high":   "🟢",
    "medium": "🟡",
    "low":    "🔴",
}


# ── Pure formatting helpers (no Streamlit) ────────────────────────────────────

def confidence_emoji(confidence: str) -> str:
    """Return a coloured circle emoji for a confidence level string."""
    return _CONFIDENCE_EMOJI.get(confidence, "⚪")


def tier_label(tier_value: str) -> str:
    """Return a human-readable label with flag emoji for a tier string."""
    return _TIER_LABELS.get(tier_value, tier_value.capitalize())


def bias_colour(bias_type: str) -> str:
    """Return a hex colour string for a bias type."""
    return _BIAS_COLOURS.get(bias_type, "#6e7781")


def bias_label(bias_type: str) -> str:
    """Return a readable label for a bias type."""
    return _BIAS_LABELS.get(bias_type, bias_type.replace("_", " ").title())


def format_bias_summary(flags: list[BiasFlag]) -> list[dict[str, str]]:
    """Convert bias flags to a list of display dicts (no Streamlit).

    Returns:
        List of {label, signal, mitigation, colour} dicts.
    """
    return [
        {
            "label": bias_label(f.bias_type),
            "signal": f.detected_signal,
            "mitigation": f.mitigation_applied,
            "colour": bias_colour(f.bias_type),
        }
        for f in flags
    ]


def format_pathway_markdown(pathway: PathwayRecommendation, index: int) -> str:
    """Render a pathway as a Markdown string (no Streamlit dependency).

    Args:
        pathway: PathwayRecommendation to render.
        index: 1-based index for display (not used for ranking — anti-anchoring).

    Returns:
        Markdown string.
    """
    emoji = confidence_emoji(pathway.confidence)
    lines = [
        f"### {emoji} {pathway.pathway_title}",
        "",
        pathway.rationale,
    ]

    if pathway.local_market_evidence:
        lines += ["", "**Nepal market evidence:**", pathway.local_market_evidence[:200]]

    if pathway.international_context:
        lines += ["", "**International context:**", pathway.international_context[:200]]

    if pathway.matched_softwarica_modules:
        modules = ", ".join(f"`{m}`" for m in pathway.matched_softwarica_modules)
        lines += ["", f"**Relevant modules:** {modules}"]

    if pathway.next_concrete_steps:
        lines += ["", "**Next steps:**"]
        for step in pathway.next_concrete_steps:
            lines.append(f"- {step}")

    if pathway.citations:
        lines += ["", f"*{len(pathway.citations)} source(s) cited*"]

    return "\n".join(lines)


def format_citation_text(citation: RetrievalCitation) -> str:
    """Render a citation as a short text block."""
    label = tier_label(citation.tier.value)
    return f"[{label}] {citation.source_type} — {citation.excerpt[:180]}…"


def pathway_columns_layout(n_pathways: int) -> list[int]:
    """Return column width ratios for n_pathways columns.

    Anti-anchoring design: equal widths for all pathways so none appears
    visually dominant. Max 3 columns; 4th+ pathway wraps to a new row.

    Returns:
        List of integers (column ratios) for st.columns().
    """
    n = min(n_pathways, 3)
    return [1] * n if n > 0 else [1]


def summarise_stats(stats: dict) -> list[str]:
    """Convert stats dict to a list of display strings (no Streamlit)."""
    lines: list[str] = []
    lines.append(f"Queries this session: **{stats['query_count']}**")
    lines.append(f"Pathways shown: **{stats['total_pathways']}**")
    if stats["total_bias_flags"]:
        lines.append(f"Bias flags detected: **{stats['total_bias_flags']}**")
        for bias_type, count in stats["bias_type_counts"].items():
            lines.append(f"  - {bias_label(bias_type)}: {count}×")
    if stats["refusal_count"]:
        lines.append(f"Refusals (low coverage): **{stats['refusal_count']}**")
    if stats.get("avg_generation_ms") is not None:
        lines.append(f"Avg generation time: **{stats['avg_generation_ms']}ms**")
    nepal = stats.get("nepal_citations", 0)
    intl = stats.get("intl_citations", 0)
    if nepal + intl > 0:
        pct = int(100 * nepal / (nepal + intl))
        lines.append(f"Nepal citations: **{pct}%** of total")
    return lines


# ── Streamlit rendering functions ─────────────────────────────────────────────
# These import streamlit lazily so the module is importable in tests.

def render_bias_flags(flags: list[BiasFlag]) -> None:
    """Render bias flags as coloured warning boxes in Streamlit."""
    import streamlit as st  # type: ignore[import]

    if not flags:
        return

    st.markdown("---")
    st.markdown("#### Cognitive Bias Alerts")
    st.caption(
        "These patterns were detected in your question. "
        "The response has been adjusted to counteract them."
    )

    summaries = format_bias_summary(flags)
    cols = st.columns(min(len(summaries), 3))
    for col, item in zip(cols, summaries):
        with col:
            st.markdown(
                f"""<div style="border-left: 4px solid {item['colour']};
                    padding: 8px 12px; border-radius: 4px;
                    background: #f6f8fa; margin-bottom: 8px;">
                    <strong>{item['label']}</strong><br/>
                    <small style="color: #57606a">{item['signal']}</small><br/>
                    <small><em>Mitigation: {item['mitigation'][:100]}…</em></small>
                </div>""",
                unsafe_allow_html=True,
            )


def render_pathway_columns(pathways: list[PathwayRecommendation]) -> None:
    """Render pathways in equal-width columns (anti-anchoring layout)."""
    import streamlit as st  # type: ignore[import]

    if not pathways:
        st.info("No pathways were identified for this query.")
        return

    # Process in chunks of 3 for equal-width column layout
    for chunk_start in range(0, len(pathways), 3):
        chunk = pathways[chunk_start:chunk_start + 3]
        ratios = pathway_columns_layout(len(chunk))
        cols = st.columns(ratios)
        for col, pathway in zip(cols, chunk):
            with col:
                md = format_pathway_markdown(pathway, chunk_start + 1)
                st.markdown(md)
                if pathway.citations:
                    render_citation_expander(pathway.citations, pathway.pathway_title)
        if chunk_start + 3 < len(pathways):
            st.divider()


def render_citation_expander(
    citations: list[RetrievalCitation],
    context_label: str = "",
) -> None:
    """Render citations in a collapsible expander."""
    import streamlit as st  # type: ignore[import]

    label = f"Sources ({len(citations)})" + (f" — {context_label}" if context_label else "")
    with st.expander(label, expanded=False):
        # Sort: Nepal first
        tier_order = {"nepal": 0, "regional": 1, "international": 2, "synthetic": 3}
        sorted_cits = sorted(citations, key=lambda c: tier_order.get(c.tier.value, 9))
        for i, cit in enumerate(sorted_cits, 1):
            badge = tier_label(cit.tier.value)
            st.markdown(
                f"**[{i}]** `{badge}` · *{cit.source_type}* · "
                f"score: {cit.relevance_score:.3f}  \n{cit.excerpt[:200]}"
            )
            if i < len(sorted_cits):
                st.divider()


def render_refusal_banner(response: AdvisingResponse) -> None:
    """Render a refusal notice with human-followup prompt."""
    import streamlit as st  # type: ignore[import]

    st.warning(
        f"**DRONA could not generate a reliable answer.**\n\n"
        f"{response.refusal_reason or 'Insufficient data coverage.'}\n\n"
        "Please try rephrasing your question or speak with a human advisor.",
        icon="⚠️",
    )


def render_session_stats(stats: dict) -> None:
    """Render session statistics in the Streamlit sidebar."""
    import streamlit as st  # type: ignore[import]

    st.markdown("### Session Statistics")
    for line in summarise_stats(stats):
        st.markdown(line)
