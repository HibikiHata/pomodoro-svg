"""timeline のユニットテスト。

`at()` は「t秒後に何が表示されているべきか」の独立した正解を返す関数で、
後段が生成するCSSはこれと突き合わせて検証する。CSSがそれらしく見えるかではなく、
意図した時刻に意図した値になっているかを問えるようにするための分割。
"""

from __future__ import annotations

import pytest

from pomodoro.schedule import cycle, total_seconds
from pomodoro.timeline import (
    SECOND_ONES_PERIOD,
    SECOND_TENS_PERIOD,
    at,
    minute_stops,
    phase_stops,
    second_digits,
)

PAIR = cycle(work=25, rest=5, sets=0, long_rest=15)      # 1800秒
FULL = cycle(work=25, rest=5, sets=4, long_rest=15)      # 6900秒


def test_at_zero_shows_the_first_phase_at_its_full_duration():
    phase, remaining = at(PAIR, 0)
    assert phase.kind == "work"
    assert remaining == 1500          # 25:00 が1秒だけ出る


def test_remaining_counts_down_one_per_second():
    assert at(PAIR, 1)[1] == 1499     # 24:59
    assert at(PAIR, 2)[1] == 1498


def test_remaining_is_held_across_a_fractional_second():
    # 表示は秒単位で階段状に落ちる。0.5秒後もまだ24:59
    assert at(PAIR, 1.0)[1] == at(PAIR, 1.9)[1] == 1499


def test_a_phase_boundary_belongs_to_the_phase_that_starts():
    phase, remaining = at(PAIR, 1500)
    assert phase.kind == "rest"
    assert remaining == 300           # 05:00


def test_the_last_second_of_a_phase_never_shows_zero():
    # 残り0の瞬間には次の位相へ移っている
    assert at(PAIR, 1499)[1] == 1
    assert at(PAIR, 1499.9)[1] == 1


def test_at_wraps_after_one_cycle():
    total = total_seconds(PAIR)
    assert at(PAIR, total) == at(PAIR, 0)
    assert at(PAIR, total + 7) == at(PAIR, 7)


def test_at_rejects_negative_time():
    with pytest.raises(ValueError):
        at(PAIR, -1)


def test_phase_stops_start_at_zero_and_ascend():
    stops = phase_stops(FULL)
    assert [t for t, _ in stops] == sorted(t for t, _ in stops)
    assert stops[0][0] == 0
    assert len(stops) == len(FULL)


def test_phase_stops_agree_with_at():
    # 位相の開始時刻では、その位相が満了残時間で出ていなければならない
    for start, phase in phase_stops(FULL):
        found, remaining = at(FULL, start)
        assert found is phase
        assert remaining == phase.seconds


def test_minute_stops_begin_with_the_full_minute_count():
    assert minute_stops(PAIR)[0] == (0, 25)


def test_minute_stops_count_down_to_zero_within_a_phase():
    within_work = [m for t, m in minute_stops(PAIR) if t < 1500]
    assert within_work == list(range(25, -1, -1))


def test_minute_stops_reset_at_the_phase_boundary():
    stops = dict(minute_stops(PAIR))
    assert stops[1500] == 5           # 休憩の頭で 05:00 に戻る


def test_minute_stops_has_one_entry_per_displayed_minute():
    # D分の位相は D から 0 までの D+1 通りを表示する
    assert len(minute_stops(PAIR)) == (25 + 1) + (5 + 1)


def test_minute_stops_agree_with_at():
    for t, minutes in minute_stops(PAIR):
        assert at(PAIR, t)[1] // 60 == minutes


def test_second_digits_do_not_depend_on_the_phase():
    # 全位相が分単位なので、秒の桁は位相をまたいで単純な60秒ループになる。
    # これが崩れると、秒の桁を位相ごとに描き直す必要が出てファイルが膨らむ
    for t in (0, 1, 59, 60, 1499, 1500, 1501, 6899):
        tens, ones = second_digits(t)
        assert (tens, ones) == divmod(at(FULL, t)[1] % 60, 10)


def test_second_digit_periods_are_the_loop_lengths():
    assert SECOND_ONES_PERIOD == 10
    assert SECOND_TENS_PERIOD == 60
    for t in range(0, 120):
        assert second_digits(t)[1] == second_digits(t + SECOND_ONES_PERIOD)[1]
        assert second_digits(t)[0] == second_digits(t + SECOND_TENS_PERIOD)[0]


def test_second_digits_descend_from_zero():
    # t=0 は 00 秒、その1秒後は 59 秒
    assert second_digits(0) == (0, 0)
    assert second_digits(1) == (5, 9)
    assert second_digits(59) == (0, 1)
    assert second_digits(60) == (0, 0)
