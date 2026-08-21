"""theme のユニットテスト。

配色は「好み」に見えて読めるかどうかを決めている。数字が読めないタイマーは
タイマーではないので、コントラスト比を要件として固定する。

SVG内の `@media (prefers-color-scheme)` を使わず light/dark を2枚出しにするのは、
あれがGitHubのテーマ切り替えではなくOSの設定に解決され、Safari では効かないため。
だから配色は「1テーマ1ファイル」の単位で持つ。
"""

from __future__ import annotations

import re

import pytest

from pomodoro.theme import FIELDS, PALETTES, Theme, contrast_ratio, theme_of

MODES = ("light", "dark")
HEX = re.compile(r"^#[0-9a-f]{6}$")


def all_themes() -> list[Theme]:
    return [PALETTES[name][mode] for name in PALETTES for mode in MODES]


def test_every_palette_has_both_modes():
    for name, modes in PALETTES.items():
        assert set(modes) == set(MODES), name


def test_every_colour_is_a_lowercase_six_digit_hex():
    # 大文字と3桁略記を混ぜると、同じ色が別の文字列になって決定性が崩れる
    for theme in all_themes():
        for field in FIELDS:
            value = getattr(theme, field)
            assert HEX.match(value), f"{theme.name}.{field} = {value}"


def test_theme_names_are_unique():
    names = [theme.name for theme in all_themes()]
    assert len(set(names)) == len(names)


def test_theme_name_encodes_palette_and_mode():
    for palette, modes in PALETTES.items():
        for mode, theme in modes.items():
            assert theme.name == f"{palette}-{mode}"


# --- コントラスト -----------------------------------------------------------

def test_contrast_ratio_matches_the_known_extremes():
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_contrast_ratio_is_symmetric():
    assert contrast_ratio("#0d1117", "#e6edf3") == contrast_ratio("#e6edf3", "#0d1117")


def test_main_text_meets_wcag_aa():
    # 残り時間の数字がこの色で出る。読めなければ何も意味がない
    for theme in all_themes():
        assert contrast_ratio(theme.fg, theme.bg) >= 4.5, theme.name


def test_secondary_text_meets_the_large_text_threshold():
    for theme in all_themes():
        assert contrast_ratio(theme.muted, theme.bg) >= 3.0, theme.name


def test_phase_colours_meet_the_text_threshold():
    """位相の色は**ラベルの文字色としても**使われる（`render._labels`）。

    リング以外の4デザインでラベルは13〜16pxで、WCAGの大文字扱い（18.66px太字/24px）
    に届かない。したがって図形の3:1ではなく本文の4.5:1が要る。現行3パレットは
    偶然通っているが、3:1ちょうどに調整した新パレットは黙って非準拠になる。

    リングやバー（非文字）に要る3:1はこれに含まれるので、別に検査しない。
    """
    for theme in all_themes():
        for field in ("work", "rest"):
            assert contrast_ratio(getattr(theme, field), theme.bg) >= 4.5, \
                f"{theme.name}.{field}"



def test_the_track_is_dimmer_than_the_ring_it_backs():
    # 下地が本体より目立つと、減っているのか増えているのか読めない
    for theme in all_themes():
        assert contrast_ratio(theme.track, theme.bg) < contrast_ratio(theme.work, theme.bg), \
            theme.name


def test_light_and_dark_are_actually_inverted():
    for name, modes in PALETTES.items():
        light = contrast_ratio(modes["light"].bg, "#000000")
        dark = contrast_ratio(modes["dark"].bg, "#000000")
        assert light > dark, name


# --- 参照 -------------------------------------------------------------------

def test_theme_of_returns_the_requested_pair():
    assert theme_of("mono", "dark") is PALETTES["mono"]["dark"]


@pytest.mark.parametrize("args", [("nope", "light"), ("mono", "sepia")])
def test_theme_of_rejects_unknown_names(args):
    with pytest.raises(ValueError):
        theme_of(*args)


def test_themes_are_immutable():
    with pytest.raises(Exception):
        PALETTES["mono"]["light"].bg = "#000000"  # type: ignore[misc]
