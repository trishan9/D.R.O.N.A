# Perception output: current student engagement state.
# Published by perception_node at ~10 Hz.

builtin_interfaces/Time stamp
string  state        # ABSENT | PASSING_BY | APPROACHING | ENGAGED | DISENGAGING
float32 confidence   # EMA-smoothed face detection confidence [0, 1]
float32 distance_m   # estimated distance in metres (proxy from face area)
