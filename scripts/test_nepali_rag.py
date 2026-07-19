#!/usr/bin/env python3
"""
End-to-end Nepali advising test: translate-for-retrieval -> RAG -> Himalaya Gemma
-> grounded Nepali answer. Run on the machine with the RAG deps (chromadb +
encoders); it reaches Ollama (which serves the Nepali model) via ollama_host.

Env it expects:
    ADVISOR_LANGUAGE=ne
    LLM_BACKEND=ollama                 # primary also ollama (lazy, unused here)
    NEPALI_OLLAMA_MODEL=<gemma tag>
    OLLAMA_HOST=http://localhost:11434 # Ollama (in WSL, forwarded to localhost)

    python3 scripts/test_nepali_rag.py "optional Nepali question"
"""
from __future__ import annotations

import sys
import time

from drona.advising.engine import AdvisingEngine, make_query
from drona.utils.language import detect_language


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else \
        "मलाई डेटा साइन्समा जान मन छ, कहाँबाट सुरु गरौं?"
    print(f"question: {question}")
    print(f"detected language: {detect_language(question)}")

    t = time.time()
    eng = AdvisingEngine()
    print(f"engine (RAG) ready in {time.time() - t:.0f}s; advising ...")

    t = time.time()
    resp = eng.advise(make_query(question, programme="csai"))
    print(f"--- Nepali advising response in {time.time() - t:.0f}s ---")
    print("refusal:", resp.refusal)
    print("bias flags:", [b.bias_type for b in resp.bias_flags])
    print("\nSUMMARY:", resp.summary)
    print("\nSPEAK (robot voice):", resp.speak_text)
    for i, p in enumerate(resp.pathways, 1):
        print(f"\n[{i}] {p.pathway_title}  (goal={p.goal_type}, conf={p.confidence})")
        print("   ", p.rationale[:220])
        if p.matched_softwarica_modules:
            print("    modules:", ", ".join(p.matched_softwarica_modules[:5]))
    # crude check: did the answer actually come back in Nepali (Devanagari)?
    devanagari = detect_language(resp.speak_text) == "ne" if resp.speak_text else False
    print("\nanswer is in Nepali:", devanagari)
    return 0 if (not resp.refusal and devanagari) else 1


if __name__ == "__main__":
    sys.exit(main())
