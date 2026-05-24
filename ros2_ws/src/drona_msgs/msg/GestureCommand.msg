# Command sent to the gesture execution node.

builtin_interfaces/Time stamp
string gesture_label   # greet | nod | point | idle | listen | farewell
float32 target_x       # optional: world-frame target for POINT gesture (metres)
float32 target_y
float32 target_z
string policy_hint     # "" = auto | "keyframe" | "act"
