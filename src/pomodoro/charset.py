"""描きうる文字の集合。

サブセット生成器（開発時）が「何を残すか」を、描画側（実行時）が
「manifestが足りているか」を判断する共通の出典。文言は `labels` から
機械的に集める——手で書き写すと、文言を足したときに必ず漏れる。
"""
from __future__ import annotations

from pomodoro.labels import KINDS, LOCALES, LABELS, UNITS

_DIGITS = "0123456789"

#: 区切りのコロンは**フォントを使わず円2つで描く**（`render._colon`）。
#: CJKフォントのコロンは字面の中心に寄っていて数字と揃わず、しかもフォントを
#: 差し替えるたびに揃い方が変わる。図形なら配置を完全に決められる。


def required_charset(locale: str | None = None) -> str:
    """必要な文字を重複なく、決定的な順序で返す。

    `locale` を指定すると、そのロケールの文言だけに絞る。ロケール別に生成
    すればサブセットがさらに小さくなる（日本語版に FOCUS の字形は要らない）。
    """
    if locale is not None and locale not in LOCALES:
        raise ValueError(f"未知のロケールです: {locale!r}（{'/'.join(LOCALES)}）")

    targets = LOCALES if locale is None else (locale,)
    seen: dict[str, None] = {}
    for character in _DIGITS:
        seen.setdefault(character, None)
    for name in targets:
        for kind in KINDS:
            for character in LABELS[name][kind]:
                seen.setdefault(character, None)
        for character in UNITS[name]:      # ring の2行目「25分 / 25 MIN」
            seen.setdefault(character, None)
    return "".join(seen)
