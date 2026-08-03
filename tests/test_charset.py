"""labels と charset のユニットテスト。

描く文字がサブセットに無いと、ブラウザは黙って豆腐（□）を出す。文言を足した
ときにサブセットの再生成を忘れる、という壊れ方が一番起きやすいので、文言の
定数から機械的に集める形にして、手で書き写す余地を無くす。
"""

from __future__ import annotations

import pytest

from pomodoro.charset import required_charset
from pomodoro.labels import KINDS, LOCALES, label


def test_every_locale_defines_every_phase_kind():
    for locale in LOCALES:
        for kind in KINDS:
            assert label(locale, kind)


def test_the_states_a_reader_must_tell_apart_have_distinct_labels():
    # 作業・休憩・完了が同じ文字列だと、ラベルを見ても状態が判別できない
    for locale in LOCALES:
        names = [label(locale, kind) for kind in ("work", "rest", "done")]
        assert len(set(names)) == len(names), locale


def test_the_two_breaks_share_one_label_on_purpose():
    # 長さは残り時間とリングが示すので語を分けない。`ring` は数字を持たないが、
    # 点を見れば最後のセットを終えたことが分かる
    for locale in LOCALES:
        assert label(locale, "rest") == label(locale, "long_rest")


@pytest.mark.parametrize("args", [("fr", "work"), ("ja", "nap")])
def test_label_rejects_unknown_keys(args):
    with pytest.raises(ValueError):
        label(*args)


def test_charset_covers_every_label_in_every_locale():
    # ここが本体。文言を足したのにサブセットを作り直していない、を検出する
    covered = set(required_charset())
    for locale in LOCALES:
        for kind in KINDS:
            missing = set(label(locale, kind)) - covered
            assert not missing, f"{locale}/{kind}: {''.join(sorted(missing))}"


def test_charset_contains_the_digits():
    assert set("0123456789") <= set(required_charset())


def test_charset_excludes_the_colon():
    # 区切りは円2つで描くのでフォントに要らない。要求だけ残すと、描かない字の
    # ために元フォントを縛ることになる
    assert ":" not in required_charset()


def test_charset_can_be_narrowed_to_one_locale():
    # いまは英語だけなので全体と一致する。**絞る仕組みは残す**——日本語を足した
    # ときに、英語版のサブセットにCJKを抱え込ませないため
    assert set(required_charset("en")) == set(required_charset())


def test_only_latin_and_digits_are_required():
    # 日本語を落としたので、サブセットにCJKのアウトラインは要らない
    assert all(ord(character) < 128 for character in required_charset())


def test_charset_has_no_duplicates():
    charset = required_charset()
    assert len(charset) == len(set(charset))


def test_charset_order_is_deterministic():
    assert required_charset() == required_charset()


def test_charset_rejects_an_unknown_locale():
    with pytest.raises(ValueError):
        required_charset("fr")
