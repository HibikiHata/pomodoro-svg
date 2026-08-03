"""fontembed のユニットテスト。

フォントは生成SVGの中に base64 で入る。つまり配布される複製ごとにフォント
本体が同梱されるので、OFL 1.1 が各複製に求める著作権表示とライセンスは
文書の中に無ければならない——リポジトリのLICENSEファイルでは条件を満たさない。

描く文字がサブセットに無いとブラウザは黙って豆腐を出す。実グリフを検査するのと
同じ目的を、標準ライブラリだけで達成するために manifest と突き合わせる。
"""

from __future__ import annotations

import base64

import pytest

from pomodoro.charset import required_charset
from pomodoro.fontembed import (
    FontSubset,
    available_subsets,
    load_subset,
    missing_characters,
)

SAMPLE = FontSubset(
    family="probe",
    data=b"\x00\x01\x00\x00rest-of-a-font",
    charset=frozenset("012"),
    copyright="Copyright 2026 Someone <x@example.com> -- all rights",
)


def test_font_face_declares_the_family_and_embeds_the_bytes():
    css = SAMPLE.font_face_css()
    assert "@font-face{" in css
    assert "font-family:'probe'" in css
    assert base64.b64encode(SAMPLE.data).decode("ascii") in css
    assert "format('truetype')" in css


def test_font_face_can_be_placed_inside_a_style_element():
    # `<` や `&` が混じると文書構造が壊れる。base64 の字種はこれを満たす
    css = SAMPLE.font_face_css()
    assert "<" not in css and "&" not in css


def test_licence_notice_names_the_licence_and_where_to_read_it():
    # OFL 1.1 条項2は「著作権表示**と**ライセンス」を求める。URLだけでは足りない
    notice = SAMPLE.license_notice()
    assert "Copyright 2026 Someone" in notice
    assert "SIL Open Font License" in notice
    assert "1.1" in notice


def test_licence_notice_survives_being_put_in_an_xml_comment():
    # 著作権表示にメールアドレスの山括弧や連続ハイフンが入っていることがある。
    # そのまま入れるとコメントが壊れて文書ごと落ちる
    notice = SAMPLE.license_notice()
    assert "--" not in notice
    assert "<" not in notice and ">" not in notice


def test_missing_characters_finds_what_the_subset_cannot_draw():
    assert missing_characters("012", SAMPLE) == set()
    assert missing_characters("0129", SAMPLE) == {"9"}


def test_missing_characters_reports_every_absentee_once():
    assert missing_characters("99988", SAMPLE) == {"9", "8"}


def test_loading_an_absent_subset_says_how_to_build_it():
    with pytest.raises(ValueError, match="gen_font_subset"):
        load_subset("no-such-font")


def test_available_subsets_is_deterministic():
    assert available_subsets() == sorted(available_subsets())


# --- 生成済みアセットに対する検査 -------------------------------------------
#
# 生成物はリポジトリに入る。文言を足してサブセットを作り直し忘れる、という
# 一番起きやすい壊れ方をここで捕まえる。

def test_the_shipped_subset_exists():
    assert "noto-sans-jp" in available_subsets()


def test_the_shipped_subset_covers_every_character_we_draw():
    subset = load_subset("noto-sans-jp")
    assert missing_characters(required_charset(), subset) == set()


def test_the_shipped_subset_carries_a_copyright_line():
    assert load_subset("noto-sans-jp").copyright
