# Result published after a gesture completes (or fails).

builtin_interfaces/Time stamp
string gesture_label    # echoes the command
bool   success
int32  frames_executed
float32 duration_s
string policy_used      # "KeyframePolicy" | "LeRobotACT(<gesture>)"
string error_message    # non-empty on failure
