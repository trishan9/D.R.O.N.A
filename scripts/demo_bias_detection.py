#!/usr/bin/env python3
"""
Demonstrate D.R.O.N.A.'s cognitive-bias detection (Research Contribution C2).

Runs one realistic student utterance per bias type through the rule-based
BiasDetector and prints what was flagged and how the advisor is instructed to
mitigate it. Pure/offline - no LLM, no retrieval - so it is safe for CI and for
a live thesis demo.

    python3 scripts/demo_bias_detection.py
"""
from __future__ import annotations

import sys

from drona.advising.bias_detector import BiasDetector
from drona.contracts import StudentProfile

# (label, utterance) - phrased the way a Softwarica student actually would.
CASES: list[tuple[str, str]] = [
    ("availability_heuristic",
     "My friend Rajesh got a job at Deerwalk right after his internship, so I should "
     "do exactly what he did, right?"),
    ("anchoring",
     "I only want a job that pays at least 200000 per month, nothing less than that."),
    ("confirmation",
     "I've already decided to become a data scientist. Just confirm that it's the "
     "best choice for me."),
    ("loss_aversion",
     "I'm scared of wasting my time - what if I switch to cybersecurity and it "
     "turns out to be a mistake?"),
    ("consistency",
     "I've told everyone I'll be a data scientist, I've gone too far to change now."),
    ("dunning_kruger (over)",
     "I already know everything about machine learning, I just need a senior role."),
    ("dunning_kruger (under)",
     "I'm probably not smart enough for AI, I'm just average at coding."),
]


def main() -> int:
    det = BiasDetector()
    profile = StudentProfile(session_id="demo-session", programme="csai")
    total_flags = 0
    detected_types: set[str] = set()

    print("=" * 78)
    print("D.R.O.N.A. - Cognitive Bias Detection (C2)")
    print("=" * 78)

    for expected, text in CASES:
        flags = det.detect(text, profile=profile)
        total_flags += len(flags)
        for f in flags:
            detected_types.add(f.bias_type)
        got = ", ".join(f.bias_type for f in flags) or "(none)"
        hit = "OK  " if flags else "MISS"
        print(f"\n[{hit}] expected~{expected}")
        print(f'  student : "{text[:70]}{"..." if len(text) > 70 else ""}"')
        print(f"  flagged : {got}")
        for f in flags:
            print(f"    - {f.bias_type}")
            print(f"      signal    : {f.detected_signal[:80]}")
            print(f"      mitigation: {f.mitigation_applied[:110]}")

    # A neutral question must NOT be flagged (false-positive guard).
    neutral = "What modules should I take next semester to prepare for backend work?"
    neutral_flags = det.detect(neutral, profile=profile)
    print("\n" + "-" * 78)
    print(f'[{"OK  " if not neutral_flags else "FALSE+"}] neutral control')
    print(f'  student : "{neutral}"')
    print(f"  flagged : {[f.bias_type for f in neutral_flags] or '(none - correct)'}")

    print("\n" + "=" * 78)
    print(f"distinct bias types detected: {len(detected_types)} -> {sorted(detected_types)}")
    print(f"total flags: {total_flags} | false positives on neutral: {len(neutral_flags)}")
    ok = len(detected_types) >= 5 and not neutral_flags
    print("RESULT:", "PASS - bias detection is working" if ok else "REVIEW NEEDED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
