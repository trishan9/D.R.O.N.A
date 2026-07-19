#!/usr/bin/env python3
"""
Verify D.R.O.N.A.'s full conversational loop, in sim.

Drives the complete interaction the way a real student session runs:

  engagement -> greeting (gesture + spoken hello)
             -> ask a question on /drona/ask
             -> advising_node -> brain (/advise) -> /drona/advising_response
             -> orchestrator SPEAKS the answer on /drona/say
             -> farewell

Assumes drona_gazebo.launch.py is running with advisor_remote_url pointing at a
brain (the mock brain, a local API, or the Colab T4). Checks that the robot
greeted, produced an advising response, and emitted a spoken answer.

    python3 scripts/verify_advising_loop.py "your question"
"""
from __future__ import annotations

import sys
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from drona_msgs.msg import AdvisingResponse, EngagementDetection


class ConvoProbe(Node):
    def __init__(self, question: str) -> None:
        super().__init__("drona_convo_probe")
        self.question = question
        self._eng = self.create_publisher(EngagementDetection, "/drona/engagement", 10)
        self._ask = self.create_publisher(String, "/drona/ask", 10)
        self.said: list[str] = []
        self.responses = 0
        self.create_subscription(String, "/drona/say", self._on_say, 10)
        self.create_subscription(AdvisingResponse, "/drona/advising_response",
                                 self._on_resp, 10)
        self._asked = False
        self._greeted_at: float | None = None
        self.create_timer(0.2, self._tick)

    def _on_say(self, msg: String) -> None:
        self.said.append(msg.data)
        self.get_logger().info(f'robot said: "{msg.data[:60]}..."')
        # The first utterance is the greeting; mark when it happened so we ask
        # a beat later (after the greet+listen gestures), when the session is in
        # NEEDS_ASSESSMENT and ready to accept a question.
        if self._greeted_at is None and ("D.R.O.N.A." in msg.data or "Hello" in msg.data):
            self._greeted_at = time.time()

    def _on_resp(self, msg: AdvisingResponse) -> None:
        self.responses += 1

    def _tick(self) -> None:
        # keep the student present so the session doesn't time out
        m = EngagementDetection()
        m.stamp = self.get_clock().now().to_msg()
        m.state = "engaged"
        m.confidence = 0.95
        m.distance_m = 0.9
        self._eng.publish(m)
        # ask ~3 s after the greeting (lets greet + listen gestures finish)
        if (not self._asked and self._greeted_at is not None
                and time.time() - self._greeted_at > 3.0):
            s = String(); s.data = self.question
            self._ask.publish(s)
            self.get_logger().info(f'asked: "{self.question}"')
            self._asked = True


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else \
        "How do I become a backend engineer in Nepal?"
    rclpy.init()
    n = ConvoProbe(question)
    end = time.time() + 40.0
    while time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.1)
        if n.responses >= 1 and len(n.said) >= 2 and n._asked:
            # answered + spoke; give speech a moment then finish early
            time.sleep(1.0)
            break

    greeted = any("D.R.O.N.A." in s or "Hello" in s for s in n.said)
    answered = len(n.said) >= 2  # greeting + at least one more utterance
    n.destroy_node()
    rclpy.shutdown()

    print("\n=== CONVERSATION LOOP RESULT ===")
    print(f"  utterances spoken   : {len(n.said)}")
    for i, s in enumerate(n.said, 1):
        print(f"    {i}. {s[:72]}{'...' if len(s) > 72 else ''}")
    print(f"  advising responses  : {n.responses}")
    print(f"  greeted             : {greeted}")
    print(f"  spoke an answer     : {answered}")
    if greeted and n.responses >= 1 and answered:
        print("  LOOP VERIFIED: greeted -> answered the question -> spoke it aloud.")
        return 0
    print("  NOT VERIFIED (is advisor_remote_url pointing at a running brain?)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
