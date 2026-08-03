"""確認用の生成物のテスト。

ポモドーロは待たないと次の状態が見られないので、位相ごとの静止画が
デザイン検討の唯一の手段になる。**止めた時刻が意図した位相に落ちていない**と、
見比べているものが別物になる——しかも絵としては成立しているので気づけない。
"""

from __future__ import annotations

import pytest

from pomodoro._generate.gen_preview import MOMENTS, SHORT, instants, page
from pomodoro.config import DESIGNS, Options
from pomodoro.schedule import LONG_REST, REST, WORK, cycle
from pomodoro.timeline import at

EXPECTED = {"start": WORK, "work": WORK, "rest": REST, "done": LONG_REST}


def test_every_moment_has_an_instant():
    # 既定の設定では5つとも存在する
    assert set(instants(Options())) == {name for name, _, _ in MOMENTS}


def test_a_single_set_has_no_short_break_to_show():
    # 作業の次がいきなり長い休憩。無いものを長い休憩で代用すると同じ絵が2枚並ぶ
    assert "rest" not in instants(Options(sets=1))


def test_each_instant_lands_in_the_phase_it_claims():
    options = Options()
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    for name, (second, _) in instants(options).items():
        phase, _ = at(phases, min(second, second - 1 if name == "done" else second))
        assert phase.kind == EXPECTED[name], f"{name}: {phase.kind}"


def test_the_work_still_is_mid_phase_so_the_ring_is_partly_drained():
    # 開始直後と同じ絵では「作業中」を見たことにならない
    options = Options()
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    remaining = at(phases, instants(options)["work"][0])[1]
    assert 0 < remaining < phases[0].seconds


def test_the_finished_still_lands_in_the_long_break():
    # 長い休憩は専用の瞬間を持たない（休憩と同じ絵になる）。点が全部濃い姿は
    # ここで見る
    options = Options()
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    phase, _ = at(phases, instants(options)["done"][0] - 1)
    assert phase.kind == LONG_REST
    assert phase.index == options.sets - 1


def test_the_finished_still_runs_once_not_forever():
    assert instants(Options())["done"][1] == "once"


@pytest.mark.parametrize("kwargs", [
    {"work": 50, "rest": 10, "long_rest": 20},
    {"sets": 1},
    {"sets": 2, "work": 1, "rest": 1, "long_rest": 1},
])
def test_instants_follow_the_schedule(kwargs):
    # 時刻を定数で持つと、既定を変えたときに黙って別の位相を指す
    options = Options(**kwargs)
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    for name, (second, _) in instants(options).items():
        probe = second - 1 if name == "done" else second
        assert at(phases, probe)[0].kind == EXPECTED[name], f"{kwargs} {name}"


def test_each_instant_sits_inside_its_phase_not_at_the_edge():
    # 1分の位相に固定の60秒を足すと次の位相へ飛び出す
    options = Options(work=1, rest=1, sets=2, long_rest=1)
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    for name, (second, _) in instants(options).items():
        if name in ("start", "done"):
            continue
        phase, remaining = at(phases, second)
        assert 0 < remaining < phase.seconds, f"{name}: 位相の端にいる"


def test_the_short_schedule_turns_over_within_a_few_minutes():
    # 位相の変わり目を実時間で見るためのもの。長いと確認にならない
    phases = cycle(SHORT.work, SHORT.rest, SHORT.sets, SHORT.long_rest)
    assert sum(phase.seconds for phase in phases) <= 5 * 60


def test_the_page_references_every_generated_image():
    # ページも画像も同じ定義から作る。書き忘れが起きないことを固定する
    text = page()
    for design in DESIGNS:
        assert f"anim-{design}-light.svg" in text
        assert f"short-{design}-light.svg" in text
        for name, _, _ in MOMENTS:
            for mode in ("light", "dark"):
                assert f"{name}-{design}-{mode}.svg" in text


def test_the_page_leads_with_the_zero_wait_section():
    text = page()
    assert text.index("待ち時間なし") < text.index("裏タブ25分")
