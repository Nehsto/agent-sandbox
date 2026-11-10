"""Finite ILI9341 color test; no desktop or root required."""

import argparse
from pathlib import Path
import sys
import time
import traceback

from PIL import Image, ImageDraw, ImageFont


def test_pattern():
    image = Image.new("RGB", (240, 320), "black")
    draw = ImageDraw.Draw(image)
    draw.text((16, 16), "ILI9341 / Raspberry Pi", fill="white")
    draw.text((16, 38), "240 x 320 | SPI0 CE0", fill="white")
    for index, color in enumerate(("red", "lime", "blue", "white")):
        draw.rectangle((16, 70 + index * 42, 223, 109 + index * 42), fill=color)
    draw.text((16, 254), "DC:25  RESET:24  CS:8", fill="white")
    draw.text((16, 276), "LED: physical pin 17", fill="white")
    draw.rectangle((0, 0, 239, 319), outline="white")
    return image


def orientation_pattern(number, angle, frame=0, fps=None):
    size = (320, 240) if angle in (90, 270) else (240, 320)
    image = Image.new("RGB", size, "#101828")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=52)
    draw.rectangle((0, 0, size[0]-1, size[1]-1), outline="white", width=2)
    draw.text((8, 6), "TOP ^   LEFT", fill="yellow")
    draw.text((16, 36), str(number), font=font, fill="white")
    draw.text((16, 100), f"ROTATION {angle} degrees", fill="cyan")
    draw.text((16, 122), f"{size[0]} x {size[1]} | frame {frame}", fill="white")
    if fps is not None:
        draw.text((16, 144), f"Full-frame: {fps:.1f} FPS", fill="lime")
    x = 8 + (frame * 9) % (size[0] - 36)
    draw.rectangle((x, 174, x+20, 194), fill="magenta")
    draw.text((8, size[1]-22), "BOTTOM            RIGHT >", fill="yellow")
    # Driver framebuffer remains native 240x320; rotate logical canvas to fit.
    return image.rotate(angle, expand=True)


def run_benchmark(display, number, angle, seconds, target_fps=30):
    started = time.perf_counter()
    frames = 0
    while time.perf_counter() - started < seconds:
        elapsed = time.perf_counter() - started
        image = orientation_pattern(number, angle, frames,
                                    frames / elapsed if frames else 0)
        display.image(image)
        frames += 1
        if target_fps:
            # Pace each completed frame without catching up in bursts.
            delay = 1 / target_fps - (time.perf_counter() - started - elapsed)
            if delay > 0:
                time.sleep(delay)
    elapsed = time.perf_counter() - started
    fps = frames / elapsed
    print(f"Orientation {number} ({angle} deg): {frames} frames / "
          f"{elapsed:.2f}s = {fps:.2f} FPS (render + convert + SPI + pacing)", flush=True)
    display.image(orientation_pattern(number, angle, frames, fps))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, help="Save PNG without accessing GPIO")
    parser.add_argument("--debug", action="store_true", help="Show full hardware error traceback")
    parser.add_argument("--baudrate", type=int, default=32_000_000,
                        help="Requested SPI Hz (default 32000000)")
    parser.add_argument("--fps-seconds", type=float, default=5,
                        help="Benchmark duration per orientation (default 5)")
    parser.add_argument("--orientation", type=int, choices=(1, 2, 3, 4), default=2,
                        help="Numbered orientation (default 2, landscape)")
    parser.add_argument("--all-orientations", action="store_true")
    parser.add_argument("--target-fps", type=float, default=30,
                        help="Frame rate cap; 0 means unlimited (default 30)")
    parser.add_argument("--static", action="store_true",
                        help="Show orientation without animation")
    args = parser.parse_args()
    if not 0 <= args.target_fps <= 240:
        parser.error("target-fps must be between 0 and 240")
    if args.baudrate <= 0 or not 0 < args.fps_seconds <= 60:
        parser.error("baudrate must be positive; fps-seconds must be >0 and <=60")
    def report(message):
        if args.debug:
            print(message, flush=True)

    report("Starting display test: SPI0 CE0; DC GPIO25/pin22; RESET GPIO24/pin18")
    pattern = test_pattern()
    if args.preview:
        pattern.save(args.preview)
        print(f"Saved {args.preview}")
        return 0
    if not Path("/dev/spidev0.0").exists():
        print("Display test blocked: /dev/spidev0.0 is unavailable. "
              "Check SPI configuration and device visibility on the host.", file=sys.stderr)
        return 1
    stage = "loading display libraries"
    report(stage)
    try:
        import board
        import digitalio
        if digitalio.Pin is None:
            raise RuntimeError(
                'Blinka GPIO backend is unset. On this Raspberry Pi 4B, rerun with '
                'BLINKA_FORCEBOARD=RASPBERRY_PI_4B BLINKA_FORCECHIP=BCM2XXX '
                'before the Python command.'
            )
        from adafruit_rgb_display import ili9341

        from contextlib import ExitStack
        with ExitStack() as stack:
            # Linux SPI0 controls hardware CE0 (GPIO8 / physical pin 24).
            # Requesting it through libgpiod conflicts with the kernel driver.
            stage = "claiming DC GPIO25"
            report(stage)
            dc = stack.enter_context(digitalio.DigitalInOut(board.D25))
            stage = "claiming RESET GPIO24"
            report(stage)
            reset = stack.enter_context(digitalio.DigitalInOut(board.D24))
            stage = "opening SPI0"
            report(stage)
            spi = stack.enter_context(board.SPI())
            stage = "initializing ILI9341"
            report(stage)
            display = ili9341.ILI9341(
                spi, cs=None, dc=dc, rst=reset, baudrate=args.baudrate,
                width=240, height=320, rotation=0,
            )
            print(f"Requested SPI: {args.baudrate:,} Hz; actual clock may be rounded/clamped."
                  " Check visually for corruption.", flush=True)
            numbers = (1, 2, 3, 4) if args.all_orientations else (args.orientation,)
            for number in numbers:
                angle = (number - 1) * 90
                stage = f"testing orientation {number} ({angle} degrees)"
                print(stage, flush=True)
                display.image(orientation_pattern(number, angle))
                time.sleep(3)
                if not args.static:
                    run_benchmark(display, number, angle, args.fps_seconds, args.target_fps)
                time.sleep(3)
            print("Done. Report the upright orientation number and any corruption.", flush=True)
        return 0
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        print(f"Display test failed while {stage}: {error}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
