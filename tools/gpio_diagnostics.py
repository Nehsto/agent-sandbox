"""Inspect GPIO chip metadata without requesting or changing any GPIO lines."""
from pathlib import Path
import gpiod


def main():
    print(f'gpiod version: {getattr(gpiod, "__version__", "unknown")}')
    paths = sorted(Path('/dev').glob('gpiochip*'))
    if not paths:
        print('No /dev/gpiochip* devices visible; run from the Pi host SSH shell.')
        return 1
    failed = False
    for path in paths:
        chip = None
        try:
            chip = gpiod.Chip(str(path))
            if hasattr(chip, 'get_info'):
                info = chip.get_info()
                label, count = info.label, info.num_lines
            else:
                label, count = chip.label, chip.num_lines
                label = label() if callable(label) else label
                count = count() if callable(count) else count
            print(f'{path}: label={label!r}, lines={count}')
        except (OSError, RuntimeError) as error:
            print(f'{path}: {type(error).__name__}: {error}')
            failed = True
        finally:
            if chip is not None:
                if hasattr(chip, 'close'):
                    chip.close()
                else:
                    chip.reset()
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
