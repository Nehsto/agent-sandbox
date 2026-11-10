# AGENTS.md — Raspberry Pi Autonomous Interface Project

## Project Objective

Develop a graphical interface for a 2.4-inch ILI9341 TFT display connected to a Raspberry Pi 4B over SPI.

You are responsible for designing, implementing, testing, and iteratively improving the interface.

Favor autonomy, experimentation, and maintainable code.

## Hardware

**Host:** Raspberry Pi 4B running Raspberry Pi OS  
**Display:** ILI9341, 240×320 pixels, SPI, 3.3V logic

### Pin Configuration

| Display | Raspberry Pi |
|---|---|
| MISO | GPIO9, physical pin 21 |
| LED | 3.3V, if current-limited |
| SCK | GPIO11, physical pin 23 |
| MOSI | GPIO10, physical pin 19 |
| DC | GPIO25, physical pin 22 |
| RESET | GPIO24, physical pin 18 |
| CS | GPIO8, physical pin 24 |
| GND | Physical pin 20 |
| VCC | 3.3V, physical pin 1 |

SPI device: `/dev/spidev0.0`

Do not change GPIO assignments without permission.

## Software

- Python 3
- Pillow for drawing graphics
- Adafruit CircuitPython RGB Display for ILI9341 communication
- Prefer a Python virtual environment.
- Avoid installing unnecessary system packages.
- Do not require a desktop environment or graphical session.

## Interface Requirements

Develop an interface capable of displaying:

1. Current agent task and execution status.
2. CPU and RAM utilization.
3. System uptime and temperature.
4. Recent agent activity.
5. Errors and diagnostic information.

You may introduce additional features and visualizations where useful.

Design for the display's limited resolution and refresh bandwidth. Avoid unnecessary full-screen updates.

## Autonomy

You are encouraged to:

- Explore the project and available hardware interfaces.
- Design and implement software independently.
- Execute tests and debug failures.
- Refactor code when appropriate.
- Document decisions and technical findings.
- Propose additional features.

Prefer working implementations over extensive planning.

If a task fails, investigate the cause and attempt a reasonable correction.

Do not claim that functionality has been verified on physical hardware unless a hardware test supports that claim.

## Security and System Restrictions

The Raspberry Pi is accessed remotely over SSH.

**Preserving remote access is a critical requirement.**

Do not perform the following without explicit approval:

- Reboot or shut down the Raspberry Pi.
- Modify SSH settings, networking, routing, or firewall rules.
- Change boot configuration or systemd services.
- Modify files outside the project directory except for approved dependencies.
- Execute destructive or irreversible commands.
- Modify GPIO connections or electrical configurations.
- Access private credentials or unrelated personal files.

Never disable SSH connectivity.

Do not execute commands as root unless explicitly authorized.

## Development Workflow

1. Inspect the existing project.
2. Identify the next implementation objective.
3. Make focused changes.
4. Run applicable tests.
5. Verify functionality when hardware access is available.
6. Record meaningful progress and remaining problems.

Maintain a `codex/PROGRESS.md` file describing completed features, active tasks, and known issues.

Maintain a `codex/README.md` containing setup and execution instructions.

### On-screen agent activity

Keep the project's `agent-state.json` current while doing project work. At the
start, publish `working`; append concise activity at meaningful milestones;
publish `ready` when finished, or `blocked`/`error` when appropriate. Use
`agent_status.py` for atomic writes. This file drives the display; it is not
an automatic runtime heartbeat. Do not publish invented activity.

## Agent Behavior

Be resource-conscious: the Raspberry Pi has limited processing power and memory.

Work independently within the permitted project scope. Ask for approval when an action crosses the defined security boundaries.

Prioritize a functioning interface, robust error handling, and reliable operation over unnecessary complexity.
