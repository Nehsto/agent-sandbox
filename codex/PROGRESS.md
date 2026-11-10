# Progress

## Board detection diagnosis — 2026-11-08

- User reports PlatformDetect 3.90.0 cannot identify the board at startup.
- This environment hides `/proc/device-tree/model` and `/dev/spidev0.0`;
  missing board metadata is a possible cause, not confirmed for user's shell.
- Verified explicit `BLINKA_FORCEBOARD=RASPBERRY_PI_4B` and
  `BLINKA_FORCECHIP=BCM2XXX` return the expected detector IDs; documented
  per-process host launch. Physical startup with override remains pending.

## Completed

- Inspected Raspberry Pi 4B environment and existing project instructions.
- Recorded LED power on physical pin 17; other assignments unchanged.
- Created project virtual environment and finite color/pattern test with
  hardware-free PNG preview and actionable device errors.

## Validation and remaining work

- PNG preview generated successfully at 240×320; Python compilation passed.
- Hardware test attempted and stopped cleanly because SPI device is missing.
- Dependency installation could not reach package indexes due to DNS/network
  restrictions. Adafruit Blinka and RGB Display still need installation.
- Next: obtain host SPI/GPIO access, install requirements, and repeat the test.

## Known issues

- This execution environment exposes no `/dev/spidev0.0` or `/dev/gpiochip*`.
- No SPI devices appeared in `/sys/bus/spi/devices`; GPIO chips appear in sysfs.
- Physical display operation has not been verified. SPI enablement versus
  execution-environment device restrictions remains unresolved.
- No boot, SSH, network, service, or system permission settings changed.

## SPI recheck — 2026-11-08

- After user enabled SPI, sysfs now lists `spidev0.0` and `spidev0.1`.
  This confirms host SPI device registration.
- The execution environment still exposes no `/dev/spidev*` device nodes,
  so this session cannot run the physical display test yet.
- Next: expose host SPI/GPIO devices to this execution environment, or run
  the documented display test directly from a host SSH shell.

## Host test diagnostics — 2026-11-08

- User confirmed host SPI and GPIO device nodes; host display test reports
  errno 16 (resource busy). The resource responsible is not yet identified.
- Added operation-specific errors and `--debug` tracebacks to the test.
- PNG preview and Python compilation pass after the diagnostic change.
- Next: rerun on host with `--debug` to identify the failing resource before
  changing the hardware access implementation. Physical operation unverified.

## CE0 conflict correction — 2026-11-08

- Host traceback identifies the failure as the libgpiod claim of GPIO8.
- User confirmed CS wiring on physical pin 24. Removed the separate GPIO8
  claim and passed `cs=None` to use SPI hardware CE0. Wiring is unchanged.
- PNG preview and Python compilation pass. Host rerun and physical display
  confirmation remain pending; this sandbox cannot access SPI devices.

## Pin review — 2026-11-08

- Reviewed code against AGENTS.md: DC GPIO25/pin22, RESET GPIO24/pin18,
  CS CE0 GPIO8/pin24, SPI0 SCK GPIO11/pin23, MOSI GPIO10/pin19,
  MISO GPIO9/pin21. No pin reassignment made.
- Upstream Blinka Linux SPI opens bus 0/device 0 for SPI0 and leaves
  hardware CS enabled; no extra hardware-CS setting indicated in that code.
- User reports no output. Added flushed debug messages before imports,
  GPIO claims, SPI opening, and display initialization to locate a stall.
- Physical wiring and installed host library behavior still need confirmation.

## Orientation and FPS test — 2026-11-08

- User reports display output after CE0 correction.
- Added numbered rotations 1–4, landscape canvases for 2/4, directional labels,
  moving marker and full-frame FPS on screen and terminal.
- Requested SPI speed defaults to experimental 125 MHz, configurable with
  `--baudrate`; actual clock and maximum reliable panel speed are unverified.
- Benchmark duration is bounded; drawing, conversion and writes are included.
- Compilation, original preview, and all four native framebuffer dimensions
  verified with a fake display. Hardware FPS and preferred rotation pending.

## Animation stability — 2026-11-08

- User selected orientation 2 and reports approximately 30 FPS with skew when
  animation starts. Cause remains unconfirmed (transfer integrity versus tearing).
- Defaulted to orientation 2, reduced requested SPI from 125 to 32 MHz and
  added a 30 FPS cap without catch-up bursts; unlimited mode remains available.
- Added static comparison and explicit all-orientations options.
- Compilation and PNG preview pass. Host comparison at 32/8 MHz pending.

## Agent dashboard — 2026-11-08

- User reports 83,333,333 Hz request works well; used it for dashboard default.
- Implemented headless 320×240 orientation-2 dashboard: task/status/detail,
  CPU/RAM bars, uptime, temperature, recent activity and error footer.
- Project-local JSON state supplies agent information with visible update age;
  no automatic agent lifecycle integration is claimed. System metrics are live.
- One-second polling, changed-region SPI writes, bounded state input,
  unavailable-metric handling and clean Ctrl-C exit implemented.
- Preview visually inspected. Compilation and three tests pass, covering
  rotated partial-write reconstruction, unchanged-frame suppression, malformed
  state recovery and missing metrics/long text rendering.
- Remaining: user run on physical display to verify dashboard and partial writes.
  Sandbox still lacks SPI device access. No system settings or wiring changed.

## Companion face and menu — 2026-11-08

- User confirmed dashboard works on display and requested a default face with
  keyboard access to that dashboard as a menu.
- Added Pillow-drawn face, blinking, gaze, happy/nap/thinking/error expressions.
- Foreground terminal keys: m menu, f face, h hello, b blink, s nap, q quit.
  Terminal settings restore on normal exit, exceptions and Ctrl-C.
- Face redraws at up to 10 Hz with changed-region writes; state/system sampling
  stays at the configured interval. No new GPIO assignments or dependencies.
- Face preview inspected; six tests and compilation pass, including real pseudo-
  terminal input/restoration, reaction expiry, and rotated partial updates.
- Remaining: physical face/menu review. Agent-state updates remain file-driven;
  keyboard reactions do not invoke an agent or speech service.

## Menu refinements — 2026-11-08

- Changed title to CODEX @ PI, removed CPU/RAM bars, boxed recent activity,
  and reserved separate rows for shortcuts and diagnostics.
- Shared shortcut renderer gives every action a different color and bold key
  in both face and menu views; verified legend fits the 320-pixel width.
- Added atomic agent_status.py publisher and project instructions for working,
  milestone and completion state updates. No runtime heartbeat is claimed.
- Menu preview inspected; six existing tests plus publisher transition checks
  pass. Physical review of updated layout remains pending.

- Quit refinement: q/Q now sends a full native-size black frame before exiting.
  Python compilation passed; physical confirmation pending.

- Latest-update refinement: publisher records timezone-aware update timestamps;
  menu top line shows `<MM/DD-HH:MM>Update: latest activity` in monospace.
  Pixel-measured truncation includes the prefix and ellipsis, tested with both
  220px and 300px budgets. Landscape orientation remains 2. Seven tests pass.

- Changed nap shortcut from S to N in keyboard handling, both visual legends,
  terminal help and README. Seven existing tests pass; previews regenerated.

- Simplified latest-update prefix to `MM/DD-HH:MM: message`, removing angle
  brackets and the Update label. Pixel fitting retained; seven tests pass.

- Restored task as a bold update title. Subtitle now shows timestamp plus
  optional detail; empty/whitespace detail shows timestamp alone. Both lines
  remain width-limited. Eight tests pass, including empty-subtitle behavior.

## Unset GPIO backend diagnosis — 2026-11-08

- Reproduced board-only override selecting RASPBERRY_PI_4B with chip ID None
  and digitalio.Pin None, matching the reported DigitalInOut TypeError.
- Confirmed adding BLINKA_FORCECHIP=BCM2XXX selects a callable Raspberry Pi
  GPIO backend in the installed Blinka 10.1.0; no dependency changes needed.
- Dashboard and screen test now report actionable guidance for an unset backend;
  README explains why both overrides are required in this environment.
- Eight UI tests and Python compilation pass. Physical startup remains pending
  because this environment lacks the SPI/GPIO device nodes.

## GPIO controller discovery — 2026-11-08

- User reports GPIO25 header controller discovery failure after both overrides.
- Installed backend accepts pinctrl-bcm2835, pinctrl-bcm2711 and pinctrl-rp1
  labels and requires line count greater than 25. Failure means no visible
  accessible controller matched; host metadata is needed to distinguish causes.
- Added read-only gpio_diagnostics.py to print chip labels, line counts and
  access failures without claiming lines. Compilation passes; local run confirms
  no /dev/gpiochip* nodes in this sandbox. Host output remains pending.

## Bluetooth menu — 2026-11-08

- B now opens a Bluetooth status menu instead of requesting a blink; automatic
  face blinking remains active. Both shortcut legends and terminal help updated.
- Shows adapter name, power/discoverability/pairability and up to three known
  devices using host bluetoothctl. R refreshes; M/F return to dashboard/face.
- Queries are read-only and bounded to two seconds per command, with unavailable
  adapter, missing command and timeout messages. No system settings changed.
- Eight existing tests pass with added B navigation assertion. Bluetooth success,
  missing-command and timeout checks pass with mocked subprocesses; preview saved.
- Pillow is now available in the container. Native Bluetooth/display verification
  remains for the user; restart dashboard.py to load this code change.

## Nearby Bluetooth discovery — 2026-11-08

- Replaced cached-device listing with an eight-second bluetoothctl discovery
  session on B/menu entry and R. Shows names and addresses of devices observed
  through NEW or RSSI events during that scan; no Wi-Fi/LAN discovery claimed.
- Background worker keeps drawing/keys responsive and prevents overlapping scans.
  Subprocess has an eleven-second hard timeout; no pairing or power changes.
- Eleven tests pass, including scan-output parsing, unavailable/timeout handling,
  empty results and nonblocking/nonoverlapping worker behavior.
- Physical Bluetooth discovery remains unverified in the container. User should
  restart the native dashboard and test with a discoverable nearby device.

## Bluetooth scrolling and selection — 2026-11-08

- Retain all devices observed during a scan. Up/Down moves a visible selection
  arrow/highlight, scrolling in pages of three with a position/total counter.
- Selection clamps at both ends; scan restart resets selection. Empty/error
  screens remain informational and cannot select nonexistent devices.
- Terminal input now decodes ANSI and application-mode arrow sequences, including
  split reads, while retaining queued keys. No pairing/connect action added.
- Thirteen tests pass, including split arrow decoding, navigation boundaries and
  rendering beyond the first page. Native SSH/display verification pending.

## Bluetooth activity monitor — 2026-11-08

- Bluetooth menu now includes live agent task/status from agent-state.json and
  two timestamped runtime events: idle, scan start, scan completion or failure.
- Device list displays two selectable devices per page to reserve monitor space;
  all observed devices remain accessible using Up/Down.
- Fourteen tests pass, including monitor rendering and asynchronous scan events;
  Bluetooth monitor preview generated successfully without hardware.
- ESP32 connection, encrypted communication and service use remain unimplemented;
  monitor does not claim these operations have occurred. Native review pending.

## ESP32 BLE client — 2026-11-08

- Added C action to connect to the selected observed device using Bleak, inspect
  GATT, and verify user-provided service 4fafc201-1fb5-459e-8fcc-c5c9c331914b.
- Optional --ble-pair requests pairing; --ble-read UUID reads only an explicitly
  configured readable characteristic within that service. Default is inspection.
- Background activity monitor tracks real connection/discovery/read/disconnect
  stages. Project-local atomic ble-report.json records service metadata and read
  byte counts without storing characteristic values. Pairing is not labeled as
  proof of link encryption. Added bleak dependency and host setup instructions.
- Seventeen tests pass, including mocked discovery, explicit read, wrong service,
  wrong characteristic and disconnect on failure. No BLE hardware used here.
- Pending: user must install updated requirements/run native session and identify
  the ESP32 and read characteristic/authentication protocol. Encrypted service
  access has NOT occurred; application encryption support awaits protocol details.

## BLE D-Bus diagnostics — 2026-11-08

- User reported BleakDBusError; previous exception-type-only reporting hid the
  actual BlueZ failure. Root cause cannot be inferred from that class name.
- Added bounded, control-character-cleaned exception message and D-Bus name/details
  to ble-report.json and SSH stderr; monitor shows the short D-Bus reason.
- Nineteen tests pass, including diagnostic formatting and failed-session report.
- Pending: restart native dashboard, retry selected ESP32 and inspect error fields
  to identify actual pairing/connection failure. No system changes made.

## Bluetooth name resolution — 2026-11-08

- User identified ESP32 address 80:B5:4E:E8:B4:69; laptop shows its configured
  name while dashboard can show only address. Pi hardware output not inspected.
- Fixed scan parser dropping Name/Alias updates received before RSSI. Missing
  scan names now fall back to host bluetoothctl devices cache (two-second limit).
- Cached devices are not added unless observed during the current scan. Failed
  name lookup preserves discoveries and displays Name unavailable.
- Twenty-one tests pass, including event ordering, cached-name resolution,
  excluding unobserved cached devices and lookup timeout recovery.

## Short unnamed-device label — 2026-11-08

- Changed missing Bluetooth device-name fallback from Name unavailable to Unknown.
  Address remains visible for identification. Updated README and existing check.
- Seven Bluetooth menu tests pass.

## Autonomous BLE probing — 2026-11-08

- User authorized independent investigation with minimal ESP32 information.
- For AuthenticationFailed during requested pairing, client now makes exactly
  one fallback connection without explicitly requesting pairing. Both attempts
  are retained in report; no passkeys guessed or stored bonds removed.
- Once target service is found, automatically probe up to sixteen readable
  characteristics (five seconds each); save per-read byte counts/errors alongside
  service metadata. Explicit --ble-read still selects a single characteristic.
- Session cap increased to 100 seconds. Twenty-four tests pass, including auth
  fallback, no retry for unrelated errors and metadata retention on rejected read.
- No container access to BLE hardware. Next native C action executes this probe;
  actual encrypted access remains unverified. No undocumented writes performed.

## Headless ESP32 pairing and information access — 2026-11-08

- Investigated shared report: pairing AuthenticationFailed, normal connection and
  service enumeration succeed, target read times out at previous five-second cap.
- Added temporary NoInputNoOutput BlueZ agent scoped to the exact selected device.
  Pair is called on the same D-Bus connection as agent registration; default agent
  is not replaced. Unknown PIN/passkey or numeric confirmation requests are
  reported/rejected. Agent unregister/bus cleanup runs on success or failure.
- Increased per-read timeout to twenty seconds and total session cap to 150.
  Capture up to 256 bytes per successful read as hex/valid UTF-8 plus total count.
  Pairing/read success still does not claim verified link encryption.
- Added native standalone ble_client.py --pair entry point with confirmed ESP32
  address default; publishes current operation to agent-state.json for live monitor
  display without restarting dashboard. Do not overlap with dashboard BLE jobs.
- Explicit dbus-fast Linux dependency; container package installation unavailable.
  Twenty-eight tests pass, with mocked agent registration, target scoping, unknown
  passkey rejection, cleanup, error normalization and response truncation. CLI
  help runs. Real dbus-fast integration and ESP32 hardware execution are pending.
- No host services, networking, power, firmware or existing bonds changed. Original
  hardware report preserved; new pairing/read strategy remains unverified on Pi.

## Expanded Bluetooth-only terminal — 2026-11-08

- Added dashboard-style top bar titled Bluetooth Menu with independent Bluetooth
  operation status. Display now shows one selected device and Up/Down position.
- Expanded BT TERMINAL to six wrapped feedback lines (20 retained timestamped
  events). General agent task/status removed from this panel.
- Added atomic bluetooth-activity.json feed for dashboard BLE operations and
  standalone probe progress, polled at 0.5-second intervals. Missing/corrupt feed
  falls back to local Bluetooth state. No runtime activity fabricated.
- Thirty-one tests pass, covering shared-feed recovery/history/status, single-device
  rendering, title/status and wrapped feedback. Layout preview visually inspected
  at 320x240. Native screen verification pending; dashboard restart required.

## BLE control-read and connection diagnostics — 2026-11-08

- Added standard Generic Access Device Name control read before target probing,
  with separate response/error and a twenty-second cap. Missing readable control
  is explicitly skipped. Target reads still restricted to the configured service.
- Read-only BlueZ snapshots record Paired/Bonded/Connected/ServicesResolved where
  available, around reads. Missing properties or unavailable D-Bus remain unknown.
- Disconnect callback records active phase and intentional cleanup flag; read
  results include connected flags, elapsed durations and operation offsets from
  a UTC session start, allowing correlation with separately captured serial logs.
- Added cautious diagnostic assessments for control-only success, both-read failure,
  successful target access, and dropped connection. No encryption proof claimed.
- Atomic checkpoints preserve intermediate evidence through outer timeout/errors;
  target probing stops after a read error or observed connection loss. Attempt
  outcome now distinguishes completed_with_read_errors from completed.
- Thirty-seven hardware-free tests pass, including control success/target timeout,
  both-read failure, disconnect during read, unavailable state, skipped target
  after control disconnect and partial-report retention on session timeout.
- Native retry is still required; existing hardware report was not overwritten.
  No serial logs or physical security/connection state have been verified here.

## Project organization — 2026-11-08

- Grouped Bluetooth code as bt.client, bt.pairing, bt.menu and bt.activity;
  moved face/keyboard/shared drawing controls under ui/.
- Moved all seven test modules into test/, hardware diagnostic commands into
  tools/, and existing PNG artifacts into previews/. Added package initializers.
- Updated imports, mock targets, project-root path resolution and README commands.
  Keep dashboard.py and agent_status.py as stable root entry points; live JSON
  producer/consumer paths intentionally remain at the root.
- New BLE command: .venv/bin/python -m bt.client --pair. Test command:
  .venv/bin/python -m unittest discover -s test -v.
- All 37 tests pass. BLE CLI help, dashboard/face/Bluetooth previews and standalone
  display-test preview run successfully after reorganization. Native hardware
  not tested; restart the dashboard to load the new package imports.

## Documentation and reports directories — 2026-11-08

- Moved all root Markdown files (AGENTS.md, README.md, PROGRESS.md) into codex/.
  Updated instruction paths and README layout/run documentation.
- Moved existing BLE report into reports/ble-report.json. Dashboard and standalone
  client now share a REPORT_PATH constant; atomic report writer creates parent
  directories as needed. Updated on-screen report references.
- agent-state.json and bluetooth-activity.json remain runtime feeds at root.
- All 37 tests pass and BLE CLI help runs. Native dashboard restart required so
  existing processes use the updated report location. Hardware not tested.

## Target-read timeout investigation — 2026-11-08

- Latest native report confirms Paired/Bonded/Connected/ServicesResolved true;
  Device Name read succeeds as ESP32-S3-Test in 122ms. Target characteristic
  beb5483e-36e1-4688-b7f5-ea07361b26a8 times out after 20052ms while connected.
  The only recorded disconnect is intentional cleanup. No target data received.
- Added bounded thread-scoped Bleak BlueZ read trace counters to each read result:
  InProgress retries versus logged completions, plus cautious timeout evidence.
  Monitor distinguishes BlueZ busy from waiting without logged read completion.
- Trace records no payloads and restores logger configuration on success/failure;
  this does not replace ATT packet capture or prove a specific firmware cause.
- Forty hardware-free tests pass, including busy-timeout integration, unrelated
  thread filtering, no payload logging and logger cleanup on exception.
- Next native run supplies transport evidence. ESP32 firmware/serial/ATT evidence
  may still be needed to resolve target behavior; encryption remains unverified.

## Native btmon capture preparation — 2026-11-08

- Confirmed container has no btmon executable or host system D-Bus socket; no
  Bluetooth packet capture was performed here.
- Added tools.capture_ble: native btmon recording around one paired target-only
  ESP32 read, with bounded process lifetime and cleanup, no sudo/system changes.
  Capture/logs/fresh-report copy go into a unique directory under reports/.
- Added --target-only client mode to skip the Device Name control read during the
  fresh-target experiment. No change to dashboard default diagnostics.
- Forty-four tests pass, including target-only behavior, missing btmon, early
  monitor failure preventing probe and owned monitor cleanup. CLI help runs.
- Pending: native .venv/bin/python -m tools.capture_ble and inspect resulting ATT
  trace; monitor permissions may need host-side setup outside this container.

## Development backlog and final container plan — 2026-11-08

- Added codex/TODO.md with actionable ESP32 diagnostics, service access, reload,
  BLE lifecycle, physical validation and maintenance work; linked it from README.
- Recorded user's intended final container access to SPI, GPIO, btmon/Bluetooth
  tooling and additional tools introduced during development. Listed device,
  D-Bus, dependency, permission and hardware-verification requirements separately
  from current container capabilities; existing SSH/system restrictions preserved.
- Documentation-only change; no runtime code, host setup or hardware changes.

## Documented next captured service attempt — 2026-11-08

- Updated codex/TODO.md with completed client/capture preparation and the exact
  native command for btmon plus a paired target-only probe in one run.
- Documented prerequisites, output artifacts and interpretation; physical capture
  and service data retrieval remain unchecked. No new hardware attempt performed.
- Documentation-only change; verified procedure against current helper/client code.

## Concerned face and Bluetooth quit cleanup — 2026-11-08

- Found agent-state.json and Bluetooth feed owned by a different mapped user with
  mode 0600; state read returned Permission denied in this environment. Such state
  diagnostics trigger concerned face. Existing unreadable agent state preserved
  under reports/; publisher now writes status files as 0644 for shared reading.
- Refreshed state reads without errors; local metrics sample also reports none.
  Renderer returns thinking for real working status rather than concerned.
- Dashboard ExitStack now runs Bluetooth close on Q, Ctrl-C or exceptions. Close
  prevents new jobs, signals cancellation, waits for async context cleanup, and
  sends bounded bluetoothctl disconnect only for this dashboard's target.
- Pairing cancellation requests CancelPairing/Disconnect before agent teardown.
  Run-session cancellation preserves available report evidence. Cleanup failures
  remain visible; no global device disconnect or external process termination.
- Fifty tests pass, including cancel-during-read with awaited context cleanup,
  owned-target-only disconnect, failure feedback, shutdown idempotence and status
  permissions/unreadable-state preservation. Native shutdown verification pending.

## Capture access diagnosis — 2026-11-08

- Readable capture reports/ble-20261108T224058Z-we1eu7qz/btmon.log contains
  Failed to bind channel: Operation not permitted; no usable packet evidence
  established from that attempt.
- Newer reports/ble-20261108T224324Z-ckh8cjzw directory is owned by a different
  mapped user with mode 0700 and cannot be inspected from this container.
- Latest client report still shows successful paired/bonded control read and
  connected target timeout with 946 InProgress retries. It is not a packet trace.
- Future capture directories now use 0755; completed artifacts and atomic BLE
  reports use 0644 so native/container users can share diagnostic evidence.
- Fifty-one tests pass, including report/capture permission checks. Existing newer
  capture needs native chmod before inspection. No host monitor privilege changes.

## Actual btmon capture analysis — 2026-11-08

- Read newest accessible capture reports/ble-20261108T224910Z-qcjrwxdq/.
- HCI event #30 at 3.029863s, connection handle 64 for the confirmed ESP32, reports
  Success and Encryption Enabled with AES-CCM. Link encryption is verified for
  this captured connection, though client JSON independently says unverified.
- Complete decoded capture has zero ATT Read Request (0x0a)/Read Response (0x0b)
  packets. Discovery and configuration transactions respond; target-only client
  times out with 1,755 BlueZ InProgress retries before intentional disconnect.
- No target data retrieved. Evidence points to a read pending/busy in BlueZ with
  no transmitted target read observed; root cause is not established. Next compare
  an independent native GATT client and inspect BlueZ request state.
- Saved sanitized summary reports/ble-20261108T224910Z-analysis.json. Original
  capture/report preserved; source directory is readable but not writable here.

## Container Bluetooth access TODO — 2026-11-08

- Recorded current absence of bluetoothctl, btmon and host system D-Bus socket in
  codex/TODO.md. Added explicit access-verification and independent-client read
  comparison tasks. Documentation only; no container/host configuration changed.
