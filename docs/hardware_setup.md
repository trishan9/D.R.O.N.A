# Hardware Setup Guide - SO-100 Arm

This guide covers wiring, calibration, and software configuration for the SO-100 6-DOF robotic arm used in D.R.O.N.A. Phase 2.

---

## Components

| Item | Specification |
|------|--------------|
| Arm | SO-100 (6× Dynamixel XL430-W250-T servos) |
| USB adapter | ROBOTIS U2D2 |
| Power supply | 12 V DC, ≥ 5 A |
| Cable | U2D2 → PC USB-A or USB-C |
| Webcam (optional) | Any UVC-compatible camera for MediaPipe detection |

---

## Wiring

```
12V PSU ──┬── SO-100 power bus
          │
         GND

U2D2 USB ─── PC USB port
U2D2 data ─── SO-100 Dynamixel bus (daisy-chained: ID 1→2→3→4→5→6)
```

Servo IDs are assigned 1–6 from base to gripper. Factory default baud rate is 57600. The D.R.O.N.A. implementation uses 57600 - do not change it without updating `SO100ArmInterface`.

---

## Pre-flight Checklist

Before launching the hardware nodes:

1. **Power on** the SO-100 arm and verify all LEDs illuminate briefly (self-test)
2. **Connect** the U2D2 USB adapter and confirm the device appears:
   ```bash
   ls /dev/ttyUSB*   # expect /dev/ttyUSB0 or similar
   ```
3. **Set permissions** (one-time, or add user to dialout group):
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   # or permanently:
   sudo usermod -aG dialout $USER  # then log out and back in
   ```
4. **Verify Ollama** is running (advising requires it):
   ```bash
   ollama serve &
   ollama pull mistral  # or whichever model is configured in settings.yaml
   ```
5. **Verify ChromaDB** is populated:
   ```bash
   python scripts/ingest_data.py --check
   ```
6. **Verify ACT checkpoint** exists (optional - KeyframePolicy fallback activates if absent):
   ```bash
   ls data/checkpoints/
   # expect: greet/ nod/ point/ idle/ listen/ farewell/
   ```

---

## Launch Hardware Mode

```bash
# On Ubuntu 24.04 + ROS2 Jazzy (native or WSL2 - see docs/wsl_setup.md).
# Real hardware over USB in WSL2 needs usbipd-win (wsl_setup.md §8).
source /opt/ros/jazzy/setup.bash
source ~/D.R.O.N.A/ros2_ws/install/setup.bash

ros2 launch drona_bringup drona_hardware.launch.py

# Custom serial port:
ros2 launch drona_bringup drona_hardware.launch.py arm_port:=/dev/ttyUSB1
```

---

## SO-100 Arm Interface - Implementation Notes

The arm is controlled via `drona.interaction.arm_interface.SO100ArmInterface`:

```python
class SO100ArmInterface(BaseArmInterface):
    # Dynamixel XL430-W250-T
    # Control table addresses:
    #   ADDR_TORQUE_ENABLE = 64
    #   ADDR_GOAL_POSITION = 116  (4-byte, little-endian)
    #   ADDR_PRESENT_POSITION = 132
    #
    # Tick range: 0–4095 (0.088° resolution)
    # Centre = 2048 ticks = 0 radians
    # Conversion: ticks = angle_rad * (4096 / 2π) + 2048
    #
    # GroupSyncWrite is used for simultaneous multi-servo commands
    # (critical for smooth, coordinated motion)
```

**Joint limits (radians):**

| Joint | Min | Max | Note |
|-------|-----|-----|------|
| J0 (base yaw) | −π | +π | Full rotation |
| J1 (shoulder pitch) | −1.57 | +1.57 | ±90° |
| J2 (elbow pitch) | −2.09 | +2.09 | ±120° |
| J3 (wrist pitch) | −1.57 | +1.57 | ±90° |
| J4 (wrist roll) | −π | +π | Full rotation |
| J5 (gripper) | 0 | 1.57 | Open/close |

---

## Calibration

On first use, verify the zero position is correct:

```bash
python -c "
from drona.interaction.arm_interface import make_arm_interface
arm = make_arm_interface(use_hardware=True, port='/dev/ttyUSB0')
arm.connect()
print('Current positions (rad):', arm.get_joint_positions())
arm.home()
print('After home:', arm.get_joint_positions())
arm.disconnect()
"
```

The `home()` method commands all joints to their zero position (2048 ticks). If any joint does not reach zero within 2 seconds, check for mechanical obstruction or power supply voltage.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `PortHandler open failed` | Wrong port or permissions | Check `/dev/ttyUSB*`, `sudo chmod 666` |
| Servo not responding (ID mismatch) | Factory reset wiped IDs | Use ROBOTIS Dynamixel Wizard 2.0 to re-assign IDs 1–6 |
| Arm jerks or stutters | Voltage sag | Use ≥ 5 A supply; check connections |
| Torque overload error | Mechanical obstruction | Power off, clear obstruction, re-home |
| `KeyframePolicy` used instead of ACT | Checkpoint missing | Run `python scripts/train_act.py` |

---

## Phase 2 Simulation (no hardware)

To run Phase 2 nodes without the physical arm, use `use_hardware: false` in `params.yaml` (the default). The `SimArmInterface` wraps `StubEnv` and accepts all the same commands silently.
