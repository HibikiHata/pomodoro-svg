"""1周期の組み立て。

作業と休憩の並びと、長い休憩がどこに入るかだけを決める。時刻の計算も描画も
持たない——ここが小さく保たれている限り、タイムライン側は「位相の列」という
1つの形だけを相手にすればよい。

**各位相は分単位の整数でなければならない。** 秒の桁を「位相に依存しない60秒
ループ」1本で描けるのはこの前提のおかげで、端数を許すと位相の変わり目で秒が
ずれ、位相ごとに秒の帯を描き直す羽目になる。
"""
from __future__ import annotations

from dataclasses import dataclass

WORK = "work"
REST = "rest"
LONG_REST = "long_rest"


@dataclass(frozen=True)
class Phase:
    """1つの位相。`index` は所属するセット番号（0始まり）。

    作業とその直後の休憩は同じセットに属する。セット表示のドットを塗る単位が
    これなので、休憩を次のセットに数えると1つ手前で満ちてしまう。
    """

    kind: str
    seconds: int
    index: int


def _minutes(name: str, value: int, *, positive: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} は分単位の整数である必要があります: {value!r}")
    if positive and value <= 0:
        raise ValueError(f"{name} は正である必要があります: {value}")
    return value * 60


def cycle(work: int, rest: int, sets: int = 4, long_rest: int = 15) -> tuple[Phase, ...]:
    """1周期ぶんの位相の列を返す。

    `sets` が0のときは作業と休憩の対だけを返す。セットのドットも長い休憩も
    出さない設定なので、`long_rest` の値は使わず検証もしない。
    """
    work_seconds = _minutes("work", work)
    rest_seconds = _minutes("rest", rest)

    if isinstance(sets, bool) or not isinstance(sets, int) or sets < 0:
        raise ValueError(f"sets は0以上の整数である必要があります: {sets!r}")

    if sets == 0:
        return (Phase(WORK, work_seconds, 0), Phase(REST, rest_seconds, 0))

    long_seconds = _minutes("long_rest", long_rest)

    phases: list[Phase] = []
    for index in range(sets):
        phases.append(Phase(WORK, work_seconds, index))
        final = index == sets - 1
        phases.append(
            Phase(LONG_REST, long_seconds, index) if final
            else Phase(REST, rest_seconds, index)
        )
    return tuple(phases)


def total_seconds(phases: tuple[Phase, ...]) -> int:
    """1周期の長さ。ループ時のアニメーション周期そのもの。"""
    return sum(phase.seconds for phase in phases)
