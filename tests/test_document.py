"""document のユニットテスト。

外部ライブラリを使わずSVGを組み立てる。属性の並び順を固定するのは、順序が
揺れると内容が同じでも差分が出るため。カレンダーと違って `<defs>` と
`<clipPath>` と入れ子の `<g>` が要る——オドメーターの窓がそれで出来ている。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from pomodoro.document import Svg


def parse(svg: Svg):
    """組み立てた文書を読み返す。

    標準の ElementTree を使ってよいのは、**入力が同一プロセス内で生成した
    バイト列だけ**だから。外部実体もDTDも構文上入り込む余地がなく、XXE や
    billion laughs の前提が成り立たない。外から来たSVGを読む用途がここに
    入ってきたら、そのときは defusedxml へ移すこと。
    """
    return ET.fromstring(svg.to_bytes().decode("utf-8"))


def test_output_is_well_formed_xml():
    doc = Svg(220, 220, title="t", desc="d")
    doc.circle(cx=110, cy=110, r=90, fill="none", stroke="#888", stroke_width=6)
    assert parse(doc).tag.endswith("svg")


def test_root_carries_the_viewbox_and_size():
    root = parse(Svg(220, 180))
    assert root.get("viewBox") == "0 0 220 180"
    assert root.get("width") == "220"
    assert root.get("height") == "180"


def test_a_title_makes_the_image_announceable():
    # role="img" が無いと、支援技術は <title> を読み上げる相手を持たない
    root = parse(Svg(220, 220, title="Pomodoro"))
    assert root.get("role") == "img"
    assert root[0].tag.endswith("title")
    assert root[0].text == "Pomodoro"


def test_without_a_title_there_is_no_role():
    assert parse(Svg(220, 220)).get("role") is None


def test_rejects_a_size_that_is_not_positive():
    for size in ((0, 100), (100, -1)):
        with pytest.raises(ValueError):
            Svg(*size)


# --- defs と clipPath -------------------------------------------------------

def test_clip_rect_lands_in_defs():
    doc = Svg(220, 220)
    doc.clip_rect("win", x=10, y=20, width=100, height=48)
    defs = parse(doc)[0]
    assert defs.tag.endswith("defs")
    assert defs[0].tag.endswith("clipPath")
    assert defs[0].get("id") == "win"


def test_defs_is_omitted_when_nothing_needs_it():
    assert not any(child.tag.endswith("defs") for child in parse(Svg(220, 220)))


def test_defs_precedes_the_drawing():
    # 参照される側が先に来ていないと、順序に厳しい実装で解決に失敗しうる
    doc = Svg(220, 220)
    doc.rect(x=0, y=0, width=10, height=10, fill="#000")
    doc.clip_rect("win", x=0, y=0, width=10, height=10)
    tags = [child.tag.split("}")[-1] for child in parse(doc)]
    assert tags.index("defs") < tags.index("rect")


def test_duplicate_clip_ids_are_rejected():
    # 後勝ちで黙って上書きされると、片方の窓だけが正しく切られる
    doc = Svg(220, 220)
    doc.clip_rect("win", x=0, y=0, width=10, height=10)
    with pytest.raises(ValueError):
        doc.clip_rect("win", x=0, y=0, width=20, height=20)


def test_a_group_can_reference_a_clip_by_id():
    doc = Svg(220, 220)
    doc.clip_rect("win", x=0, y=0, width=10, height=10)
    with doc.group(clip="win"):
        doc.text("0", x=0, y=0, fill="#000", size=10)
    group = [c for c in parse(doc) if c.tag.endswith("g")][0]
    assert group.get("clip-path") == "url(#win)"


def test_referencing_an_undeclared_clip_is_rejected():
    doc = Svg(220, 220)
    with pytest.raises(ValueError):
        with doc.group(clip="nope"):
            pass


# --- グループ ---------------------------------------------------------------

def test_groups_nest():
    doc = Svg(220, 220)
    with doc.group(cls="outer"):
        with doc.group(cls="inner"):
            doc.text("0", x=1, y=2, fill="#000", size=10)
    outer = [c for c in parse(doc) if c.tag.endswith("g")][0]
    assert outer.get("class") == "outer"
    assert outer[0].get("class") == "inner"
    assert outer[0][0].text == "0"


def test_an_unclosed_group_is_impossible_through_the_context_manager():
    doc = Svg(220, 220)
    with doc.group(cls="a"):
        pass
    assert doc.to_bytes().count(b"<g ") == doc.to_bytes().count(b"</g>")


def test_a_group_survives_an_exception_without_corrupting_the_document():
    doc = Svg(220, 220)
    with pytest.raises(RuntimeError):
        with doc.group(cls="a"):
            raise RuntimeError("boom")
    assert doc.to_bytes().count(b"<g ") == doc.to_bytes().count(b"</g>")


# --- エスケープ -------------------------------------------------------------

def test_text_content_is_escaped():
    doc = Svg(220, 220)
    doc.text("a & b < c", x=0, y=0, fill="#000", size=10)
    assert b"a &amp; b &lt; c" in doc.to_bytes()


def test_attribute_values_are_escaped():
    doc = Svg(220, 220)
    doc.text("x", x=0, y=0, fill='#000" onload="x', size=10)
    assert b'onload="x"' not in doc.to_bytes()
    assert parse(doc) is not None


def test_style_is_not_escaped_but_refuses_markup():
    # CSSに `<` や `&` を通すと文書構造が壊れる。エスケープすると今度は
    # CSSとして壊れるので、通さないことにする
    doc = Svg(220, 220)
    doc.style(".a{fill:#000}")
    assert b".a{fill:#000}" in doc.to_bytes()
    with pytest.raises(ValueError):
        doc.style("a{content:'<'}")


def test_comments_refuse_the_double_hyphen():
    doc = Svg(220, 220)
    doc.comment("Copyright 2026")
    assert b"<!-- Copyright 2026 -->" in doc.to_bytes()
    with pytest.raises(ValueError):
        doc.comment("a -- b")


def test_path_data_is_rejected_rather_than_escaped():
    # ここだけは文字列をそのまま流すので、壊れた図形を黙って出すより
    # 組み立て側の誤りとして落ちるほうがよい
    doc = Svg(220, 220)
    with pytest.raises(ValueError):
        doc.path('M0 0" x="', fill="#000")


# --- 決定性 -----------------------------------------------------------------

def build() -> bytes:
    doc = Svg(220, 220, title="t")
    doc.style(".a{fill:#000}")
    doc.clip_rect("win", x=10, y=20, width=100, height=48)
    with doc.group(cls="a", clip="win", transform="translate(1,2)"):
        doc.text("0", x=1.5, y=2, fill="#000", size=10)
    return doc.to_bytes()


def test_identical_construction_gives_identical_bytes():
    assert build() == build()


def test_integer_coordinates_carry_no_decimal_point():
    assert re.search(rb'\by="2"', build())
    assert not re.search(rb'\by="2\.0"', build())


def test_output_ends_with_a_single_newline():
    assert build().endswith(b"</svg>\n")
