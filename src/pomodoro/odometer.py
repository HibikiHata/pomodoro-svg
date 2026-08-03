"""数字の帯と、その移動量。

CSSは文字列を計算できない。「24:59」を出すには、数字をあらかじめ描いておいて
動かすしかない。縦に積んだ帯を1セル分ずつ跳ばし、1セル高の窓で切る——跳ばす
のは `steps()`、切るのは `<clipPath>` で、どちらもGitHub上で動くことを実測済み。

1秒ごとに1要素を並べる素朴な方法なら1周期で数千要素になるが、桁ごとの帯に
すれば10要素で足りる。
"""
from __future__ import annotations

from pomodoro.numbers import format_number

DIGITS = "0123456789"


def strip(count: int, cell: float, x: float, baseline: float) -> str:
    """0から始まる `count` 個の数字を縦に積んだ帯を返す。

    `baseline` は先頭（0）のベースライン。以降は `cell` ずつ下へ置く。
    """
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError(f"桁数は整数である必要があります: {count!r}")
    if not 1 <= count <= len(DIGITS):
        raise ValueError(f"桁数は1〜{len(DIGITS)}である必要があります: {count}")
    if cell <= 0:
        raise ValueError(f"セルの高さは正である必要があります: {cell}")

    return "".join(
        f'<text x="{format_number(x)}" '
        f'y="{format_number(baseline + index * cell)}">{DIGITS[index]}</text>'
        for index in range(count)
    )


def cell_offset(digit: int, cell: float) -> float:
    """`digit` を窓に出すための帯の移動量。

    窓は固定で帯のほうが上へ動くので符号は負。`strip` の `baseline + digit*cell`
    をちょうど打ち消す値になっている。
    """
    return -digit * cell
