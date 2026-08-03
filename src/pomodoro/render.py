"""デザインを1枚のSVGに組み立てる。

読み込んだ瞬間が開始。だから静的な既定値は t=0 の姿——「25:00 / 集中」——に
しておく。アニメーションは通常の宣言より優先されるので上書きされるが、万一
アニメーションが動かない環境でも、意味のある1枚として読める。

light/dark は2枚に分ける。SVG内の `@media (prefers-color-scheme)` はGitHubの
テーマ切り替えではなくOSの設定に解決され、Safari では効かない。
"""
from __future__ import annotations

import math
import re

from pomodoro.charset import required_charset
from pomodoro.config import Options
from pomodoro.document import Svg
from pomodoro.fontembed import load_subset, missing_characters
from dataclasses import replace

from pomodoro.keyframes import (
    Track,
    dot_track,
    linear_track,
    label_track,
    minute_track,
    phase_track,
    ring_track,
    second_track,
)
from pomodoro.labels import DONE, groups, label, unit
from pomodoro.numbers import format_number
from pomodoro.odometer import cell_offset, strip
from pomodoro.schedule import LONG_REST, REST, WORK, cycle, total_seconds
from pomodoro.theme import Theme, theme_of

FONT = "noto-sans-jp"

#: (幅, 高さ)。デザインごとに形が違ってよい——リングは正方形、デジタルは横長
CANVAS: dict[str, tuple[int, int]] = {
    "ring": (200, 200),
    "odometer": (220, 220),
    "digital": (280, 110),
    "minimal": (200, 200),
    "matrix": (260, 170),
}

#: 数字の桁数。分は2桁で0〜9、秒の十の位だけ0〜5
COLUMN_DIGITS = {"m0": 10, "m1": 10, "s0": 6, "s1": 10}

#: 自前で板を敷くデザイン。全面の下地を張らない
OWN_BACKGROUND = frozenset({"digital"})

#: 端に寄せた要素が接触しないための余白
MARGIN = 8


def _iteration(track: Track, total: int, repeat: str) -> str:
    """`animation` の繰り返し指定。

    1回きりのときは、秒のように周期の短いトラックも周期の終わりで止める必要が
    ある。回数は周期に収まる整数回。
    """
    if repeat == "loop":
        return "infinite"
    return f"{max(1, total // track.duration)} forwards"


def _frozen(track: Track, at_second: float, repeat: str) -> str:
    """`at_second` 秒後にそのトラックが示している値を、静止した宣言として返す。

    休憩や完了の見た目を25分待たずに確かめるための道具。**トラックから導く**ので
    アニメーションと食い違いようがない——別に組み立てると、確認した絵と実際に
    動く絵が別物になる。

    `step-end` は直前の停止点を保持する。`linear`（リング・バー）だけは前後の
    停止点を補間する。
    """
    if repeat == "once" and at_second >= track.duration:
        held = track.stops[-1][1]                 # forwards で最後の姿のまま止まる
        return f".{track.target}{{{held}}}"

    percent = 100.0 * (at_second % track.duration) / track.duration
    before, after = track.stops[0], None
    for stop in track.stops:
        if stop[0] <= percent + 1e-9:
            before = stop
        else:
            after = stop
            break

    held = before[1]
    if track.timing == "linear" and after is not None:
        held = _interpolate(before, after, percent)
    return f".{track.target}{{{held}}}"


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _interpolate(before: tuple[float, str], after: tuple[float, str],
                 percent: float) -> str:
    """2つの宣言の間の値。

    数値を素直に取り出す。`stroke-dashoffset:603` も
    `transform:translateY(-135px)` も、**変わるのは数値ひとつだけ**という形を
    しているので、そこだけ差し替えれば足りる。形が違えば補間せず手前を保つ。
    """
    start, end = _NUMBER.findall(before[1]), _NUMBER.findall(after[1])
    shape_matches = _NUMBER.sub("#", before[1]) == _NUMBER.sub("#", after[1])
    if len(start) != 1 or len(end) != 1 or not shape_matches:
        return before[1]
    span = (percent - before[0]) / (after[0] - before[0])
    value = float(start[0]) + (float(end[0]) - float(start[0])) * span
    return _NUMBER.sub(lambda _: format_number(value), before[1], count=1)


def _shorthand(track: Track, total: int, repeat: str) -> str:
    delay = f" {format_number(track.delay)}s" if track.delay else ""
    return (f"{track.name} {track.duration}s {track.timing}{delay} "
            f"{_iteration(track, total, repeat)}")


def _animations(tracks: list[Track], total: int, repeat: str) -> list[str]:
    """要素ごとに `animation` を**1本にまとめる**。

    `.a{animation:x}` と `.b{animation:y}` を同じ要素に当てても2つは走らない——
    `animation` は加算されず、後の宣言が前を丸ごと置き換える。リングの減少が
    色の切り替えに打ち消されて**止まって見えていた**のがこれ。カンマ区切りの
    1つの宣言にすれば両方走る。
    """
    grouped: dict[str, list[Track]] = {}
    for track in tracks:
        grouped.setdefault(track.target, []).append(track)
    return [
        f".{target}{{animation:"
        + ",".join(_shorthand(track, total, repeat) for track in group) + "}"
        for target, group in grouped.items()
    ]


def _digit_columns(doc: Svg, tracks: list[Track], theme: Theme, options: Options,
                   subset, *, cx: float, baseline: float, size: float) -> list[str]:
    """MM:SS の一式を、フォントの実寸から組み立てて置く。

    桁の位置も窓の大きさもコロンの高さも、**生成時に測った送り幅と字面の中心**
    から出す。目分量のem比で決めると、フォントを差し替えたときに黙ってずれる。
    """
    width = size * subset.digit_advance          # 数字1桁の送り幅
    cell = size * 1.15                           # 帯の1段の高さ。字面より少し広い
    center = baseline - size * subset.digit_center

    columns = {
        "m0": cx - 1.75 * width,
        "m1": cx - 0.75 * width,
        "s0": cx + 0.75 * width,
        "s1": cx + 1.75 * width,
    }
    window = (cx - 2.3 * width, center - cell / 2, 4.6 * width, cell)

    doc.clip_rect("win", x=window[0], y=window[1], width=window[2], height=window[3])
    _colon(doc, theme, x=cx, center=center, size=size)

    # 帯の <text> は装飾属性を**一切**持たない（`strip` は幾何だけを扱う）。
    # 継承する3つを包むグループでまとめて指定する。**どれを忘れても静かに壊れる**——
    # fill なら暗色で沈み、font-size なら既定の16pxで描かれ、text-anchor なら
    # 左揃えになって右端の桁が窓からはみ出す。3つとも実際にやった。
    with doc.group(cls="d digits", clip="win"):
        for name, x in columns.items():
            with doc.group(cls=name):
                doc.raw(strip(COLUMN_DIGITS[name], cell, x, baseline))

    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    tracks.append(minute_track(phases, cell, 0, options.repeat))
    tracks.append(minute_track(phases, cell, 1, options.repeat))
    tracks.append(second_track(cell, 0, options.repeat))
    tracks.append(second_track(cell, 1, options.repeat))

    # 静的な既定値は t=0 の姿。アニメーションが動かなくても 25:00 が読める
    first = phases[0].seconds // 60
    statics = {"m0": first // 10, "m1": first % 10, "s0": 0, "s1": 0}
    return [
        f".digits{{fill:{theme.fg};font-size:{format_number(size)}px;"
        f"text-anchor:middle}}"
    ] + [
        f".{name}{{transform:translateY({format_number(cell_offset(digit, cell))}px)}}"
        for name, digit in statics.items()
    ]


def _hues(theme: Theme) -> dict[str, str]:
    """位相ごとのリングの色。**長い休憩は休憩と同じ。**"""
    return {WORK: f"stroke:{theme.work}", REST: f"stroke:{theme.rest}",
            LONG_REST: f"stroke:{theme.rest}"}


def _colon(doc: Svg, theme: Theme, *, x: float, center: float, size: float) -> None:
    """区切りを円2つで描く。**数字の字面の中心に合わせる。**

    フォントのコロンを使わないのは、CJKフォントでは字面の中心に寄っていて数字と
    揃わず、しかも揃い方がフォント次第で変わるため。図形なら決められる。
    """
    for offset in (-size * 0.11, size * 0.11):
        doc.circle(cx=x, cy=center + offset, r=size * 0.05, fill=theme.fg)


def _labels(doc: Svg, tracks: list[Track], theme: Theme, options: Options,
            *, x: float, y: float, size: float, anchor: str = "middle") -> None:
    """位相の名前を重ねて置き、1つだけを見せる。

    **語が同じ位相はまとめて1枚にする。** 休憩と長い休憩は同じ「休憩」なので、
    2枚重ねると同じ字が二重に描かれてにじむ。
    """
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    colours = {WORK: theme.work, REST: theme.rest, LONG_REST: theme.rest,
               DONE: theme.muted}          # 完了は位相ではないので位相の色を使わない
    for text, kinds in groups(options.locale):
        doc.text(text, x=x, y=y, fill=colours[kinds[0]], size=size,
                 anchor=anchor, cls=f"d l-{kinds[0]}", weight="bold")
        tracks.append(label_track(phases, kinds, options.repeat))


def _durations(theme: Theme, options: Options) -> list[tuple[str, tuple[str, ...], str]]:
    """(表示する文字列, その文字列を出す位相, 色)。

    語をまとめた休憩と違い、**長さは分けて出す**。5分と15分は別の文字列なので
    同じ `<text>` にできない——ここが `ring` に数字が無くても休憩の長さが読める
    理由になっている（設計文書 D8）。
    """
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    present = {phase.kind for phase in phases}
    minutes = {WORK: options.work, REST: options.rest, LONG_REST: options.long_rest}
    ordered: dict[str, list[str]] = {}
    for kind in (WORK, REST, LONG_REST):
        if kind in present:
            ordered.setdefault(f"{minutes[kind]}{unit(options.locale)}", []).append(kind)
    return [(text, tuple(kinds), theme.muted) for text, kinds in ordered.items()]


def _dial(doc: Svg, tracks: list[Track], theme: Theme, options: Options, subset,
          *, cx: float, phase_y: float, unit_y: float,
          phase_size: float, unit_size: float, ink: str | None = None) -> None:
    """リングの内側に2行。元の `_reference/original-pomodoro.svg` の構成。

    元は「FOCUS」「25 MIN」に加えて「FINISHED」を**同じ中心に3枚目として**置いて
    いたので、終了時に3つが重なって読めなくなっていた。ここでは各行の候補が
    不透明度で排他になるため、重なりようがない。
    """
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    colours = {WORK: theme.work, REST: theme.rest, LONG_REST: theme.rest,
               DONE: theme.muted}
    if ink is not None:
        colours = dict.fromkeys(colours, ink)     # 単色。位相は語で読む

    # 「完了」だけは2行目を持たない。他と同じ高さに置くと、消えた行のぶんの
    # 空白が下に残って重心が上にずれる。**1行のときは2行ぶんの光学中心へ置く。**
    # 字面の高さはフォントの実測値から出す（数字の中心の2倍がほぼ字面の高さ）
    cap = subset.digit_center * 2
    middle = ((phase_y - phase_size * cap) + unit_y) / 2
    solo_y = middle + phase_size * cap / 2

    for text, kinds in groups(options.locale):
        alone = DONE in kinds
        doc.text(text, x=cx, y=solo_y if alone else phase_y,
                 fill=colours[kinds[0]], size=phase_size,
                 cls=f"d l-{kinds[0]}", weight="bold")
        tracks.append(label_track(phases, kinds, options.repeat))
    for text, kinds, colour in _durations(theme, options):
        doc.text(text, x=cx, y=unit_y, fill=ink or colour, size=unit_size,
                 cls=f"d u-{kinds[0]}", weight="bold")
        tracks.append(label_track(phases, kinds, options.repeat,
                                  name=f"u-{kinds[0]}"))


def _dots(doc: Svg, tracks: list[Track], theme: Theme, options: Options,
          *, cx: float, y: float, gap: float, r: float) -> None:
    """セットの進み具合。`sets` が0なら何も描かない。

    **間隔はキャンバスに収まるまで詰める。** 既定の間隔のまま並べると、セット数を
    増やしたときに点が画面外へ出る——SVGとしては妥当なままなので、XMLの検査では
    捕まらない。`digital` は既定値で sets=8 から溢れていた。
    """
    if options.sets <= 0:
        return
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    if options.sets > 1:
        width = CANVAS[options.design][0]
        # 中心から左右対称に置ける幅。端に近い側で決まる
        room = 2 * min(cx, width - cx) - MARGIN
        span = gap * (options.sets - 1) + 2 * r
        if span > room:
            # 間隔だけを詰めると半径に阻まれて収まらない。行全体を等比で縮める
            scale = room / span
            gap, r = gap * scale, r * scale
    left = cx - gap * (options.sets - 1) / 2
    for index in range(options.sets):
        doc.circle(cx=left + gap * index, cy=y, r=r, fill=theme.muted,
                   cls=f"d{index}")
        tracks.append(dot_track(phases, index))


def _ring(doc: Svg, tracks: list[Track], theme: Theme, options: Options,
          *, cx: float, cy: float, r: float, width: float,
          ink: str | None = None) -> list[str]:
    """`ink` を渡すと位相で色を変えない（単色のまま減る）。"""
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    circumference = 2 * math.pi * r
    doc.circle(cx=cx, cy=cy, r=r, fill="none", stroke=theme.track,
               stroke_width=width, cls="track")
    doc.circle(cx=cx, cy=cy, r=r, fill="none", stroke=ink or theme.work,
               stroke_width=width, cls="ring")
    tracks.append(ring_track(phases, circumference))
    if ink is None:
        # 同じ要素に載せるので `ring` クラスへまとめる
        tracks.append(replace(phase_track(phases, _hues(theme), "hue"), group="ring"))
    return [
        # 12時から始めるための回転。塗りの向きを決めるだけで動かない
        f".ring{{stroke-dasharray:{format_number(circumference)};"
        f"stroke-linecap:round;transform:rotate(-90deg);"
        f"transform-origin:{format_number(cx)}px {format_number(cy)}px}}",
    ]


def _bar(doc: Svg, tracks: list[Track], theme: Theme, options: Options,
         *, x: float, y: float, length: float, width: float) -> list[str]:
    """リングの直線版。`ring_track` の「円周」に長さを渡すだけで成り立つ。"""
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    line = f"M{format_number(x)} {format_number(y)} H{format_number(x + length)}"
    doc.path(line, fill="none", stroke=theme.track, stroke_width=width)
    doc.path(line, fill="none", stroke=theme.work, stroke_width=width, cls="ring")
    tracks.append(ring_track(phases, length))
    tracks.append(replace(phase_track(phases, _hues(theme), "hue"), group="ring"))
    return [f".ring{{stroke-dasharray:{format_number(length)};stroke-linecap:round}}"]


# --- デザイン ---------------------------------------------------------------

def _design_ring(doc: Svg, tracks: list[Track], theme: Theme,
                 options: Options, subset) -> list[str]:
    """元の `pomodoro.svg` の寸法をそのまま踏襲する（r=90 / 太さ8 / 2行）。"""
    rules = _ring(doc, tracks, theme, options, cx=100, cy=100, r=90, width=8)
    _dial(doc, tracks, theme, options, subset, cx=100, phase_y=96, unit_y=122,
          phase_size=22, unit_size=14)
    _dots(doc, tracks, theme, options, cx=100, y=148, gap=15, r=4)
    return rules


def _design_odometer(doc: Svg, tracks: list[Track], theme: Theme,
                     options: Options, subset) -> list[str]:
    rules = _ring(doc, tracks, theme, options, cx=110, cy=110, r=96, width=8)
    _labels(doc, tracks, theme, options, x=110, y=76,
            size=15 if options.locale == "ja" else 13)
    rules += _digit_columns(doc, tracks, theme, options, subset,
                            cx=110, baseline=126, size=42)
    _dots(doc, tracks, theme, options, cx=110, y=152, gap=15, r=4)
    return rules


def _design_digital(doc: Svg, tracks: list[Track], theme: Theme,
                    options: Options, subset) -> list[str]:
    doc.rect(x=0.5, y=0.5, width=279, height=109, rx=10, fill=theme.bg,
             stroke=theme.track, stroke_width=1)
    rules = _digit_columns(doc, tracks, theme, options, subset,
                           cx=92, baseline=66, size=44)
    _labels(doc, tracks, theme, options, x=262, y=45,
            size=16 if options.locale == "ja" else 14, anchor="end")
    _dots(doc, tracks, theme, options, cx=234, y=64, gap=14, r=4)
    rules += _bar(doc, tracks, theme, options, x=20, y=90, length=242, width=5)
    return rules


def _design_minimal(doc: Svg, tracks: list[Track], theme: Theme,
                    options: Options, subset) -> list[str]:
    """`ring` と同じ構成を**単色**で。元の `pomodoro.svg` をそのまま。

    位相を色で示さないので、作業か休憩かは語で読む——元の作りがそうだった。
    パレットは効き続ける（既定＝墨、`terminal`＝緑）が、位相では変わらない。
    READMEに置いたときに主張しないことを選ぶ人のための版。
    """
    rules = _ring(doc, tracks, theme, options, cx=100, cy=100, r=90, width=8,
                  ink=theme.fg)
    _dial(doc, tracks, theme, options, subset, cx=100, phase_y=96, unit_y=122,
          phase_size=22, unit_size=14, ink=theme.fg)
    _dots(doc, tracks, theme, options, cx=100, y=148, gap=15, r=4)
    return rules


#: マトリックスの降る数字。列数と、1列あたりの字数
RAIN_COLUMNS, RAIN_LENGTH = 14, 9

#: 暗色のときの雨の色。本家の燐光緑。明色では沈むのでテーマの色に任せる
RAIN_DARK = "#00ff41"


def _design_matrix(doc: Svg, tracks: list[Track], theme: Theme,
                   options: Options, subset) -> list[str]:
    """降る数字の中に時刻が浮く。

    降る文字に数字を使うのは雰囲気のためだけではない——**埋め込みフォントに
    数字しか入っていない**ので、他の字を使えば豆腐になる。制約が意匠を決めた。

    列ごとに周期と開始位置をずらす。乱数は使わない（決定的出力のため）ので、
    列番号から素数を混ぜて周期を散らしている。
    """
    width, height = CANVAS["matrix"]
    cell = 15
    doc.clip_rect("rain", x=0, y=0, width=width, height=height)
    with doc.group(cls="rain", clip="rain"):
        for index in range(RAIN_COLUMNS):
            x = 10 + index * (width - 20) / (RAIN_COLUMNS - 1)
            with doc.group(cls=f"r{index}"):
                doc.raw(strip(RAIN_LENGTH, cell, x, 0))
            # 7と11を混ぜて周期を散らす。乱数だとバイト列が毎回変わる
            period = 6 + (index * 7) % 11
            span = height + RAIN_LENGTH * cell
            # 負の遅延で「すでに再生済み」の位置から描く。これが無いと t=0 では
            # 全列が画面の上に揃っていて、最初の数秒は何も降っていない
            tracks.append(linear_track(
                f"r{index}", period,
                (f"transform:translateY({format_number(-RAIN_LENGTH * cell)}px)",
                 f"transform:translateY({format_number(span)}px)"),
                delay=-((index * 5) % period) - 0.5,
            ))

    # 暗色は本家に寄せた燐光緑。明色では薄すぎて消えるのでテーマの色を使う
    ink = RAIN_DARK if theme.name.endswith("-dark") else theme.work
    rules = [f".rain{{fill:{ink};font-size:{format_number(cell * 0.8)}px;"
             f"opacity:0.18}}"]
    rules += _digit_columns(doc, tracks, theme, options, subset,
                            cx=width / 2, baseline=96, size=40)
    _labels(doc, tracks, theme, options, x=width / 2, y=126,
            size=15 if options.locale == "ja" else 13)
    _dots(doc, tracks, theme, options, cx=width / 2, y=146, gap=15, r=4)
    return rules


_DESIGNS = {
    "ring": _design_ring,
    "odometer": _design_odometer,
    "digital": _design_digital,
    "minimal": _design_minimal,
    "matrix": _design_matrix,
}


def render(options: Options, mode: str, freeze: float | None = None) -> bytes:
    """1枚ぶんのSVGを返す。

    `freeze` を渡すと、その秒数の状態で止まった静止画になる。休憩や完了の
    見た目を確認するためのもので、配布物には使わない。
    """
    theme = theme_of(options.palette, mode)
    subset = load_subset(FONT)
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    total = total_seconds(phases)

    drawn = required_charset(options.locale)
    missing = missing_characters(drawn, subset)
    if missing:
        raise ValueError(
            f"サブセットに無い文字を描こうとしています: {''.join(sorted(missing))}。"
            "gen_font_subset を実行し直してください"
        )

    width, height = CANVAS[options.design]
    title = f"{label(options.locale, WORK)} {options.work}/{options.rest}"
    doc = Svg(width, height,
              title=title,
              desc=f"{options.design} pomodoro, "
                   f"{options.work}min work / {options.rest}min break")
    doc.comment(subset.license_notice())

    if options.design not in OWN_BACKGROUND:
        doc.background(theme.bg)

    tracks: list[Track] = []
    rules = _DESIGNS[options.design](doc, tracks, theme, options, subset)

    # 規則は描き終えるまで決まらない。`style` は順序によらず先頭に出る
    css = [subset.font_face_css(), f'.d{{font-family:"{subset.family}"}}']
    css += rules
    if freeze is None:
        css += _animations(tracks, total, options.repeat)
        # 動きの抑制を求めている閲覧者には静止した姿を見せる。`<img>` 経由SVGの
        # メディアクエリはOS設定に解決される——`prefers-color-scheme` ではそれが
        # 欠陥だが、ここではそれこそが正しい。**この方式で正しく効く唯一の
        # メディアクエリ**なので使わない理由がない。静止値は既に規則に入っている
        selectors = ",".join(dict.fromkeys(f".{track.target}" for track in tracks))
        css.append(
            f"@media (prefers-reduced-motion:reduce){{{selectors}{{animation:none}}}}"
        )
        css += [track.to_css() for track in tracks]
    else:
        # 静止画にキーフレームは要らない。落とすとファイルも小さくなる
        css += [_frozen(track, freeze, options.repeat) for track in tracks]
    doc.style("".join(css))
    return doc.to_bytes()


def variants(options: Options, freeze: float | None = None) -> dict[str, bytes]:
    """light/dark の対を返す。貼る側は `<picture>` で出し分ける。"""
    return {mode: render(options, mode, freeze) for mode in ("light", "dark")}
