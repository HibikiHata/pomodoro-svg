"""時刻から表示値への写像。

`at()` は「読み込みから t 秒後に何が出ているべきか」の**独立した正解**を返す。
後段が生成するCSSはこれと突き合わせて検証する。生成物を眺めて「それらしい」と
判断するのではなく、意図した時刻に意図した値かを問えるようにするための分割で、
検証すべき区別を検査器側で潰さないための備えでもある。

表示の約束: 残り時間は秒単位で階段状に落ちる。位相の頭では満了時間がまるまる
1秒だけ出て（25:00）、その次から 24:59 になる。残り0は表示されない——0になる
瞬間には次の位相へ移っているため。
"""
from __future__ import annotations

import math

from pomodoro.schedule import Phase, total_seconds

# 秒の桁は位相に依存しない単純なループになる（全位相が分単位であるため）。
# 一の位は10秒、十の位は60秒で一周する。
SECOND_ONES_PERIOD = 10
SECOND_TENS_PERIOD = 60


def at(phases: tuple[Phase, ...], t: float) -> tuple[Phase, int]:
    """t秒後の位相と、そのとき表示される残り秒数を返す。

    `t` は周期で折り返す（ループ再生の意味論）。位相の境界はこれから始まる側に
    属する——ちょうど1500秒の時点では休憩が05:00で始まっている。
    """
    if t < 0:
        raise ValueError(f"時刻は0以上である必要があります: {t}")

    remaining = math.floor(t) % total_seconds(phases)
    for phase in phases:
        if remaining < phase.seconds:
            return phase, phase.seconds - remaining
        remaining -= phase.seconds
    raise AssertionError("周期で折り返した以上ここには到達しない")


def phase_stops(phases: tuple[Phase, ...]) -> tuple[tuple[int, Phase], ...]:
    """各位相の開始時刻（秒）。リングの巻き戻しとラベルの切り替え点になる。"""
    stops: list[tuple[int, Phase]] = []
    elapsed = 0
    for phase in phases:
        stops.append((elapsed, phase))
        elapsed += phase.seconds
    return tuple(stops)


def minute_stops(phases: tuple[Phase, ...]) -> tuple[tuple[int, int], ...]:
    """分の表示が変わる時刻と、そのときの分の値。

    秒の桁と違って分は位相ごとに巻き戻るので、周期ぶんを列挙するしかない。
    それでも1分に1つで済む——1秒に1つ並べれば1周期で数千個になる。

    位相の頭の値は1秒しか出ないことに注意（25:00 → 24:59）。だから2つ目の
    変化は60秒後ではなく1秒後に来る。
    """
    stops: list[tuple[int, int]] = []
    base = 0
    for phase in phases:
        minutes = phase.seconds // 60
        stops.append((base, minutes))
        for step in range(minutes):
            stops.append((base + 1 + 60 * step, minutes - 1 - step))
        base += phase.seconds
    return tuple(stops)


def second_digits(t: float) -> tuple[int, int]:
    """t秒後に表示される秒の (十の位, 一の位)。

    位相を参照しない。全位相が分単位なので、どの位相の残り秒も 60 を法として
    -t に合同になり、秒の桁は周期全体で1本のループに畳める。
    """
    return divmod((-math.floor(t)) % 60, 10)
