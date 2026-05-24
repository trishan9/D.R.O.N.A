"""
Hardware Abstraction Layer for D.R.O.N.A. robot arm.

Three implementations share the same interface:

  BaseArmInterface   — abstract base; defines the contract
  SimArmInterface    — wraps StubEnv (no hardware, always available)
  SO100ArmInterface  — real SO-100 6-DOF arm via Dynamixel SDK

The GestureNode selects between Sim and SO100 via the `use_hardware` parameter.
Phase 2 hardware deployment only requires swapping to SO100ArmInterface — all
gesture logic, policy routing, and joint publishing remain unchanged.

SO-100 hardware notes:
  - 6 Dynamixel XL430-W250-T servos (IDs 1–6)
  - Communication: USB-to-TTL (U2D2) at 57600 baud
  - Position unit: Dynamixel ticks (0–4095 = 0–360°)
  - Control mode: Position Control Mode (Mode 3)
  - Home position corresponds to REST_POSE in demonstration.py
  - Torque must be enabled before commanding positions
  - DO NOT command beyond hardware limits — joint_limits in demonstration.py
    match the mechanical range of the SO-100
"""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod

import numpy as np
from loguru import logger

from drona.interaction.demonstration import (
    DOF,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    REST_POSE,
    clamp_joints,
)


# ── Base interface ─────────────────────────────────────────────────────────────

class BaseArmInterface(ABC):
    """Shared contract for all arm implementations."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to arm hardware or simulation."""

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly disconnect, returning arm to rest pose."""

    @abstractmethod
    def set_joint_positions(self, q: np.ndarray) -> None:
        """Command all joints simultaneously.

        Args:
            q: Joint positions in radians, shape (DOF,).
               Clamped to JOINT_LIMITS before sending.
        """

    @abstractmethod
    def get_joint_positions(self) -> np.ndarray:
        """Read current joint positions in radians, shape (DOF,)."""

    def home(self) -> None:
        """Move to REST_POSE."""
        self.set_joint_positions(REST_POSE)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.home()
        self.disconnect()


# ── Simulation interface ───────────────────────────────────────────────────────

class SimArmInterface(BaseArmInterface):
    """Simulated arm backed by StubEnv (exponential tracking dynamics).

    This is the default for Phase 1 and for development/testing without
    physical hardware. Behaviour is identical to the StubEnv used in
    gesture evaluation — the same env that generated the C3 baseline metrics.
    """

    def __init__(self, dt: float = 0.05) -> None:
        self._env = None
        self._dt = dt
        self._q = REST_POSE.copy()

    def connect(self) -> None:
        from drona.interaction.mujoco_env import StubEnv
        self._env = StubEnv(dt=self._dt)
        self._q = self._env.reset().copy()
        logger.info("SimArmInterface connected (StubEnv).")

    def disconnect(self) -> None:
        if self._env is not None:
            self._env.close()
            self._env = None
        logger.info("SimArmInterface disconnected.")

    def set_joint_positions(self, q: np.ndarray) -> None:
        q_clamped = clamp_joints(np.asarray(q, dtype=np.float32))
        if self._env is not None:
            self._q, _ = self._env.step(q_clamped)
        else:
            self._q = q_clamped

    def get_joint_positions(self) -> np.ndarray:
        return self._q.copy()


# ── SO-100 hardware interface ──────────────────────────────────────────────────

# Dynamixel servo IDs match joint ordering in demonstration.py
_DXL_IDS = [1, 2, 3, 4, 5, 6]  # j0_base_yaw … j5_gripper

# Conversion constants
_TICKS_PER_REV = 4096
_RAD_PER_TICK = (2 * math.pi) / _TICKS_PER_REV
_TICK_PER_RAD = _TICKS_PER_REV / (2 * math.pi)
_CENTER_TICK = 2048  # 180° = neutral

# Dynamixel control table addresses (XL430-W250-T)
_ADDR_TORQUE_ENABLE = 64
_ADDR_GOAL_POSITION = 116
_ADDR_PRESENT_POSITION = 132
_TORQUE_ENABLE = 1
_TORQUE_DISABLE = 0
_PROTOCOL_VERSION = 2.0
_BAUDRATE = 57600


def _rad_to_ticks(rad: float) -> int:
    """Convert radians to Dynamixel position ticks (0–4095)."""
    ticks = int(round(_CENTER_TICK + rad * _TICK_PER_RAD))
    return max(0, min(_TICKS_PER_REV - 1, ticks))


def _ticks_to_rad(ticks: int) -> float:
    """Convert Dynamixel position ticks to radians."""
    return (ticks - _CENTER_TICK) * _RAD_PER_TICK


class SO100ArmInterface(BaseArmInterface):
    """Real SO-100 arm interface using the Dynamixel SDK.

    Install:  pip install dynamixel-sdk
    Hardware: U2D2 USB adapter → TTL bus → 6× XL430-W250-T servos
    Port:     Windows: "COM3" (check Device Manager)
              Linux:   "/dev/ttyUSB0"

    Calibration:
        Before first run, verify REST_POSE in demonstration.py corresponds to
        the physical home position. Use the Dynamixel Wizard 2.0 to read tick
        values at home and update _CENTER_TICK if needed.
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = _BAUDRATE,
        move_time_ms: int = 200,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._move_time_ms = move_time_ms
        self._portHandler = None
        self._packetHandler = None
        self._group_sync_write = None
        self._q = REST_POSE.copy()

    def connect(self) -> None:
        try:
            from dynamixel_sdk import (  # type: ignore[import]
                GroupSyncWrite,
                PacketHandler,
                PortHandler,
                COMM_SUCCESS,
            )
        except ImportError as exc:
            raise RuntimeError(
                "dynamixel-sdk not installed. Run: pip install dynamixel-sdk"
            ) from exc

        self._portHandler = PortHandler(self._port)
        self._packetHandler = PacketHandler(_PROTOCOL_VERSION)

        if not self._portHandler.openPort():
            raise RuntimeError(f"Cannot open serial port: {self._port}")
        if not self._portHandler.setBaudRate(self._baudrate):
            raise RuntimeError(f"Cannot set baud rate to {self._baudrate}")

        # Group sync write for simultaneous position commands
        self._group_sync_write = GroupSyncWrite(
            self._portHandler, self._packetHandler,
            _ADDR_GOAL_POSITION, 4,  # 4 bytes for position
        )

        # Enable torque on all servos
        for dxl_id in _DXL_IDS:
            result, error = self._packetHandler.write1ByteTxRx(
                self._portHandler, dxl_id, _ADDR_TORQUE_ENABLE, _TORQUE_ENABLE
            )
            if result != 0:  # COMM_SUCCESS = 0
                logger.warning(f"Torque enable failed on servo {dxl_id}: error={error}")

        logger.info(f"SO-100 arm connected on {self._port}.")

    def disconnect(self) -> None:
        if self._packetHandler is None:
            return
        # Disable torque before disconnecting (safe power-off state)
        for dxl_id in _DXL_IDS:
            self._packetHandler.write1ByteTxRx(
                self._portHandler, dxl_id, _ADDR_TORQUE_ENABLE, _TORQUE_DISABLE
            )
        self._portHandler.closePort()
        logger.info("SO-100 arm disconnected (torque disabled).")

    def set_joint_positions(self, q: np.ndarray) -> None:
        q_clamped = clamp_joints(np.asarray(q, dtype=np.float32))
        if self._group_sync_write is None:
            raise RuntimeError("Not connected. Call connect() first.")

        self._group_sync_write.clearParam()
        for i, dxl_id in enumerate(_DXL_IDS):
            ticks = _rad_to_ticks(float(q_clamped[i]))
            # Pack as 4-byte little-endian
            param = [
                (ticks >> 0) & 0xFF,
                (ticks >> 8) & 0xFF,
                (ticks >> 16) & 0xFF,
                (ticks >> 24) & 0xFF,
            ]
            self._group_sync_write.addParam(dxl_id, param)

        self._group_sync_write.txPacket()
        self._q = q_clamped.copy()

        # Brief sleep so servos begin moving before next command
        time.sleep(0.001)

    def get_joint_positions(self) -> np.ndarray:
        if self._packetHandler is None:
            return self._q.copy()
        q = np.zeros(DOF, dtype=np.float32)
        for i, dxl_id in enumerate(_DXL_IDS):
            ticks, result, _ = self._packetHandler.read4ByteTxRx(
                self._portHandler, dxl_id, _ADDR_PRESENT_POSITION
            )
            if result == 0:  # COMM_SUCCESS
                q[i] = _ticks_to_rad(int(ticks))
            else:
                q[i] = self._q[i]  # fallback to last commanded position
        return q


# ── Factory ───────────────────────────────────────────────────────────────────

def make_arm_interface(use_hardware: bool = False, port: str = "/dev/ttyUSB0") -> BaseArmInterface:
    """Return the best available arm interface.

    Args:
        use_hardware: If True, attempt SO100ArmInterface; fall back to Sim on error.
        port: Serial port for SO-100 (ignored when use_hardware=False).
    """
    if use_hardware:
        try:
            arm = SO100ArmInterface(port=port)
            arm.connect()
            logger.info("Using SO-100 hardware arm.")
            return arm
        except Exception as exc:
            logger.warning(
                f"SO-100 connection failed ({exc}). Falling back to SimArmInterface."
            )

    arm = SimArmInterface()
    arm.connect()
    logger.info("Using simulated arm (StubEnv).")
    return arm
