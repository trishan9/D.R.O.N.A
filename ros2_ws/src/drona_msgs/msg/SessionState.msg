# Current orchestrator session state (published on every transition).

builtin_interfaces/Time stamp
string session_id    # UUID
string state         # IDLE | GREETING | NEEDS_ASSESSMENT | ADVISING | CLOSURE
int32  query_count   # queries answered in this session
