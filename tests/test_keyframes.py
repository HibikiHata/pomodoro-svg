"""keyframes のユニットテスト。

ここが「意図した時刻に意図した値になっているか」を問う場所。生成したCSSを
目で見て納得するのではなく、`timeline.at()` という別経路の正解と突き合わせる。
カレンダーで、検証すべき区別を検査器の側で正規化して潰していた失敗をしたので、
正解は生成物から独立していなければならない。
"""

from __future__ import annotations

import re

import pytest

from pomodoro.keyframes import (
    _checked,
    dot_track,
    phase_track,
    label_track,
    minute_track,
    ring_track,
    second_track,
)
from pomodoro.odometer import cell_offset
from pomodoro.schedule import cycle, total_seconds
from pomodoro.timeline import at, second_digits

PAIR = cycle(work=25, rest=5, sets=0, long_rest=15)      # 1800秒
FULL = cycle(work=25, rest=5, sets=4, long_rest=15)      # 7800秒
CIRCUMFERENCE = 263.894
CELL = 48

SAMPLES = [0, 1, 2, 59, 60, 61, 599, 1499, 1500, 1501, 1799, 1800, 3000, 6899]


def held_at(track, t: float) -> str:
    """step-end のトラックが t 秒後に保持している宣言。

    直前の停止点の値がそのまま保たれる、というのが step-end の意味。
    """
    percent = 100.0 * (t % track.duration) / track.duration
    held = track.stops[-1][1]      # 折り返し直後は最後の停止点が生きている
    for position, declaration in track.stops:
        if position <= percent + 1e-9:
            held = declaration
        else:
            break
    return held


def translate_px(declaration: str) -> float:
    return float(re.search(r"translateY\(([-\d.]+)px\)", declaration).group(1))


# --- リング -----------------------------------------------------------------

def test_ring_starts_full_and_ends_empty():
    track = ring_track(PAIR, CIRCUMFERENCE)
    assert track.stops[0] == (0.0, "stroke-dashoffset:0")
    assert track.stops[-1][0] == 100.0
    assert track.stops[-1][1] == f"stroke-dashoffset:{CIRCUMFERENCE}"


def test_ring_is_reset_at_every_phase_start():
    # 位相ごとに巻き戻る。周期全体で1回だけ減っていくのでは、休憩に入っても
    # リングが減り続けてしまう
    track = ring_track(FULL, CIRCUMFERENCE)
    resets = [position for position, decl in track.stops if decl.endswith(":0")]
    assert len(resets) == len(FULL)


def test_ring_positions_ascend_and_are_distinct():
    # 同じ位置に2つ並ぶと片方が消える。短い位相ほど起きやすい
    positions = [position for position, _ in ring_track(FULL, CIRCUMFERENCE).stops]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)


def test_ring_empties_just_before_each_phase_boundary():
    track = ring_track(PAIR, CIRCUMFERENCE)
    boundary = 100.0 * 1500 / total_seconds(PAIR)
    empties = [p for p, decl in track.stops if decl.endswith(f":{CIRCUMFERENCE}")]
    assert any(0 < boundary - p < 0.01 for p in empties)


def test_ring_interpolates_linearly_and_so_is_not_step_end():
    assert ring_track(PAIR, CIRCUMFERENCE).timing == "linear"


# --- 分の桁 -----------------------------------------------------------------

@pytest.mark.parametrize("column", [0, 1])
def test_minute_columns_agree_with_at(column):
    track = minute_track(FULL, cell=CELL, column=column)
    for t in SAMPLES:
        minutes = at(FULL, t)[1] // 60
        digit = (minutes // 10) if column == 0 else (minutes % 10)
        assert translate_px(held_at(track, t)) == cell_offset(digit, CELL)


def test_minute_columns_hold_their_value_between_changes():
    assert minute_track(FULL, cell=CELL, column=1).timing == "step-end"


def test_minute_tens_changes_less_often_than_ones():
    # 十の位は分が10跨ぐときだけ動く。同じ値を並べていれば無駄が出る
    tens = minute_track(FULL, cell=CELL, column=0)
    ones = minute_track(FULL, cell=CELL, column=1)
    assert len(tens.stops) < len(ones.stops)


def test_minute_columns_have_no_consecutive_duplicates():
    for column in (0, 1):
        stops = minute_track(FULL, cell=CELL, column=column).stops
        values = [declaration for _, declaration in stops]
        assert all(a != b for a, b in zip(values, values[1:]))


# --- 秒の桁 -----------------------------------------------------------------

@pytest.mark.parametrize("column", [0, 1])
def test_second_columns_agree_with_the_oracle(column):
    track = second_track(cell=CELL, column=column)
    for t in SAMPLES:
        assert translate_px(held_at(track, t)) == cell_offset(second_digits(t)[column], CELL)


def test_second_columns_loop_independently_of_the_schedule():
    # 位相を引数に取らないこと自体が主張。全位相が分単位なので秒は畳める
    assert second_track(cell=CELL, column=1).duration == 10
    assert second_track(cell=CELL, column=0).duration == 60


def test_second_ones_visits_every_digit():
    stops = second_track(cell=CELL, column=1).stops
    offsets = {translate_px(declaration) for _, declaration in stops}
    assert offsets == {cell_offset(d, CELL) for d in range(10)}


# --- ラベル -----------------------------------------------------------------

def test_exactly_one_label_is_visible_at_any_time():
    # 休憩と長い休憩は同じ「休憩」なのでひとまとめ。残り時間と点で区別がつく
    groups = {("work",): None, ("rest", "long_rest"): None}
    tracks = {kinds: label_track(FULL, kinds) for kinds in groups}
    for t in SAMPLES:
        visible = [kinds for kinds, track in tracks.items()
                   if held_at(track, t) == "opacity:1"]
        assert len(visible) == 1
        assert at(FULL, t)[0].kind in visible[0]


def test_a_label_absent_from_the_cycle_is_never_visible():
    track = label_track(PAIR, ("long_rest",))   # sets=0 に長い休憩は無い
    assert all(declaration == "opacity:0" for _, declaration in track.stops)


def test_a_merged_label_covers_both_of_its_phases():
    # 「休憩」は短い休憩と長い休憩の両方で出る
    track = label_track(FULL, ("rest", "long_rest"))
    for t in (1560, 7080):
        assert held_at(track, t) == "opacity:1"


def test_label_tracks_hold_their_value():
    assert label_track(FULL, ("work",)).timing == "step-end"


# --- 出力の形 ---------------------------------------------------------------

def test_css_is_a_single_keyframes_rule():
    css = ring_track(PAIR, CIRCUMFERENCE, name="sweep").to_css()
    assert css.startswith("@keyframes sweep{")
    assert css.endswith("}")
    assert "<" not in css and "&" not in css     # style 要素にそのまま入る


def test_css_percentages_carry_no_trailing_zeros():
    css = minute_track(PAIR, cell=CELL, column=1).to_css()
    assert "0%{" in css
    assert not re.search(r"\b\d+\.0+%", css)


def test_css_is_byte_identical_across_calls():
    a = ring_track(FULL, CIRCUMFERENCE).to_css()
    b = ring_track(FULL, CIRCUMFERENCE).to_css()
    assert a == b


def test_rejects_a_circumference_that_is_not_positive():
    with pytest.raises(ValueError):
        ring_track(PAIR, 0)


# --- 停止点のガード ---------------------------------------------------------
#
# 現実的な設定では踏めない（60秒の位相が丸めで潰れるには周期が19年ほど要る）。
# 将来 EPSILON や分解能を触ったとき、黙って停止点が消える形で壊れるのを防ぐ
# ためのものなので、内部関数を直接呼んで確かめる。

def test_stops_that_round_to_the_same_position_are_rejected():
    with pytest.raises(ValueError, match="同じ位置"):
        _checked("t", "step-end", 60, [(0.0, "a"), (0.000001, "b")])


def test_stops_out_of_order_are_rejected():
    with pytest.raises(ValueError, match="昇順"):
        _checked("t", "step-end", 60, [(50.0, "a"), (10.0, "b")])


# --- 終端の状態 -------------------------------------------------------------

def test_digit_tracks_close_at_a_hundred_percent():
    # forwards で止めたとき最後の停止点で固まる。ここを置かないと
    # 「00:01」のような半端な状態で終わる
    for track in (minute_track(FULL, cell=CELL, column=1),
                  second_track(cell=CELL, column=1)):
        assert track.stops[-1][0] == 100.0


def test_a_looping_track_closes_where_it_will_restart():
    # 100%と0%は同じ瞬間。値が違えば折り返しで一瞬ちらつく
    for track in (minute_track(FULL, cell=CELL, column=0, repeat="loop"),
                  minute_track(FULL, cell=CELL, column=1, repeat="loop"),
                  second_track(cell=CELL, column=0),
                  second_track(cell=CELL, column=1)):
        assert track.stops[-1][1] == track.stops[0][1]


def test_a_one_shot_track_closes_at_zero():
    for column in (0, 1):
        track = minute_track(FULL, cell=CELL, column=column, repeat="once")
        assert translate_px(track.stops[-1][1]) == cell_offset(0, CELL)


def test_the_closing_stop_does_not_disturb_the_sampled_values():
    # 終端を足したせいで途中の値が変わっていないこと
    track = minute_track(FULL, cell=CELL, column=1, repeat="once")
    for t in SAMPLES:
        expected = (at(FULL, t)[1] // 60) % 10
        assert translate_px(held_at(track, t)) == cell_offset(expected, CELL)


# --- セットの点 -------------------------------------------------------------

def test_a_dot_starts_dim_and_fills_once():
    track = dot_track(FULL, 0)
    assert track.stops[0] == (0.0, "opacity:0.25")
    assert [d for _, d in track.stops].count("opacity:1") == 1


def test_a_dot_fills_at_the_break_that_follows_its_own_work():
    # 満ちる瞬間が「1本終えた」ときであってほしい。次の作業が始まってから
    # では一拍遅れる
    track = dot_track(FULL, 1)
    filled = [position for position, d in track.stops if d == "opacity:1"][0]
    expected = 100.0 * (1500 + 300 + 1500) / total_seconds(FULL)
    assert filled == pytest.approx(expected)


def test_dots_fill_in_order():
    positions = []
    for index in range(4):
        stops = dot_track(FULL, index).stops
        positions.append([p for p, d in stops if d == "opacity:1"][0])
    assert positions == sorted(positions)


def test_the_last_dot_fills_at_the_long_break():
    track = dot_track(FULL, 3)
    filled = [position for position, d in track.stops if d == "opacity:1"][0]
    expected = 100.0 * (total_seconds(FULL) - 900) / total_seconds(FULL)
    assert filled == pytest.approx(expected)


def test_a_dot_beyond_the_set_count_never_fills():
    track = dot_track(FULL, 9)
    assert [d for _, d in track.stops] == ["opacity:0.25"]


# --- 位相ごとの宣言 ---------------------------------------------------------

COLOURS = {"work": "stroke:#a", "rest": "stroke:#b", "long_rest": "stroke:#c"}


def test_a_phase_track_ends_on_the_last_phase():
    # 1回きりのとき `forwards` はここで固まる。先頭の色を置くと、終わった
    # タイマーが作業中の色になる
    assert phase_track(FULL, COLOURS, "hue").stops[-1][1] == COLOURS["long_rest"]


def test_a_phase_track_agrees_with_at():
    track = phase_track(FULL, COLOURS, "hue")
    for t in SAMPLES:
        assert held_at(track, t) == COLOURS[at(FULL, t)[0].kind]


def test_a_phase_track_skips_repeats():
    # work/rest が交互なので、色は位相の数だけ変わる
    assert len(phase_track(FULL, COLOURS, "hue").stops) == len(FULL)
