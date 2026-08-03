"""タイムラインをCSSのキーフレームへ落とす。

トラックは4種類。リングだけが位相の中で連続的に変化し、残りは停止点で値が
切り替わるだけなので `step-end` で保持させる。`step-end` は補間しないため、
桁の途中の値という存在しない状態を描かずに済む。

**リングだけは刻みが要る。** 位相の終わりで空になり、次の位相の頭で満ちる。
CSSは同じ位置に2つの値を置けないので、終わりを `EPSILON` だけ手前に置く。
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from pomodoro.numbers import format_number, format_percent
from pomodoro.odometer import cell_offset
from pomodoro.labels import DONE
from pomodoro.schedule import LONG_REST, REST, Phase, total_seconds
from pomodoro.timeline import (
    SECOND_ONES_PERIOD,
    SECOND_TENS_PERIOD,
    minute_stops,
    phase_stops,
    second_digits,
)

# リングを巻き戻すのに使う幅（周期に対する百分率）。7800秒の周期で78ミリ秒。
# `format_percent` の分解能（1e-5%）の100倍あり、丸めで停止点が重ならない。
EPSILON = 0.001

TENS, ONES = 0, 1


@dataclass(frozen=True)
class Track:
    """1本の `@keyframes`。

    `duration` は秒。`stops` は (周期に対する百分率, CSS宣言) の昇順。
    """

    name: str
    timing: str
    duration: int
    stops: tuple[tuple[float, str], ...]
    #: 負の遅延。「すでにこれだけ再生済み」として描き始める。装飾の位相を
    #: ずらすのに使う——乱数を使わずに散らせる
    delay: float = 0.0
    #: 付ける先のCSSクラス。空なら `name` と同じ。**1つの要素に2つ以上の
    #: アニメーションを載せるときは、同じクラスにまとめる必要がある**——
    #: `animation` は加算されず、後の宣言が前を丸ごと置き換えるため
    group: str = ""

    @property
    def target(self) -> str:
        return self.group or self.name

    def to_css(self) -> str:
        body = "".join(
            f"{format_percent(position)}%{{{declaration}}}"
            for position, declaration in self.stops
        )
        return f"@keyframes {self.name}{{{body}}}"


def _checked(name: str, timing: str, duration: int,
             stops: list[tuple[float, str]]) -> Track:
    """停止点が昇順で、整形しても別々の位置に残ることを確かめてから包む。

    同じ位置に落ちた停止点は例外を出さず**黙って片方が消える**。判定を浮動小数の
    間隔ではなく整形後の文字列で行うのは、消えるかどうかを決めるのが文字列だから。
    間隔で見ると、ちょうど `EPSILON` 離れた正当な組を丸め誤差で弾いてしまう。
    """
    for (before, _), (after, _) in zip(stops, stops[1:]):
        if after < before:
            raise ValueError(f"{name}: 停止点が昇順ではありません（{before} → {after}）")
        if format_percent(before) == format_percent(after):
            raise ValueError(
                f"{name}: 停止点が同じ位置に丸められます（{before} と {after}）。"
                "位相が短すぎるか、周期が長すぎます"
            )
    return Track(name, timing, duration, tuple(stops))


def ring_track(phases: tuple[Phase, ...], circumference: float,
               name: str = "ring") -> Track:
    """位相ごとに満ちて減るリング。

    周期全体で1回だけ減らす作りにすると、休憩に入ってもリングが減り続ける。
    位相の切り替わりで巻き戻すこと自体が仕様。
    """
    if circumference <= 0:
        raise ValueError(f"円周は正である必要があります: {circumference}")

    total = total_seconds(phases)
    full = "stroke-dashoffset:0"
    empty = f"stroke-dashoffset:{format_number(circumference)}"

    stops: list[tuple[float, str]] = []
    elapsed = 0
    for index, phase in enumerate(phases):
        stops.append((100.0 * elapsed / total, full))
        elapsed += phase.seconds
        final = index == len(phases) - 1
        # 最後の位相の終わりは100%そのもの。折り返しは瞬時なので刻みは要らない
        stops.append((100.0 if final else 100.0 * elapsed / total - EPSILON, empty))
    return _checked(name, "linear", total, stops)


def _declaration(digit: int, cell: float) -> str:
    return f"transform:translateY({format_number(cell_offset(digit, cell))}px)"


def _digit_track(name: str, duration: int, samples: list[tuple[int, int]],
                 cell: float, terminal: int) -> Track:
    """(時刻, 数字) の列を、値が変わったところだけの停止点にする。

    100%に `terminal` の値を必ず置く。ループなら折り返し先（t=0）の値、1回きり
    なら 0。ここを置かないと、`forwards` で止めたとき最後の停止点の値——つまり
    「00:01」のような半端な状態——で固まる。
    """
    stops: list[tuple[float, str]] = []
    previous: str | None = None
    for at_second, digit in samples:
        declaration = _declaration(digit, cell)
        if declaration == previous:
            continue
        stops.append((100.0 * at_second / duration, declaration))
        previous = declaration

    closing = _declaration(terminal, cell)
    if previous != closing:
        stops.append((100.0, closing))
    return _checked(name, "step-end", duration, stops)


def minute_track(phases: tuple[Phase, ...], cell: float, column: int,
                 repeat: str = "loop", name: str | None = None) -> Track:
    """分の桁。位相ごとに巻き戻るので周期ぶんを列挙する。"""
    def split(minutes: int) -> int:
        return minutes // 10 if column == TENS else minutes % 10

    samples = [(at_second, split(minutes)) for at_second, minutes in minute_stops(phases)]
    terminal = 0 if repeat == "once" else split(phases[0].seconds // 60)
    return _digit_track(
        name or f"m{column}", total_seconds(phases), samples, cell, terminal
    )


def second_track(cell: float, column: int, repeat: str = "loop",
                 name: str | None = None) -> Track:
    """秒の桁。**位相を引数に取らない**。

    全位相が分単位なので、どの位相の残り秒も60を法として同じ動きになる。
    十の位は60秒、一の位は10秒で一周する短いループに畳める。
    """
    period = SECOND_TENS_PERIOD if column == TENS else SECOND_ONES_PERIOD
    samples = [(t, second_digits(t)[column]) for t in range(period)]
    # 位相の頭も周期の頭も秒は00なので、ループでも1回きりでも終端は0で正しい
    return _digit_track(name or f"s{column}", period, samples, cell, 0)


def dot_track(phases: tuple[Phase, ...], index: int, dim: float = 0.25,
              name: str | None = None) -> Track:
    """セットの進み具合を示す点。作業を終えた時点で満ちる。

    休憩の頭で満ちるのは、満ちる瞬間が「1本終えた」ときであってほしいため。
    次の作業が始まってから満ちるのでは、ご褒美が一拍遅れる。
    """
    total = total_seconds(phases)
    stops: list[tuple[float, str]] = [(0.0, f"opacity:{format_number(dim)}")]
    for start, phase in phase_stops(phases):
        if phase.index == index and phase.kind in (REST, LONG_REST):
            stops.append((100.0 * start / total, "opacity:1"))
            break
    return _checked(name or f"d{index}", "step-end", total, stops)


def phase_track(phases: tuple[Phase, ...], values: dict[str, str],
                name: str) -> Track:
    """位相ごとに切り替わる任意の宣言。リングの色付けに使う。

    色で位相が分かると、ラベルを読まなくても作業中か休憩中かが分かる。テーマの
    work/rest/long_rest が非文字の3:1を満たすよう固定してあるのはこのため。
    """
    total = total_seconds(phases)
    stops: list[tuple[float, str]] = []
    previous: str | None = None
    for start, phase in phase_stops(phases):
        declaration = values[phase.kind]
        if declaration == previous:
            continue
        stops.append((100.0 * start / total, declaration))
        previous = declaration
    # **折り返し用の終端は置かない。** ループなら100%と0%は同じ瞬間なので不要で、
    # 1回きりなら `forwards` が最後の姿を保つ——そこに先頭の色を置くと、
    # 終わったタイマーが作業中の色で固まる
    return _checked(name, "step-end", total, stops)


def label_track(phases: tuple[Phase, ...], kinds: tuple[str, ...],
                repeat: str = "loop", name: str | None = None) -> Track:
    """位相の名前の出し分け。どの時刻でもちょうど1つだけが見えている。

    `done` は位相ではなく「周期が終わった」状態で、1回きりのときだけ最後に出る。
    これが無いと、止まったタイマーが「長い休憩」と表示したまま固まる——休憩中
    なのか終わったのか読めない。ループでは100%と0%が同じ瞬間なので出番はない。
    """
    total = total_seconds(phases)
    finished = DONE in kinds
    stops: list[tuple[float, str]] = []
    previous: str | None = None
    for start, phase in phase_stops(phases):
        declaration = "opacity:1" if (not finished and phase.kind in kinds) else "opacity:0"
        if declaration == previous:
            continue
        stops.append((100.0 * start / total, declaration))
        previous = declaration
    if repeat == "once":
        closing = "opacity:1" if finished else "opacity:0"
        if previous != closing:
            stops.append((100.0, closing))
    return _checked(name or f"l-{kinds[0]}", "step-end", total, stops)


def linear_track(name: str, duration: int, declarations: tuple[str, str],
                 delay: float = 0.0) -> Track:
    """0%から100%へ一直線に動くだけのトラック。装飾に使う。

    位相にも時刻にも関係しない——マトリックスの降る数字のような、意味を持たない
    動きのためのもの。意味のある動きと同じ仕組みで扱えるようにしておくと、
    CSSの組み立てが1本道になる。
    """
    track = _checked(name, "linear", duration,
                     [(0.0, declarations[0]), (100.0, declarations[1])])
    return replace(track, delay=delay)
