"""
D.R.O.N.A. Speech Node - ROS2 Jazzy

Turns text into the robot's spoken voice. Subscribes to /drona/say and speaks
each utterance, off the ROS executor thread so synthesis never blocks the robot.

Topics:
    sub  /drona/say  (std_msgs/String)   - text the robot should speak

Parameters:
    tts_backend : "espeak"   espeak | piper | http | log
    voice       : ""         backend-specific voice id (empty = backend default)
    rate_wpm    : 165        words-per-minute (espeak)
    volume      : 1.0        0..1
    http_url    : ""         POST endpoint for the "http" backend (VAPI/ElevenLabs/etc.)
    http_auth   : ""         Authorization header value, or "env:VAPI_API_KEY" to
                             read it from the environment (never store keys in
                             launch files / params)
    audio_player: "auto"     auto | ffplay | aplay | paplay | none

Design:
  - Every utterance is ALWAYS logged, so the robot's speech is visible in logs
    and in CI even with no audio device. Audio is best-effort on top.
  - Backends are pluggable behind one `speak(text)` call:
      espeak  - offline, robotic but always works (good for a Pi with no net)
      piper   - offline NEURAL TTS, natural voice, runs on a Pi (needs a model)
      http    - any cloud TTS returning audio bytes (VAPI / ElevenLabs / Azure);
                natural voice, needs a key + network
      log     - text only, no audio
  - Synthesis runs in a worker thread fed by a queue, so a slow cloud round-trip
    or a long sentence never stalls perception / control callbacks.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import tempfile
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def _resolve_auth(value: str) -> str:
    """Allow 'env:VAR_NAME' so API keys stay out of launch files and params."""
    if value.startswith("env:"):
        return os.environ.get(value[4:], "")
    return value


class SpeechNode(Node):
    def __init__(self) -> None:
        super().__init__("drona_speech_node")

        self.declare_parameter("tts_backend", "espeak")
        self.declare_parameter("voice", "")
        self.declare_parameter("rate_wpm", 165)
        self.declare_parameter("volume", 1.0)
        self.declare_parameter("http_url", "")
        self.declare_parameter("http_auth", "")
        self.declare_parameter("audio_player", "auto")

        self._backend = str(self.get_parameter("tts_backend").value).lower()
        self._voice = str(self.get_parameter("voice").value)
        self._rate = int(self.get_parameter("rate_wpm").value)
        self._volume = float(self.get_parameter("volume").value)
        self._http_url = str(self.get_parameter("http_url").value)
        self._http_auth = _resolve_auth(str(self.get_parameter("http_auth").value))
        self._player = self._pick_player(str(self.get_parameter("audio_player").value))

        # If a cloud backend was requested but not configured, fall back cleanly.
        if self._backend == "http" and not self._http_url:
            self.get_logger().warn(
                "tts_backend=http but http_url is empty - falling back to espeak."
            )
            self._backend = "espeak"
        if self._backend == "espeak" and not shutil.which("espeak-ng") \
                and not shutil.which("espeak"):
            self.get_logger().warn(
                "espeak not installed - speech will be logged only "
                "(sudo apt install espeak-ng)."
            )
            self._backend = "log"

        self._q: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        self.create_subscription(String, "/drona/say", self._on_say, 10)
        self.get_logger().info(
            f"SpeechNode ready. backend={self._backend} "
            f"player={self._player or 'none'} voice={self._voice or 'default'}"
        )

    # ── ROS ────────────────────────────────────────────────────────────────────

    def _on_say(self, msg: String) -> None:
        text = msg.data.strip()
        if text:
            self._q.put(text)

    # ── Worker ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        while True:
            text = self._q.get()
            # The utterance is always recorded, audio or not.
            self.get_logger().info(f'🗣  "{text}"')
            try:
                self._synthesize(text)
            except Exception as exc:  # noqa: BLE001 - speech must never crash the robot
                self.get_logger().warn(f"TTS ({self._backend}) failed: {exc}")

    def _synthesize(self, text: str) -> None:
        if self._backend == "log":
            return
        if self._backend == "espeak":
            self._speak_espeak(text)
        elif self._backend == "piper":
            self._speak_piper(text)
        elif self._backend == "http":
            self._speak_http(text)

    # ── Backends ─────────────────────────────────────────────────────────────

    def _speak_espeak(self, text: str) -> None:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        args = [exe, "-s", str(self._rate), "-a", str(int(self._volume * 200))]
        if self._voice:
            args += ["-v", self._voice]
        args.append(text)
        subprocess.run(args, check=False)

    def _speak_piper(self, text: str) -> None:
        # Offline neural TTS. Expects `piper` on PATH and a voice model at `voice`
        # (a .onnx path). Produces natural speech and runs on a Raspberry Pi.
        piper = shutil.which("piper")
        if not piper or not self._voice:
            raise RuntimeError("piper backend needs `piper` on PATH and voice=<model.onnx>")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav = f.name
        subprocess.run([piper, "--model", self._voice, "--output_file", wav],
                       input=text.encode(), check=True)
        self._play(wav)
        os.unlink(wav)

    def _speak_http(self, text: str) -> None:
        # Provider-agnostic cloud TTS: POST the text, receive audio bytes, play
        # them. Works with any HTTP TTS (VAPI / ElevenLabs / Azure) by setting
        # http_url + http_auth + voice. Natural voice; needs a key + network.
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._http_auth:
            headers["Authorization"] = self._http_auth
        # A conventional body; override per-provider once the exact schema/voice
        # is confirmed. Kept minimal so it maps onto most TTS APIs.
        body: dict = {"text": text}
        if self._voice:
            body["voice"] = self._voice
        r = httpx.post(self._http_url, json=body, headers=headers, timeout=30.0)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        suffix = ".mp3" if "mpeg" in ctype or "mp3" in ctype else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(r.content)
            audio = f.name
        self._play(audio)
        os.unlink(audio)

    # ── Audio playback ───────────────────────────────────────────────────────

    def _pick_player(self, requested: str) -> str | None:
        if requested and requested != "auto":
            return requested if requested != "none" else None
        for p in ("ffplay", "paplay", "aplay"):
            if shutil.which(p):
                return p
        return None

    def _play(self, path: str) -> None:
        if not self._player:
            self.get_logger().warn("no audio player found (install ffmpeg/alsa-utils)")
            return
        if self._player == "ffplay":
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                           check=False)
        else:
            subprocess.run([self._player, path], check=False)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SpeechNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
