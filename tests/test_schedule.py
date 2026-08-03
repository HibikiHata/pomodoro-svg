"""schedule のユニットテスト。

1周期の構造がここで決まる。以降のタイムライン・描画はすべてこの出力を入力に取るので、
セット数と長い休憩の位置を間違えると全部が静かにずれる。
"""

from __future__ import annotations

import pytest

from pomodoro.schedule import Phase, cycle, total_seconds


def kinds(phases: tuple[Phase, ...]) -> list[str]:
    return [p.kind for p in phases]


def test_default_cycle_is_four_sets_with_a_long_break_at_the_end():
    phases = cycle(work=25, rest=5, sets=4, long_rest=15)
    assert kinds(phases) == [
        "work", "rest",
        "work", "rest",
        "work", "rest",
        "work", "long_rest",
    ]


def test_durations_are_minutes_converted_to_seconds():
    phases = cycle(work=25, rest=5, sets=1, long_rest=15)
    assert [p.seconds for p in phases] == [1500, 900]


def test_set_index_increments_once_per_set():
    phases = cycle(work=25, rest=5, sets=3, long_rest=15)
    # work と、その直後の休憩は同じセットに属する
    assert [p.index for p in phases] == [0, 0, 1, 1, 2, 2]


def test_a_single_set_still_ends_in_the_long_break():
    # AC7。セットが1つでも「最後のセットの後」であることに変わりはない
    assert kinds(cycle(work=25, rest=5, sets=1, long_rest=15)) == ["work", "long_rest"]


def test_long_rest_appears_exactly_once():
    # AC7。長い休憩が2回出るのは、セット境界の判定を間違えたときの典型的な壊れ方
    phases = cycle(work=25, rest=5, sets=4, long_rest=15)
    assert kinds(phases).count("long_rest") == 1


def test_zero_sets_is_a_bare_work_rest_pair():
    # セット表示も長い休憩も出さない設定。作業と休憩だけを回す
    phases = cycle(work=25, rest=5, sets=0, long_rest=15)
    assert kinds(phases) == ["work", "rest"]
    assert [p.index for p in phases] == [0, 0]


def test_total_seconds_is_the_sum_of_the_phases():
    phases = cycle(work=25, rest=5, sets=4, long_rest=15)
    assert total_seconds(phases) == 4 * 1500 + 3 * 300 + 900


def test_every_phase_is_a_whole_number_of_minutes():
    # 秒の桁を「位相に依存しない60秒ループ」で描ける前提そのもの。
    # 分の端数を許すとこの前提が崩れ、位相の変わり目で秒がずれる
    for phase in cycle(work=25, rest=5, sets=4, long_rest=15):
        assert phase.seconds % 60 == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"work": 0, "rest": 5, "sets": 4, "long_rest": 15},
        {"work": -1, "rest": 5, "sets": 4, "long_rest": 15},
        {"work": 25, "rest": 0, "sets": 4, "long_rest": 15},
        {"work": 25, "rest": 5, "sets": -1, "long_rest": 15},
        {"work": 25, "rest": 5, "sets": 4, "long_rest": 0},
    ],
)
def test_rejects_impossible_schedules(kwargs):
    with pytest.raises(ValueError):
        cycle(**kwargs)


@pytest.mark.parametrize("work", [25.5, 0.5, "25"])
def test_rejects_durations_that_are_not_whole_minutes(work):
    # 端数を許すと位相の長さが60の倍数でなくなり、秒の桁を1本のループで
    # 描けなくなる。壊れ方が「変わり目で秒がずれる」なので気づきにくい
    with pytest.raises(ValueError):
        cycle(work=work, rest=5, sets=4, long_rest=15)


def test_rejects_booleans_disguised_as_counts():
    # bool は int の派生なので素朴な型チェックを素通りし、sets=True が
    # sets=1 として通ってしまう
    with pytest.raises(ValueError):
        cycle(work=25, rest=5, sets=True, long_rest=15)


def test_long_rest_is_ignored_when_sets_is_zero():
    # セットを使わないなら長い休憩は出番がないので、値の検証も課さない
    assert kinds(cycle(work=25, rest=5, sets=0, long_rest=0)) == ["work", "rest"]


def test_phases_are_immutable():
    phases = cycle(work=25, rest=5, sets=1, long_rest=15)
    with pytest.raises(Exception):
        phases[0].seconds = 1  # type: ignore[misc]
