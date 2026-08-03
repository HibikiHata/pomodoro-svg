"""貼るだけで使える組み合わせを一括生成する。

    PYTHONPATH=src python3 -m pomodoro._generate.gen_variants --out dist

**この一覧が公開物の全部**。Actionを出さないので（設計文書 D4）、利用者が
自分で生成する経路は「cloneしてCLI」しかない。ここに無い組み合わせは、
Pythonを持っている人だけが作れる——だから何を入れるかは重い判断になる。

スケジュールは4種類。根拠は `docs/behaviour.md`——「最適な1つ」は存在せず、
作業の性質で変わるので、代表を並べる形にした。

**長い休憩はスケジュールごとに決める。** 既定の15分を90/20に引きずると、
「長い休憩」が短い休憩より短くなる。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pomodoro.config import DESIGNS, Options
from pomodoro.render import variants

#: (作業, 短休憩, 長休憩)。根拠は設計文書 §5
SCHEDULES: tuple[tuple[int, int, int], ...] = (
    (15, 5, 15),    # 注意の持続が難しいとき。ADHD適応の臨床試験が採った長さ
    (25, 5, 15),    # 正典。Cirillo の原典
    (50, 10, 20),   # 知識労働の実務帯。DeskTime の 52/17 を丸めたもの
    (90, 20, 30),   # 深い集中。ウルトラディアンとフロー研究が一致する帯
)


def build(out: Path) -> list[tuple[Path, int]]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[tuple[Path, int]] = []
    for design in DESIGNS:
        for work, rest, long_rest in SCHEDULES:
            options = Options(work=work, rest=rest, long_rest=long_rest,
                              design=design)
            for mode, data in variants(options).items():
                path = out / f"pomodoro-{options.slug}-{mode}.svg"
                path.write_bytes(data)
                written.append((path, len(data)))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="貼るだけ用の組み合わせを作る")
    parser.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)

    written = build(args.out)
    names = {path.name for path, _ in written}
    if len(names) != len(written):
        raise SystemExit(
            "ファイル名が衝突しています。slug が区別すべき軸を落としています"
        )
    total = sum(size for _, size in written)
    print(f"{len(written)}枚 / 合計 {total / 1024:.0f}KB / 平均 {total / len(written) / 1024:.1f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
