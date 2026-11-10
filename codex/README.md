# Raspberry Pi SPI Display

Development backlog and planned final-container hardware/tool access:
[TODO.md](TODO.md).

## Project layout

```text
bt/          BLE client, pairing, discovery/menu, and Bluetooth activity feed
ui/          Companion face, keyboard input, and shared UI controls
test/       Hardware-free unittest suite
tools/      Standalone display and GPIO diagnostics
previews/   Saved display previews
codex/      Project instructions, README and progress notes
reports/    Generated BLE investigation reports
dashboard.py     Main display entry point
agent_status.py  Atomic agent-state publisher
```

Run commands from the project root. Live `agent-state.json` and
`bluetooth-activity.json` remain at the root as runtime status feeds. BLE reports
are written to `reports/ble-report.json`. Project documentation lives in `codex/`. Bluetooth source files now run as package modules:

```sh
.venv/bin/python -m bt.client --pair
.venv/bin/python -m unittest discover -s test -v
```

## Agent dashboard

Run from the Pi's host SSH shell:

```sh
.venv/bin/python dashboard.py
```

Starts with the animated companion face. Keyboard controls in the foreground
SSH terminal work without Enter: `m` dashboard menu, `f` face, `h` happy hello,
`b` Bluetooth menu, `n` eight-second nap, `q` quit. Ctrl-C also exits; terminal settings
are restored on exit. Use `--view menu` to start on the dashboard. The Bluetooth menu starts an eight-second nearby-device scan through the Pi's
`bluetoothctl`; `r` scans again. Names and addresses are shown one device at a time. Use the Up/Down arrow
keys to move the selection arrow and scroll through all observed devices; the
position counter shows the selected device and total. Press C to connect to the selected ESP32 and inspect the configured service. Devices must be
Bluetooth-discoverable; this does not discover Wi-Fi/LAN hosts. Scanning runs in
the background so navigation remains responsive, and repeated requests do not
overlap. It does not pair, connect, or change adapter power. A scan already in
progress finishes its bounded run even if you leave the menu. Use
`--view bluetooth` to start there. Noninteractive
launches still display the face but have no keyboard controls.
Pressing `q` (or `Q`) clears the display to black before quitting.

The face blinks and glances at up to 10 updates/second; system/state sampling
continues at `--interval`. It reacts to state-file errors and working/busy status.
These are visual reactions, not commands to an agent or a live chat connection.
Preview with `--preview previews/face-preview.png`; add `--view menu` for the dashboard.

Uses orientation 2, a requested 83,333,333 Hz SPI clock (reported working by
the user), and one-second metric refreshes. Changed pixels are enclosed in a
rectangle and only that region is sent, after rotation into native coordinates.
Set `--baudrate 32000000` for a lower clock or `--interval 2` for fewer updates.
Ctrl-C stops cleanly without rebooting or changing services.

CPU/RAM, uptime and temperature are read locally. CPU needs two samples;
unavailable readings show `--`. Task, status, detail, recent activity and
diagnostics come from `agent-state.json`, not an automatic Codex connection.
The agent can update this project file during work. The footer shows its age;
the initial READY status describes the completed dashboard task, not a live
agent heartbeat. Use `--state PATH` to read another producer's file. Producers
should write a temporary file and rename it atomically to avoid partial reads.
Invalid state is shown as a diagnostic and retried on the next refresh.

State fields: `task`, `status`, `detail` are strings; `activity` and `errors`
are arrays of strings. The last three activity entries and last error are shown.

Publish status and append recent activity atomically:

```sh
.venv/bin/python agent_status.py working 'Updating interface' 'Layout changes started'
.venv/bin/python agent_status.py ready 'Interface updated' 'Checks passed'
```

Project instructions require the agent to publish real work milestones. Status
changes are file-driven, not an automatic detection of whether Codex is running.
The title reads `CODEX @ PI`; metrics are text-only, activity has its own box,
and the colored shortcut row sits below it with bold key letters.
The update title uses the bold task text. Its subtitle uses `MM/DD-HH:MM: detail`,
or just `MM/DD-HH:MM` when detail is empty, with local time
recorded by the status publisher in `updated_at`. It measures the complete
line in pixels and truncates with an ellipsis to fit the available width.
The fit function is checked against both portrait and landscape width budgets;
the interface itself still uses the selected landscape orientation 2.

```sh
.venv/bin/python dashboard.py --preview previews/dashboard-preview.png
.venv/bin/python -m unittest test.test_dashboard
```

Run all UI checks with `.venv/bin/python -m unittest discover -s test -v`.

Preview is upright 320×240; hardware output is rotated to match orientation 2.
Dashboard hardware output and partial writes still need physical confirmation.

Headless Pillow and Adafruit RGB Display test for a 240×320 ILI9341.

## Wiring

If Blinka reports that it cannot identify the board on this Raspberry Pi 4B,
run from the host SSH shell with an explicit per-process board selection:

```sh
BLINKA_FORCEBOARD=RASPBERRY_PI_4B BLINKA_FORCECHIP=BCM2XXX .venv/bin/python dashboard.py
```

Use both overrides together. Setting only `BLINKA_FORCEBOARD` can leave the
chip ID unset and cause `TypeError: 'NoneType' object is not callable` inside
`digitalio.DigitalInOut`. The combined command selects the BCM2XXX GPIO backend.
Both display programs detect an unset backend and report this launch guidance.

This bypasses detection only; SPI/GPIO devices must still be accessible.
Restricted environments may hide `/proc/device-tree` and hardware device nodes.
The override does not expose those devices or change system configuration.

GPIO numbers: MISO 9 (pin 21), SCK 11 (23), MOSI 10 (19), DC 25
(22), RESET 24 (18), CS 8 (24). VCC uses 3.3V pin 1, GND pin 20,
and the current-limited LED connection uses 3.3V pin 17. LED power is
always on; the program does not control it.

## Setup and execution

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tools.screen_test --preview previews/test-pattern.png
.venv/bin/python -m tools.screen_test
```

For hardware failures, run `.venv/bin/python -m tools.screen_test --debug` to
report the failing operation and full traceback.

CS stays connected to GPIO8 (physical pin 24). Linux SPI controls CE0;
the display driver receives `cs=None` to avoid claiming the same pin through
libgpiod, which can fail with errno 16 when SPI is enabled.

The environment can reuse the OS Pillow installation. Hardware execution
requires access to `/dev/spidev0.0` and GPIO devices as the current user.
The test defaults to orientation 2 (landscape), 32 MHz SPI and a 30 FPS cap.
Use `--static` to compare a still frame, `--target-fps 15` to reduce updates,
or `--target-fps 0` for an unlimited throughput test. Actual FPS may be lower
than the cap. Use `--all-orientations` to cycle through all four rotations.

The earlier 125 MHz SPI setting was an experimental high-speed test;
this is not a verified panel limit or measured wire clock. If the driver rejects
it or the screen corrupts, rerun with `--baudrate 62500000`, then `32000000`
or the previously working `8000000`. No clock or boot configuration is changed.

Orientations are 1=0°, 2=90°, 3=180°, 4=270°, each with a three-second
identification pause, a five-second moving full-frame FPS test, and a
three-second results pause. Numbers 2 and 4 use landscape 320×240 canvases.
Report the number that reads upright. Use `--orientation 2` to repeat one,
and `--fps-seconds 10` to adjust benchmark duration (maximum 60 seconds).
FPS includes drawing, conversion, SPI writes and frame pacing, excludes identification pauses,
and measures submitted frames, not panel scanout. Check labels, borders and
motion visually; successful SPI writes alone do not prove the panel works.
`--preview` still saves the original hardware-free color pattern.

If SPI is absent, check whether it is enabled on the host and whether the
execution environment exposes hardware devices. Boot configuration, permission,
and service changes require explicit approval under AGENTS.md. Do not use sudo
or reboot as part of this test.

If startup reports `No Raspberry Pi header GPIO controller exposes GPIO 25`,
inspect controller metadata without claiming GPIO lines:

```sh
.venv/bin/python -m tools.gpio_diagnostics
```

Run this in the same host SSH shell as the dashboard. Blinka requires a visible
controller with a recognized Raspberry Pi header label and enough GPIO lines.
The output distinguishes missing device nodes, access errors, and controller
labels that need investigation. Board/chip overrides do not expose devices.

The Bluetooth menu uses the same top bar style as the dashboard, titled
`Bluetooth Menu`, with a Bluetooth operation status. One selected device is
shown at a time; Up/Down still traverses the complete discovery list.
The expanded BT TERMINAL displays the latest six wrapped lines of Bluetooth-only
feedback, backed by twenty timestamped events in `bluetooth-activity.json`.
Both dashboard scans/connections and the standalone BLE client publish to this
atomic project-local feed. The monitor polls it twice per second; unrelated
agent tasks/status no longer appear here. Missing/malformed feed data falls
back to local Bluetooth feedback. Successful connection or pairing is not
reported as proof of link encryption.

## ESP32 BLE service client

Install updated requirements in the Pi virtual environment:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python dashboard.py --ble-pair
```

Open B, select your ESP32 with Up/Down, then press C. The default target service
is `4fafc201-1fb5-459e-8fcc-c5c9c331914b`; override with `--ble-service UUID`.
Without `--ble-pair`, the client connects without explicitly requesting pairing.
If explicitly requested pairing fails with BlueZ AuthenticationFailed or a
pairing rejection, it tries
one normal BLE connection and records both attempts; other failures are not retried.
With it, BlueZ attempts pairing before connecting; the client registers a temporary, target-scoped
NoInputNoOutput BlueZ agent for headless Just Works pairing. It does not replace
the system default agent. PIN/passkey requests and numeric confirmation are
reported and rejected, not guessed or silently approved. The agent is removed
on session exit. Pairing may persist a bond on the Pi.
No SSH/network/service configuration is changed.

The session discovers GATT services, verifies the target service exists, and
atomically writes `reports/ble-report.json` in the project. It contains UUIDs and
characteristic properties, bounded characteristic response previews (at most 256 bytes per read, as hex
and UTF-8 text when valid), but no pairing credentials. To read a
known readable characteristic within that service, launch with
`--ble-read CHARACTERISTIC_UUID` (and `--ble-pair` if required), then press C.
With no --ble-read argument, the client automatically probes up to sixteen
readable characteristics in the target service, allowing twenty seconds per read.
Individual rejected reads are saved alongside discovered metadata. Read results include byte counts and bounded response previews. No arbitrary writes or application encryption
protocol are guessed. ESP32 firmware/protocol details are required for further
operations and for establishing the encryption requirements.

BLE work runs in the background, with a 150-second session timeout and automatic
disconnection on session exit. Scan and connection jobs cannot overlap. Keep the
app running until the monitor reports completion; exiting the process interrupts
background work. On failure, the report and SSH terminal include the exception type, bounded
message, and available D-Bus error name/details. The monitor shows a short reason; no
successful access or encryption is claimed. Hardware execution must be on the Pi.

Bluetooth device names come from discovery events, with a bounded lookup in the
Pi's BlueZ device cache when missing. Cached-only devices are excluded from scan
results. If neither source supplies a name, the entry says `Unknown`.

To run the current ESP32 probe without restarting the display, use a separate
native Pi SSH terminal (wait until any dashboard scan/connection has finished):

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m bt.client --pair
```

This defaults to the confirmed ESP32 address `80:B5:4E:E8:B4:69`. It publishes
actual progress into bluetooth-activity.json for the running BT terminal, also
updates agent-state.json, and writes reports/ble-report.json. The response data is project-local; encryption is still
marked unverified because discovery, pairing and reads alone do not establish
its negotiated security level. No firmware, bond deletion, adapter power,
networking or system service changes are performed.

### BLE read diagnostics

Every connection probe now runs diagnostics automatically; no new flag is needed.
Run `.venv/bin/python -m bt.client --pair` natively while other Bluetooth jobs
are idle, or restart the dashboard and use C on the selected ESP32.

Before reading the target service, the client reads the standard Generic Access
Device Name characteristic as a control, if advertised as readable. Each read has
its own twenty-second timeout. The report's `diagnostics` section includes:

- A UTC session start time and per-operation millisecond offsets/durations for
  correlation with an ESP32 serial log captured separately.
- `control_read`, with response preview or error; target results remain in `probes`.
- BlueZ `state_samples` before/after the control and after target reads, including
  Paired, Bonded, Connected and ServicesResolved when exposed by the host.
- Disconnect callbacks with the active phase and whether cleanup was intentional;
  each read also records the client's connected flag before and after.
- An evidence-based assessment, such as `Control OK / target read failed` or
  `Both reads failed / cause unresolved`. These do not identify the firmware cause.

Unavailable state properties remain unknown, rather than being interpreted as
false. Paired/bonded status does not establish negotiated link encryption (see
[BlueZ device properties](https://bluez.readthedocs.io/en/latest/device-api/)).
Service/control/read evidence is checkpointed to the atomic report during the
session and preserved if the overall session times out. A failed target read stops
further target probes to avoid queuing requests behind a stalled GATT operation.
ESP32 serial logs are not captured by this container or client automatically.

Target-read timeouts also include `transport_trace` counters for Bleak's BlueZ
InProgress retries and logged read completions. A busy-retry timeout is shown as
`BlueZ busy` in the monitor. With no logged retries/completion, the trace reports
that observation without claiming the ESP32 received the ATT request. This is
client-level evidence, not a packet capture. Counters are scoped to the reading
thread and do not store payloads; the temporary logger handler/level is restored
on exit. The behavior is based on the
[Bleak BlueZ read implementation](https://bleak.readthedocs.io/en/latest/_modules/bleak/backends/bluezdbus/client.html).

### One-shot native packet capture

While dashboard Bluetooth jobs are idle, run on the Pi:

```sh
.venv/bin/python -m tools.capture_ble
```

This starts btmon for controller index 0, runs one paired target-only read of the
confirmed ESP32 characteristic, then stops its own monitor process. Use --index N
for a different controller. Each run creates a unique reports/ble-TIMESTAMP-*/
directory containing capture.btsnoop, btmon.log, probe.log, and a copy of the
fresh BLE report if produced. It does not restart Bluetooth, change permissions,
or run sudo. Missing btmon or an immediate monitor/permission failure stops the
attempt before the probe. Wait for other Bluetooth jobs to finish first.

For replay on a host with btmon installed:

```sh
btmon -r reports/ble-TIMESTAMP-SUFFIX/capture.btsnoop
```

The target-only client mode is also available as `-m bt.client --pair --target-only`.
It skips the Device Name read so the target is the first application GATT read;
BlueZ's connection/service discovery still happens. btmon records host/controller
traffic, not an independent over-the-air radio capture. See the
[btmon manual](https://manpages.debian.org/bookworm/bluez/btmon.1.en.html).

### Quit cleanup and shared status permissions

Q, Ctrl-C and dashboard exceptions run Bluetooth shutdown before releasing the
hardware contexts. Shutdown cancels the owned BLE task, waits for its async client
context to clean up, and issues a bounded bluetoothctl disconnect for the device
this dashboard used. A scan already running is allowed to finish its bounded
subprocess. Quitting can therefore take a few seconds. Cleanup failures are
printed in SSH and recorded in the Bluetooth feed; an unconfirmed disconnect is
not reported as successful. Separate standalone client/capture processes and
connections owned by other applications are outside this dashboard's shutdown.

The two runtime status feeds are atomically written with mode 0644, allowing
native/container users to read them. They contain operational feedback, not
pairing secrets. If agent_status.py cannot read an existing owner-only state file,
it preserves the original under reports/agent-state-unreadable-TIMESTAMP.json
before publishing a fresh readable state. A state read/metrics error, explicit
error/blocked status or a nonempty state errors list causes the concerned face;
check the dashboard diagnostics for the specific trigger.

Capture directories use mode 0755 and completed capture/log/report files use 0644
for sharing between the native Pi and container users. BLE reports contain bounded
service values and packet captures contain diagnostic traffic. Older captures made
with owner-only permissions need their owner to grant read/traverse access before
another mapped user can inspect them. This file access issue is separate from
btmon's permission to open the host Bluetooth monitor channel.
