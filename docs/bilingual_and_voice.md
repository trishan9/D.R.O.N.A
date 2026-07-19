# D.R.O.N.A. — Bilingual Advising (English + Nepali) & Natural Voice

D.R.O.N.A. advises in **English and Nepali**, and speaks its answers in a
**natural voice**. This document explains how both work, what runs where, and how
to enable the higher-quality options.

---

## 1. How bilingual advising works

Retrieval is **language-agnostic** — the same hybrid RAG index over the
Softwarica curriculum serves both languages. Only the *generation* differs:

```
  student question
        │
        ▼
  detect language  (Devanagari ratio; catches code-switched Nepali)
        │
        ├── English ──►  fine-tuned Qwen3-4B (Softwarica + bias fine-tune)
        │
        └── Nepali  ──►  Himalaya Gemma (Nepali-specialised, via Ollama)
                          grounded by the SAME retrieved context,
                          prompted to answer in Nepali
```

- **Detection** (`drona/utils/language.py`) is a cheap Devanagari-ratio check, so
  it runs inline and on a Pi. A pure-English query stays English; any real
  Nepali/Devanagari (including `म backend engineer banna chahanchu, कसरी?`)
  routes to Nepali. Force it with `ADVISOR_LANGUAGE=en|ne` (default `auto`).
- **Routing** (`drona/advising/router_client.py`) picks the model by language.
  The **JSON keys stay English** (parsing is unchanged); only the human-readable
  values — titles, rationale, steps, `speak_text` — become Nepali.
- **Context-window budgeting**: Devanagari is token-dense, so the Nepali prompt
  gets a smaller retrieval budget (`NEPALI_CONTEXT_CHAR_BUDGET`, default 6000
  chars) to stay inside Gemma's window; English gets more
  (`ENGLISH_CONTEXT_CHAR_BUDGET`, default 9000). Lower-priority citations are
  dropped whole (never truncated mid-citation) once the budget is hit.

### Graceful fallback (works today, one model)
If the Nepali model isn't installed, Nepali queries **fall back to the primary
Qwen3** — which is multilingual and answers Nepali well when the prompt asks it
to. So **bilingual works out of the box with just Qwen3**; Himalaya Gemma is an
*upgrade* for stronger Nepali fluency, not a prerequisite.

---

## 2. Enabling the Himalaya Gemma Nepali model (optional upgrade)

Run on whichever machine serves the brain (the Colab T4, or a local box):

```bash
# 1. install Ollama (one-time)
curl -fsSL https://ollama.com/install.sh | sh

# 2. pull the Nepali model (GGUF, ~2-3 GB)
ollama pull hf.co/himalaya-ai/himalaya-gemma-4-e2b-it-gguf

# 3. tell D.R.O.N.A. to use it (defaults already point here)
export ADVISOR_LANGUAGE=auto
export NEPALI_OLLAMA_MODEL=hf.co/himalaya-ai/himalaya-gemma-4-e2b-it-gguf
```

That's it — Nepali queries now route to Gemma, English stays on your fine-tuned
Qwen3, both grounded in the same curriculum. Nothing else changes.

> **Model choice note:** `gemma4-e2b-it-nepali` and `himalaya-gemma-4-e2b-it` are
> the same family; use whichever GGUF tag Ollama resolves. They have no knowledge
> of the Softwarica curriculum themselves — that always comes from RAG, so the
> answer is grounded regardless of which model writes it.

---

## 3. Natural voice (the robot speaking)

`speech_node` turns `/drona/say` into audio. It is pluggable — pick a backend per
deployment:

| Backend | Voice | Network | Nepali | Use |
|---|---|---|---|---|
| `espeak` (default) | robotic | offline | yes (`voice:=ne`) | always-works fallback, Pi |
| `piper` | natural neural | offline | model-dependent | self-contained natural voice on a Pi |
| **`elevenlabs`** | **natural, warm** | cloud | **yes (multilingual)** | the "not robotic" voice you want |
| `http` | provider-defined | cloud | provider | any TTS HTTP API |

### ElevenLabs (recommended for natural, multilingual voice)

```bash
export ELEVENLABS_API_KEY=sk_...            # from the env, never a param file
ros2 launch drona_bringup drona_gazebo.launch.py \
    tts_backend:=elevenlabs voice:=<voice_id>
```

- Uses `eleven_multilingual_v2`, which speaks **Nepali and English** — so the
  same voice narrates whichever language the brain answered in.
- The key is read only from `ELEVENLABS_API_KEY`; it is never stored in a launch
  file or params.yaml.
- If the key is unset, `speech_node` logs a warning and falls back to espeak, so
  a missing key never silences the robot.

> **Why not VAPI?** VAPI is a real-time voice-*agent* platform (it runs the whole
> STT→LLM→TTS call). For a robot that already has its own bias-aware brain, that
> would mean handing the conversation to VAPI and exposing our brain as its custom
> LLM — a much larger integration. ElevenLabs (which VAPI uses under the hood for
> voices) gives the same natural speech for our `speak_text` with a simple, direct
> call. If you later want a full spoken back-and-forth, VAPI-with-custom-LLM is the
> path, and the `http` backend + our `/advise` API are the hooks for it.

---

## 4. End-to-end: a Nepali student session

1. Student walks up → perception → robot greets (spoken).
2. Student asks in Nepali (typed, or via an STT node publishing `/drona/ask`):
   *"मलाई डेटा साइन्समा जान मन छ, कसरी सुरु गरौं?"*
3. `advising_node` → brain: retrieval (shared) → **Himalaya Gemma** answers in
   Nepali, grounded in the Softwarica curriculum, bias-checked.
4. Orchestrator publishes the Nepali `speak_text` → `speech_node` → **ElevenLabs**
   speaks it in a natural Nepali voice.
5. Farewell.

Every layer — brain and voice — is localised, and both degrade safely (Gemma →
Qwen3, ElevenLabs → espeak) so the robot always responds.

---

## 5. Thesis framing

This is a real contribution for a Nepali institution: **bias-aware academic
advising delivered in Nepali**, with the localisation demonstrated at both the
content layer (a Nepali-specialised LLM, RAG-grounded in the local curriculum)
and the interaction layer (natural Nepali speech). State the boundary honestly:
the Nepali model's *knowledge* comes from retrieval over the Softwarica
curriculum, not from the model itself — which is exactly why grounding matters.
