"""SVGを書き出すコマンド。

    PYTHONPATH=src python3 -m pomodoro --out build --design odometer --work 50 --rest 10

`--design` ごとに light/dark の2枚を出す。貼る側は `<picture>` で出し分ける。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pomodoro.config import DESIGNS, MODES, REPEATS, Options
from pomodoro.labels import LOCALES
from pomodoro.render import variants
from pomodoro.theme import PALETTES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pomodoro", description="ポモドーロSVGを書き出す")
    parser.add_argument("--out", type=Path, default=Path("build"), help="出力先")
    parser.add_argument("--work", type=int, default=25, help="作業（分）")
    parser.add_argument("--rest", type=int, default=5, help="休憩（分）")
    parser.add_argument("--sets", type=int, default=4, help="セット数（0でセット無し）")
    parser.add_argument("--long-rest", type=int, default=15, help="長い休憩（分）")
    parser.add_argument("--repeat", choices=REPEATS, default="loop")
    parser.add_argument("--design", choices=DESIGNS, default="ring")
    parser.add_argument("--palette", choices=sorted(PALETTES), default="default")
    parser.add_argument("--locale", choices=LOCALES, default="en")
    parser.add_argument("--name", default=None,
                        help="ファイル名の幹（既定は設定から作る）")
    parser.add_argument("--freeze", type=float, default=None,
                        help="指定秒の状態で止めた静止画にする（確認用）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = Options(
        work=args.work, rest=args.rest, sets=args.sets, long_rest=args.long_rest,
        repeat=args.repeat, design=args.design, palette=args.palette,
        locale=args.locale,
    )
    stem = args.name or f"pomodoro-{options.slug}"
    args.out.mkdir(parents=True, exist_ok=True)
    for mode, data in variants(options, args.freeze).items():
        path = args.out / f"{stem}-{mode}.svg"
        path.write_bytes(data)
        print(f"{path} ({len(data):,}B)")
    assert set(variants(options, args.freeze)) == set(MODES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
