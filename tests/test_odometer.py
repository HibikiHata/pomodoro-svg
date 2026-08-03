"""odometer のユニットテスト。

CSSは文字列を計算できないので、数字は「描いて動かす」しかない。縦に積んだ帯を
1セル分ずつ跳ばし、1セル高の窓で切る。桁揃えと移動量がここで決まる。
"""

from __future__ import annotations

import re

import pytest

from pomodoro.odometer import cell_offset, strip


def texts(fragment: str) -> list[tuple[float, str]]:
    """(y, 中身) の一覧。属性の並び順に依存しないよう個別に拾う。"""
    out = []
    for element in re.findall(r"<text\b[^>]*>[^<]*</text>", fragment):
        y = float(re.search(r'\by="([-\d.]+)"', element).group(1))
        body = re.search(r">([^<]*)</text>", element).group(1)
        out.append((y, body))
    return out


def test_strip_has_one_row_per_digit():
    assert len(texts(strip(count=10, cell=48, x=100, baseline=112))) == 10


def test_rows_are_spaced_by_exactly_one_cell():
    rows = texts(strip(count=6, cell=48, x=100, baseline=112))
    ys = [y for y, _ in rows]
    assert ys == [112, 160, 208, 256, 304, 352]


def test_rows_carry_the_digits_in_order():
    rows = texts(strip(count=6, cell=48, x=100, baseline=112))
    assert [body for _, body in rows] == ["0", "1", "2", "3", "4", "5"]


def test_every_row_shares_the_same_x():
    fragment = strip(count=10, cell=48, x=137.5, baseline=112)
    assert len(re.findall(r'\bx="137.5"', fragment)) == 10


def test_offset_moves_up_by_one_cell_per_digit():
    # 窓は固定で、帯のほうが上へ動く。だから符号は負
    assert cell_offset(0, cell=48) == 0
    assert cell_offset(1, cell=48) == -48
    assert cell_offset(9, cell=48) == -432


def test_offset_and_strip_agree_on_which_digit_lands_in_the_window():
    # 帯を cell_offset(d) だけ動かすと、d 行目のベースラインが窓の基準線に来る
    baseline = 112
    rows = texts(strip(count=10, cell=48, x=100, baseline=baseline))
    for digit in range(10):
        y, body = rows[digit]
        assert y + cell_offset(digit, cell=48) == baseline
        assert body == str(digit)


def test_strip_emits_no_characters_outside_the_digit_set():
    # 埋め込みフォントは数字しか持たない。他の文字が混じれば豆腐になる
    bodies = "".join(body for _, body in texts(strip(count=10, cell=48, x=0, baseline=0)))
    assert set(bodies) <= set("0123456789")


def test_integer_coordinates_are_not_printed_with_a_decimal_point():
    # 決定的出力の一部。同じ入力なら同じバイト列でなければ差分が毎回出る
    assert 'y="112"' in strip(count=1, cell=48, x=100, baseline=112)
    assert 'y="112.0"' not in strip(count=1, cell=48, x=100, baseline=112)


def test_repeated_calls_are_byte_identical():
    a = strip(count=10, cell=48, x=100, baseline=112)
    b = strip(count=10, cell=48, x=100, baseline=112)
    assert a == b


@pytest.mark.parametrize(
    "kwargs",
    [
        {"count": 0, "cell": 48, "x": 0, "baseline": 0},
        {"count": -1, "cell": 48, "x": 0, "baseline": 0},
        {"count": 11, "cell": 48, "x": 0, "baseline": 0},   # 数字は10種まで
        {"count": 10, "cell": 0, "x": 0, "baseline": 0},
        {"count": 10, "cell": -48, "x": 0, "baseline": 0},
    ],
)
def test_rejects_impossible_strips(kwargs):
    with pytest.raises(ValueError):
        strip(**kwargs)
