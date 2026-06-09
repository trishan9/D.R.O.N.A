"""
Statistical comparison harness (scipy.stats) for D.R.O.N.A.

Provides the inferential machinery to compare two conditions — e.g. *robot/
D.R.O.N.A. advising* vs *traditional advising*, or *ACT* vs *keyframe* gesture
smoothness, or *LoRA+RAG* vs *base+RAG* response quality.

Per the proposal, the **live user study with students is Phase 2** (it needs
ethics-board approval). What ships now is the analysis harness itself, validated
on synthetic/simulated samples, so that when real measurements arrive the
statistics are a one-line call. This mirrors how the rest of the system is
"deployment-ready, swap-in-real-data".

Tests provided (chosen for small-N robustness, typical of HRI studies):
  - Welch's t-test          (unequal-variance, parametric)
  - Mann–Whitney U          (non-parametric, no normality assumption)
  - Cohen's d               (standardised effect size)
  - rank-biserial r         (non-parametric effect size from U)
  - bootstrap 95% CI        (distribution-free CI on the mean difference)
  - Shapiro–Wilk            (normality check to guide test choice)

References:
  Field 2018, "Discovering Statistics"; Welch 1947; Mann & Whitney 1947;
  Cohen 1988 (effect sizes). HRI stats practice: Bartneck et al. 2020.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np
from scipy import stats


@dataclass
class ComparisonResult:
    """Full two-sample comparison between condition A and condition B."""

    label_a: str
    label_b: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float
    mean_difference: float            # mean_a - mean_b

    welch_t: float
    welch_p: float
    mann_whitney_u: float
    mann_whitney_p: float

    cohens_d: float
    rank_biserial_r: float

    ci95_low: float                   # bootstrap CI on (mean_a - mean_b)
    ci95_high: float

    normal_a: bool                    # Shapiro p > 0.05
    normal_b: bool
    recommended_test: str             # "welch_t" or "mann_whitney"
    significant: bool                 # recommended test p < alpha
    alpha: float
    effect_magnitude: str             # negligible/small/medium/large (|d|)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        test = self.recommended_test
        p = self.welch_p if test == "welch_t" else self.mann_whitney_p
        verdict = "SIGNIFICANT" if self.significant else "not significant"
        return (
            f"{self.label_a} (M={self.mean_a:.3f}) vs {self.label_b} "
            f"(M={self.mean_b:.3f}): Δ={self.mean_difference:+.3f} "
            f"[95% CI {self.ci95_low:+.3f}, {self.ci95_high:+.3f}], "
            f"{test} p={p:.4f} → {verdict}; "
            f"Cohen's d={self.cohens_d:+.3f} ({self.effect_magnitude})"
        )


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d with pooled standard deviation."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def _effect_magnitude(d: float) -> str:
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    if ad < 0.5:
        return "small"
    if ad < 0.8:
        return "medium"
    return "large"


def bootstrap_ci_diff(
    a: np.ndarray,
    b: np.ndarray,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap percentile CI for the difference in means (mean_a - mean_b)."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        sa = rng.choice(a, size=len(a), replace=True)
        sb = rng.choice(b, size=len(b), replace=True)
        diffs[i] = sa.mean() - sb.mean()
    lo = float(np.percentile(diffs, 100 * alpha / 2))
    hi = float(np.percentile(diffs, 100 * (1 - alpha / 2)))
    return lo, hi


def _is_normal(x: np.ndarray) -> bool:
    if len(x) < 3:
        return False
    try:
        return float(stats.shapiro(x).pvalue) > 0.05
    except Exception:
        return False


def compare_conditions(
    sample_a: Sequence[float],
    sample_b: Sequence[float],
    label_a: str = "A",
    label_b: str = "B",
    alpha: float = 0.05,
    n_boot: int = 10000,
) -> ComparisonResult:
    """Run the full comparison battery between two independent samples.

    Picks the recommended test from normality: Welch's t when both samples look
    normal, otherwise Mann–Whitney U. Always reports both plus effect sizes and
    a bootstrap CI so the thesis can present a complete, defensible picture.
    """
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each sample needs at least 2 observations.")

    welch = stats.ttest_ind(a, b, equal_var=False)
    try:
        mw = stats.mannwhitneyu(a, b, alternative="two-sided")
        mw_u, mw_p = float(mw.statistic), float(mw.pvalue)
    except ValueError:
        # All values identical → U test undefined; treat as no difference.
        mw_u, mw_p = 0.0, 1.0

    d = cohens_d(a, b)
    # rank-biserial r from U (effect size for Mann–Whitney).
    rbr = 1.0 - (2.0 * mw_u) / (len(a) * len(b)) if (len(a) and len(b)) else 0.0

    lo, hi = bootstrap_ci_diff(a, b, n_boot=n_boot, alpha=alpha)
    normal_a, normal_b = _is_normal(a), _is_normal(b)
    recommended = "welch_t" if (normal_a and normal_b) else "mann_whitney"
    p_used = float(welch.pvalue) if recommended == "welch_t" else mw_p

    return ComparisonResult(
        label_a=label_a,
        label_b=label_b,
        n_a=len(a),
        n_b=len(b),
        mean_a=float(a.mean()),
        mean_b=float(b.mean()),
        std_a=float(a.std(ddof=1)),
        std_b=float(b.std(ddof=1)),
        mean_difference=float(a.mean() - b.mean()),
        welch_t=float(welch.statistic),
        welch_p=float(welch.pvalue),
        mann_whitney_u=mw_u,
        mann_whitney_p=mw_p,
        cohens_d=d,
        rank_biserial_r=float(rbr),
        ci95_low=lo,
        ci95_high=hi,
        normal_a=normal_a,
        normal_b=normal_b,
        recommended_test=recommended,
        significant=p_used < alpha,
        alpha=alpha,
        effect_magnitude=_effect_magnitude(d),
    )


def paired_comparison(
    before: Sequence[float],
    after: Sequence[float],
    label: str = "paired",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Paired comparison (e.g. same participant pre/post) — Wilcoxon + paired t."""
    x = np.asarray(before, dtype=float)
    y = np.asarray(after, dtype=float)
    if len(x) != len(y):
        raise ValueError("Paired samples must be the same length.")
    if len(x) < 2:
        raise ValueError("Need at least 2 pairs.")

    t = stats.ttest_rel(x, y)
    try:
        w = stats.wilcoxon(x, y)
        w_stat, w_p = float(w.statistic), float(w.pvalue)
    except ValueError:
        w_stat, w_p = 0.0, 1.0

    diff = y - x
    return {
        "label": label,
        "n_pairs": len(x),
        "mean_before": float(x.mean()),
        "mean_after": float(y.mean()),
        "mean_change": float(diff.mean()),
        "paired_t": float(t.statistic),
        "paired_t_p": float(t.pvalue),
        "wilcoxon_stat": w_stat,
        "wilcoxon_p": w_p,
        "cohens_dz": float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) else 0.0,
        "significant": float(t.pvalue) < alpha,
        "alpha": alpha,
    }
