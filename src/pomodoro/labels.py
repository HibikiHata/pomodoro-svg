"""位相の名前。

文言を定数として1か所に置く理由は2つ。多言語を後付けにしないことと、
フォントのサブセットをここから機械的に集めて、手で書き写す余地を無くすこと。

**文言を足したらサブセットを作り直すこと。** 足し忘れても描画前に不足として
落ちるので豆腐は出ないが、落ちてから気づくことになる。
"""
from __future__ import annotations

from pomodoro.schedule import LONG_REST, REST, WORK

#: 周期が終わった状態。位相ではないが、ラベルとしては同じ扱いをする
DONE = "done"

KINDS: tuple[str, ...] = (WORK, REST, LONG_REST, DONE)
#: **英語のみを出す（オーナー判断 2026-08-03）。** 仕組みは残してある——
#: 日本語を足すのは `LABELS` と `UNITS` に辞書を1つ増やし、`gen_font_subset` の
#: 対象ロケールを変えてサブセットを作り直すだけ。多言語を後付けにしない、という
#: 要件（R10）はこの形で満たしている
LOCALES: tuple[str, ...] = ("en",)

#: **長い休憩も BREAK と呼ぶ。** 長さは `ring` の2行目（`15 MIN`）と、数字を
#: 持つデザインの残り時間が示すので、語を分けなくても読める。語を分けると同じ
#: 状態に2つの見た目を与えることになり、フォントにも `L O N G` と空白が増える。
LABELS: dict[str, dict[str, str]] = {
    "en": {WORK: "FOCUS", REST: "BREAK", LONG_REST: "BREAK", DONE: "DONE"},
}


#: `ring` の2行目に出る時間の単位。元の `pomodoro.svg` の「25 MIN」を踏襲する
UNITS: dict[str, str] = {"en": " MIN"}


def unit(locale: str) -> str:
    if locale not in UNITS:
        raise ValueError(f"未知のロケールです: {locale!r}（{'/'.join(LOCALES)}）")
    return UNITS[locale]


def groups(locale: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """(表示する語, その語を出す位相の集合)。決定的な順序。

    語をまとめた結果、休憩と長い休憩が同じ1つの `<text>` になる。まとめずに
    2枚重ねると、同じ字が二重に描かれてにじむ。
    """
    ordered: dict[str, list[str]] = {}
    for kind in KINDS:
        ordered.setdefault(LABELS[locale][kind], []).append(kind)
    return tuple((text, tuple(kinds)) for text, kinds in ordered.items())


def label(locale: str, kind: str) -> str:
    if locale not in LABELS:
        raise ValueError(f"未知のロケールです: {locale!r}（{'/'.join(LOCALES)}）")
    if kind not in LABELS[locale]:
        raise ValueError(f"未知の位相です: {kind!r}（{'/'.join(KINDS)}）")
    return LABELS[locale][kind]
