#!/usr/bin/env bash
# Wait for the Himalaya Gemma model to finish pulling, then run a direct Nepali
# generation sanity test (no RAG - just: can the model speak Nepali?).
set -uo pipefail
export OLLAMA_HOST=0.0.0.0:11434
OLLAMA=~/ollama/bin/ollama
MODEL="hf.co/himalaya-ai/himalaya-gemma-4-e2b-it-gguf"

echo "waiting for model to be available ..."
for i in $(seq 1 80); do
  if "$OLLAMA" list 2>/dev/null | grep -qi "himalaya-gemma"; then
    echo "model present."
    break
  fi
  sleep 15
done

echo "=== ollama list ==="
"$OLLAMA" list 2>/dev/null | head -5

echo
echo "=== direct Nepali generation (no RAG) ==="
PROMPT="तपाईं एक शैक्षिक सल्लाहकार हुनुहुन्छ। एक विद्यार्थीले सोध्यो: 'मलाई डेटा साइन्समा जान मन छ, कहाँबाट सुरु गरौं?' छोटो, न्यानो नेपालीमा जवाफ दिनुहोस्।"
"$OLLAMA" run "$MODEL" "$PROMPT" 2>/dev/null
echo
echo "=== NE->EN translation test (used for retrieval) ==="
"$OLLAMA" run "$MODEL" "Translate to English, output only the translation: मलाई डेटा साइन्समा जान मन छ, कहाँबाट सुरु गरौं?" 2>/dev/null
echo
echo "GEMMA_CHECK_DONE"
