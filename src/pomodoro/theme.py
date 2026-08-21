"""配色。パレット × (light / dark) の2次元で持つ。

SVG内の `@media (prefers-color-scheme)` を使わず2枚出しにしている。あれは
GitHubのテーマ切り替えではなくOSの設定に解決され、Safari では効かない
（実測）。だから配色は「1テーマ1ファイル」の単位で持つ。

コントラスト比は要件であって好みではない。数字が読めないタイマーはタイマー
ではないので、本文4.5:1・補助3:1・図形3:1（WCAG 1.4.11）をテストで固定する。
"""
from __future__ import annotations

from dataclasses import dataclass

#: 色を持つフィールド。テストと生成器がこの一覧を使って全色を走査する
FIELDS: tuple[str, ...] = ("bg", "fg", "muted", "track", "work", "rest")


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str          # 背景
    fg: str          # 残り時間の数字など主要な文字
    muted: str       # ラベルや補助的な文字
    track: str       # リング・進捗バーの下地（本体より必ず沈める）
    work: str        # 作業中のリング
    rest: str        # 休憩中。**長い休憩も同じ色**——語を分けないので色も分けない


PALETTES: dict[str, dict[str, Theme]] = {
    # GitHub の既定キャンバスに馴染ませたもの
    "default": {
        "light": Theme(
            name="default-light",
            bg="#ffffff", fg="#1f2328", muted="#59636e", track="#d1d9e0",
            work="#cf222e", rest="#1a7f37",
        ),
        "dark": Theme(
            name="default-dark",
            bg="#0d1117", fg="#e6edf3", muted="#9198a1", track="#30363d",
            work="#ff7b72", rest="#3fb950",
        ),
    },
    # 曜日も位相も色で区別しない無彩色版。他の配色と並べても喧嘩しない。
    # 位相はラベルと数字で読む
    "mono": {
        "light": Theme(
            name="mono-light",
            bg="#ffffff", fg="#1a1a1a", muted="#6e6e6e", track="#dcdcdc",
            work="#1a1a1a", rest="#6e6e6e",
        ),
        "dark": Theme(
            name="mono-dark",
            bg="#111111", fg="#ededed", muted="#9a9a9a", track="#333333",
            work="#ededed", rest="#9a9a9a",
        ),
    },
    # 端末の画面。`calc_display.svg` の緑を引き継ぐ
    "terminal": {
        "light": Theme(
            name="terminal-light",
            bg="#f4f7f4", fg="#0f3d20", muted="#3d6b4c", track="#c8dccd",
            work="#0f3d20", rest="#3d6b4c",
        ),
        "dark": Theme(
            name="terminal-dark",
            bg="#0b0f0c", fg="#3fb950", muted="#5d8f68", track="#1f2a21",
            work="#3fb950", rest="#5d8f68",
        ),
    },
}


def theme_of(palette: str, mode: str) -> Theme:
    if palette not in PALETTES:
        raise ValueError(
            f"未知のパレットです: {palette!r}（{'/'.join(sorted(PALETTES))}）")
    if mode not in PALETTES[palette]:
        raise ValueError(f"未知のモードです: {mode!r}（light/dark）")
    return PALETTES[palette][mode]


def _linear(channel: int) -> float:
    """sRGB の1チャンネルを線形の輝度へ戻す（WCAG 2.x の定義）。"""
    value = channel / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(colour: str) -> float:
    text = colour.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"6桁の16進表記である必要があります: {colour!r}")
    red, green, blue = (int(text[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)


def contrast_ratio(a: str, b: str) -> float:
    """2色のコントラスト比。1.0（同色）から21.0（黒白）まで。"""
    first, second = _luminance(a), _luminance(b)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)
