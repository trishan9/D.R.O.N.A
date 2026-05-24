# Mirrors drona.contracts.AdvisingResponse
# Full advising response including pathways, bias flags, and spoken text.

string query_id                   # echoes the query UUID
string summary                    # one-sentence overview for TTS
PathwayRecommendation[] pathways  # ordered list (anti-anchoring: not ranked)
BiasFlag[] bias_flags             # detected cognitive biases
bool   refusal                    # true if engine could not answer safely
string refusal_reason             # populated when refusal=true
string speak_text                 # robot-ready speech string
int32  generation_time_ms         # wall-clock LLM latency
