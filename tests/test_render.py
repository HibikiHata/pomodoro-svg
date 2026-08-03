"""render の結合テスト。

部品はそれぞれ単体で検証済みなので、ここで見るのは**繋ぎ間違い**。
クラスを書いたのにキーフレームが無い、色を指定し忘れて既定の黒になる——
どちらも light では正しく見えて dark で沈む、という気づきにくい壊れ方をする。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from pomodoro.config import DESIGNS, MODES, Options
from pomodoro.render import CANVAS, render, variants
from pomodoro.theme import theme_of

ALL = [(design, mode) for design in DESIGNS for mode in MODES]


def svg(**kwargs) -> str:
    mode = kwargs.pop("mode", "light")
    return render(Options(**kwargs), mode).decode("utf-8")


# 同一プロセスで生成したバイト列のみを読む。外部実体もDTDも入る余地がない
def parse(text: str):
    return ET.fromstring(text)


@pytest.mark.parametrize("design,mode", ALL)
def test_every_design_and_mode_produces_well_formed_svg(design, mode):
    assert parse(svg(design=design, mode=mode)).tag.endswith("svg")


@pytest.mark.parametrize("design", DESIGNS)
def test_the_canvas_matches_the_declared_size(design):
    root = parse(svg(design=design))
    width, height = CANVAS[design]
    assert root.get("viewBox") == f"0 0 {width} {height}"


# --- 繋ぎの検査 -------------------------------------------------------------

def animation_rules(text: str) -> dict[str, list[str]]:
    """セレクタ -> そこで走らせているアニメーション名。カンマ区切りを展開する。

    `@media (prefers-reduced-motion)` の一括停止を先に外す。あれは全クラスを
    並べた1つの規則なので、素朴に拾うと最後のクラスの本来の指定を上書きする。
    """
    body_only = re.sub(r"@media[^{]*\{.*?\}\}", "", text, flags=re.S)
    rules: dict[str, list[str]] = {}
    for selector, value in re.findall(r"\.([\w-]+)\{animation:([^}]*)\}", body_only):
        rules[selector] = [part.strip().split()[0] for part in value.split(",")]
    return rules


@pytest.mark.parametrize("design,mode", ALL)
def test_every_animated_class_has_matching_keyframes(design, mode):
    # `.x{animation:x ...}` と `@keyframes x` の対応。片方だけ直したときに落ちる
    text = svg(design=design, mode=mode)
    used = {name for names in animation_rules(text).values() for name in names}
    defined = set(re.findall(r"@keyframes ([\w-]+)\{", text))
    assert used and used == defined


@pytest.mark.parametrize("design,mode", ALL)
def test_no_element_carries_two_animation_declarations(design, mode):
    """**`animation` は加算されない。** 同じ要素に当たる2つのクラスがそれぞれ
    `animation` を持つと、後の宣言が前を丸ごと置き換える。

    実際にこれで壊れた——`class="ring hue"` に `.ring{animation:ring}` と
    `.hue{animation:hue}` を書いたところ、色の切り替えがリングの減少を打ち消し、
    **リングが止まって見えた**。CSSとしては妥当で、静止画では気づけない。
    2つ以上載せるならカンマ区切りの1宣言にまとめること。
    """
    text = svg(design=design, mode=mode)
    animated = set(animation_rules(text))
    for value in re.findall(r'class="([^"]+)"', text):
        carried = [name for name in value.split() if name in animated]
        assert len(carried) <= 1, f'class="{value}" に animation が {carried}'


@pytest.mark.parametrize("design,mode", ALL)
def test_the_ring_both_drains_and_changes_colour(design, mode):
    # 減少と色替えは同じ要素に載る。片方しか走らないのがまさに上の壊れ方
    if design in ("minimal", "matrix"):
        return              # minimal は単色、matrix はリングもバーも持たない
    names = animation_rules(svg(design=design, mode=mode)).get("ring", [])
    assert "ring" in names and "hue" in names


@pytest.mark.parametrize("design,mode", ALL)
def test_every_animated_class_is_actually_attached_to_an_element(design, mode):
    text = svg(design=design, mode=mode)
    animated = set(re.findall(r"\.([\w-]+)\{animation:", text))
    attached: set[str] = set()
    for value in re.findall(r'class="([^"]+)"', text):
        attached.update(value.split())
    assert animated <= attached, animated - attached


#: 残り時間を数字で出すデザイン。`ring` と `minimal` は出さない（長さだけ）
DIGIT_DESIGNS = ("odometer", "digital", "matrix")


@pytest.mark.parametrize("design", DIGIT_DESIGNS)
@pytest.mark.parametrize("mode", MODES)
def test_the_digit_group_sets_both_colour_and_size(design, mode):
    # 帯の <text> は装飾属性を一切持たない（`strip` は幾何だけを扱う）。
    # **どちらを忘れても静かに壊れる**——fill を忘れれば暗色テーマで沈み、
    # font-size を忘れれば既定の16pxで描かれ、コロンだけが正しい大きさに見える。
    # 後者を実際にやった
    rule = re.search(r"\.digits\{([^}]*)\}", svg(design=design, mode=mode)).group(1)
    assert f"fill:{theme_of('default', mode).fg}" in rule
    assert re.search(r"font-size:[\d.]+px", rule), rule


@pytest.mark.parametrize("design", DIGIT_DESIGNS)
def test_the_digits_are_drawn_at_the_size_the_design_asked_for(design):
    # 16pxのまま出ていないこと。既定値と一致していたら疑う
    rule = re.search(r"\.digits\{([^}]*)\}", svg(design=design)).group(1)
    size = float(re.search(r"font-size:([\d.]+)px", rule).group(1))
    assert size >= 30, size


def painted(root):
    """実際に塗られる要素だけを辿る。

    `<defs>` の中身は切り抜きの形であって描かれない。`fill` を持たなくて正しい
    ので、ここを数えると本当の塗り忘れが埋もれる。
    """
    for child in root:
        if child.tag.split("}")[-1] == "defs":
            continue
        yield child
        yield from painted(child)


@pytest.mark.parametrize("design,mode", ALL)
def test_no_painted_element_relies_on_the_default_black_fill(design, mode):
    for element in painted(parse(svg(design=design, mode=mode))):
        tag = element.tag.split("}")[-1]
        if tag in ("circle", "rect", "path"):
            # text は包むグループから継承するので自前の fill を持たなくてよい
            assert element.get("fill") is not None, tag


# --- テーマ -----------------------------------------------------------------

def test_light_and_dark_actually_differ():
    pair = variants(Options())
    assert pair["light"] != pair["dark"]


@pytest.mark.parametrize("design", DESIGNS)
def test_the_background_colour_comes_from_the_theme(design):
    assert theme_of("default", "dark").bg in svg(design=design, mode="dark")


def test_variants_covers_both_modes():
    assert set(variants(Options())) == set(MODES)


# --- 内容 -------------------------------------------------------------------

def test_the_phase_label_is_drawn_in_the_requested_locale():
    assert "FOCUS" in svg(locale="en")


def test_an_unsupported_locale_is_refused_rather_than_drawn_as_tofu():
    # 日本語は落とした。要求されたら描く前に落ちる——サブセットに無い字を
    # 黙って描くとブラウザが豆腐を出す
    with pytest.raises(ValueError):
        svg(locale="ja")


def test_the_font_is_embedded_exactly_once():
    # 二重に入ると素材の大半が重複してファイルが倍になる
    assert svg().count("@font-face") == 1


def test_the_licence_notice_travels_with_the_font():
    # 生成物はフォント本体の複製。OFL 1.1 は各複製に表示を求める
    assert "SIL Open Font License" in svg()


def test_the_set_dots_disappear_when_sets_are_switched_off():
    assert "d0{" in svg(sets=4)
    assert "d0{" not in svg(sets=0)


def test_a_one_shot_timer_does_not_loop_forever():
    assert "infinite" in svg(repeat="loop")
    assert "infinite" not in svg(repeat="once")
    assert "forwards" in svg(repeat="once")


# --- 予算と決定性 -----------------------------------------------------------

#: 1枚あたりの上限。90/20 は分の停止点が458個になり、25/5 の3倍以上になる。
#: 自己完結SVGなので約10KBはフォントで、残りがキーフレーム。
BUDGET = 48 * 1024


@pytest.mark.parametrize("design", DESIGNS)
def test_the_file_stays_within_a_sane_budget(design):
    assert len(render(Options(design=design), "light")) < BUDGET


def test_every_shipped_variant_stays_within_budget():
    # **既定のスケジュールだけを測っていた。** 配布するのは 90/20 を含む80枚で、
    # そのうち16枚が旧予算(32KB)を超えていた。測る対象を配る対象に一致させる
    from pomodoro._generate.gen_variants import SCHEDULES
    for work, rest, long_rest in SCHEDULES:
        for design in DESIGNS:
            options = Options(work=work, rest=rest, long_rest=long_rest,
                              design=design)
            for mode in MODES:
                size = len(render(options, mode))
                assert size < BUDGET, f"{options.slug}-{mode}: {size:,}B"


def test_identical_options_give_identical_bytes():
    assert render(Options(), "light") == render(Options(), "light")


def test_the_slug_distinguishes_what_actually_differs():
    assert Options().slug == "ring-25-5"
    assert Options(work=50, rest=10).slug == "ring-50-10"
    assert Options(palette="mono").slug == "ring-25-5-mono"


# --- 極端な設定 -------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"sets": 0},                                  # セット無し
    {"sets": 1},                                  # 1本で長い休憩へ
    {"sets": 12},                                 # 点が並ぶ
    {"work": 1, "rest": 1, "long_rest": 1},       # 最短
    {"work": 99, "rest": 99, "long_rest": 99},    # 表示できる最長
    {"repeat": "once"},
    {"palette": "terminal", "locale": "en"},
])
@pytest.mark.parametrize("design", DESIGNS)
def test_extreme_schedules_still_render(design, kwargs):
    # 位相が短いほど停止点は近づく。丸めで潰れるならここで落ちる
    assert parse(svg(design=design, **kwargs)).tag.endswith("svg")


def test_a_schedule_too_long_to_display_is_refused():
    with pytest.raises(ValueError):
        Options(work=100)


def test_a_long_break_shorter_than_the_short_one_is_refused():
    # 90/20 に既定の long_rest=15 を組み合わせると黙ってこうなる
    with pytest.raises(ValueError):
        Options(work=90, rest=20, long_rest=15)


def test_the_long_break_may_equal_the_short_one():
    assert Options(work=25, rest=5, long_rest=5).long_rest == 5


def test_the_long_break_is_unchecked_without_sets():
    # セットを使わないなら長い休憩は出番がない
    assert Options(rest=20, long_rest=1, sets=0).sets == 0


# --- 事前生成する組み合わせ -------------------------------------------------

def test_every_prebuilt_combination_is_constructible():
    from pomodoro._generate.gen_variants import SCHEDULES
    for work, rest, long_rest in SCHEDULES:
        for design in DESIGNS:
            Options(work=work, rest=rest, long_rest=long_rest, design=design)


def test_prebuilt_slugs_are_unique():
    # 衝突すると片方が黙って上書きされ、貼った人には別物が出る
    from pomodoro._generate.gen_variants import SCHEDULES
    slugs = [
        Options(work=w, rest=r, long_rest=lr, design=d).slug
        for w, r, lr in SCHEDULES for d in DESIGNS
    ]
    assert len(set(slugs)) == len(slugs)


def test_every_prebuilt_schedule_has_a_long_break_worth_the_name():
    from pomodoro._generate.gen_variants import SCHEDULES
    for work, rest, long_rest in SCHEDULES:
        assert long_rest >= rest, (work, rest, long_rest)


@pytest.mark.parametrize("design", DIGIT_DESIGNS)
def test_the_digit_group_centres_each_column(design):
    # `strip` は text-anchor を出さない。既定の start のままだと桁が右へずれ、
    # 一番右の桁が窓からはみ出して切れる
    rule = re.search(r"\.digits\{([^}]*)\}", svg(design=design)).group(1)
    assert "text-anchor:middle" in rule


def test_the_matrix_rain_is_already_falling_at_load():
    # 負の遅延が無いと、開いた直後の数秒は全列が画面の上に揃っていて何も降らない
    text = svg(design="matrix")
    delays = re.findall(r"\.r\d+\{animation:r\d+ \d+s linear (-[\d.]+)s", text)
    assert len(delays) >= 10
    assert all(float(value) < 0 for value in delays)


# --- 静止画（確認用） -------------------------------------------------------

def frozen(seconds, **kwargs) -> str:
    mode = kwargs.pop("mode", "light")
    return render(Options(**kwargs), mode, seconds).decode("utf-8")


@pytest.mark.parametrize("design", DESIGNS)
def test_a_frozen_render_carries_no_animation(design):
    text = frozen(1560, design=design)
    assert "@keyframes" not in text
    assert "animation:" not in text


def test_a_frozen_render_shows_the_phase_that_is_actually_running():
    # 25分待たずに休憩の見た目を確かめるための機能。トラックから導くので
    # 実際に動く絵と食い違わない
    assert ".l-rest{opacity:1}" in frozen(1560)          # 休憩の1分後
    assert ".l-work{opacity:1}" in frozen(60)            # 作業の1分後
    assert ".l-rest{opacity:1}" in frozen(7080)          # 長い休憩も同じ「休憩」


def test_a_finished_timer_shows_zero_and_says_it_is_done():
    # 「長い休憩 00:00」で固まると、休憩中なのか終わったのか読めない
    text = frozen(7800, design="odometer", repeat="once")
    offsets = re.findall(r"\.[ms]\d\{transform:translateY\((-?[\d.]+)px\)\}", text)[-4:]
    assert offsets == ["0", "0", "0", "0"]               # 00:00
    assert ".l-done{opacity:1}" in text
    assert ".l-rest{opacity:0}" in text


def test_a_looping_timer_never_says_it_is_done():
    # 終わらないタイマーに完了は無い
    assert ".l-done{opacity:1}" not in frozen(7799, design="odometer")
    assert "DONE" in frozen(7799, design="odometer")      # 字は置くが出さない


def test_a_finished_timer_is_not_coloured_as_if_still_working():
    # phase_track に折り返し用の終端を置くと、終わったタイマーが作業中の色で固まる
    text = frozen(7800, design="odometer", repeat="once")
    assert f".ring{{stroke:{theme_of('default', 'light').rest}}}" in text


def test_all_the_set_dots_are_lit_once_the_cycle_is_done():
    text = frozen(7800, design="odometer", repeat="once")
    assert re.findall(r"\.d\d\{opacity:([\d.]+)\}", text) == ["1", "1", "1", "1"]


def test_a_frozen_render_is_smaller_than_the_animated_one():
    still = len(render(Options(design="odometer"), "light", 1560))
    moving = len(render(Options(design="odometer"), "light"))
    assert still < moving


def test_a_frozen_render_interpolates_inside_a_transform():
    # 補間が裸の数値にしか効かないと、マトリックスの雨は全列が画面外の初期位置で
    # 固まる——静止画に雨が1粒も映らない
    text = frozen(1560, design="matrix", palette="terminal")
    columns = re.findall(r"\.r\d+\{transform:translateY\((-?[\d.]+)px\)\}", text)
    assert len(columns) >= 10
    assert len({value for value in columns}) > 1, "全列が同じ位置＝補間できていない"


def test_a_frozen_ring_is_partly_depleted():
    text = frozen(1560, design="odometer")
    offset = float(re.search(r"\.ring\{stroke-dashoffset:([\d.]+)\}", text).group(1))
    assert 0 < offset < 604          # 満ちても空でもない


# --- レイアウト -------------------------------------------------------------

@pytest.mark.parametrize("sets", [1, 4, 8, 12])
@pytest.mark.parametrize("design", DESIGNS)
def test_every_circle_stays_inside_the_canvas(design, sets):
    # 点は既定の間隔のまま並べると画面外へ出る。SVGとしては妥当なままなので
    # XMLの検査では捕まらない——digital は sets=8 から溢れていた
    width, height = CANVAS[design]
    for element in painted(parse(svg(design=design, sets=sets))):
        if not element.tag.endswith("circle"):
            continue
        cx, cy, r = (float(element.get(k)) for k in ("cx", "cy", "r"))
        assert -1 <= cx - r and cx + r <= width + 1, f"{design} sets={sets}: cx={cx}"
        assert -1 <= cy - r and cy + r <= height + 1, f"{design} sets={sets}: cy={cy}"


def test_too_many_sets_is_refused():
    with pytest.raises(ValueError):
        Options(sets=13)


# --- 動きの抑制 -------------------------------------------------------------

@pytest.mark.parametrize("design", DESIGNS)
def test_reduced_motion_stops_every_animation(design):
    # `<img>` 経由SVGのメディアクエリはOS設定に解決される。prefers-color-scheme では
    # それが欠陥だが、ここではそれが正しい挙動——この方式で正しく効く唯一のクエリ
    text = svg(design=design)
    block = re.search(r"@media \(prefers-reduced-motion:reduce\)\{([^}]*)\{animation:none\}\}", text)
    assert block, "reduced-motion の指定が無い"
    stopped = {name.lstrip(".") for name in block.group(1).split(",")}
    animated = set(re.findall(r"\.([\w-]+)\{animation:", text))
    assert animated == stopped


def test_a_frozen_render_needs_no_reduced_motion_block():
    assert "prefers-reduced-motion" not in frozen(1560, design="odometer")


# --- 受け入れ条件に対応するテスト -------------------------------------------

def test_the_static_defaults_show_the_start_of_the_cycle():
    """AC1。アニメーションが動かない環境でも t=0 の姿が読める。

    静的な既定値はCSSに書いてあるだけなので、`at()` と突き合わせないと
    「それらしい値」のまま食い違いうる。
    """
    from pomodoro.odometer import cell_offset
    from pomodoro.schedule import cycle
    from pomodoro.timeline import at

    text = svg(design="odometer")
    cell = float(re.search(r"\.digits\{[^}]*font-size:([\d.]+)px", text).group(1)) * 1.15
    remaining = at(cycle(25, 5, 4, 15), 0)[1]
    expected = {
        "m0": remaining // 600, "m1": (remaining // 60) % 10,
        "s0": (remaining % 60) // 10, "s1": remaining % 10,
    }
    for name, digit in expected.items():
        rule = re.findall(rf"\.{name}\{{transform:translateY\((-?[\d.]+)px\)\}}", text)[0]
        assert float(rule) == pytest.approx(cell_offset(digit, cell)), name


@pytest.mark.parametrize("design", DESIGNS)
def test_every_track_period_divides_the_cycle(design):
    """AC2。周期＝サイクル総和ではない——秒は10/60秒、雨は6〜16秒で回る。

    ただし**どの周期もサイクル総和を割り切る**必要がある。割り切れないと
    折り返しのたびに位相がずれ、1周ごとに表示が狂っていく。
    """
    from pomodoro.schedule import cycle, total_seconds

    total = total_seconds(cycle(25, 5, 4, 15))
    text = svg(design=design)
    pairs = re.findall(r"([\w-]+) (\d+)s (?:linear|step-end)", text)
    for name, duration in pairs:
        if re.fullmatch(r"r\d+", name):
            # 降る数字は装飾で、時刻とも位相とも無関係。周期が総和を割り切る
            # 必要はない——折り返しで跳んでも意味が壊れない
            continue
        assert total % int(duration) == 0, f"{name}: {duration}s"
        if not name.startswith("s"):        # 秒だけが10/60秒の独立ループ
            assert int(duration) == total, name


@pytest.mark.parametrize("design", DIGIT_DESIGNS)
def test_the_clip_window_admits_exactly_one_row(design):
    """AC4。窓の高さが行送りと一致していなければ、隣の桁が覗くか切れる。"""
    text = svg(design=design)
    window = re.search(r'<clipPath id="win"><rect [^>]*height="([\d.]+)"', text)
    assert window, "窓が無い"
    # 帯だけを見る。ラベルもマトリックスの雨も <text> なので、文書順で先頭から
    # 拾うと別のものを測ってしまう
    block = text[text.index('class="d digits"'):]
    rows = [float(y) for y in
            re.findall(r'<text x="[-\d.]+" y="([-\d.]+)">\d</text>', block)][:2]
    assert float(window.group(1)) == pytest.approx(rows[1] - rows[0]), \
        f"窓 {window.group(1)} と行送り {rows[1] - rows[0]} が一致しない"


def test_a_missing_glyph_fails_generation(monkeypatch):
    """AC5。足りないまま描くとブラウザが黙って豆腐を出す。落とすほうがよい。"""
    import pomodoro.render as render_module
    from pomodoro.fontembed import load_subset

    full = load_subset("noto-sans-jp")
    crippled = type(full)(family=full.family, data=full.data,
                          charset=frozenset("0123456789"), copyright=full.copyright)
    monkeypatch.setattr(render_module, "load_subset", lambda name: crippled)
    with pytest.raises(ValueError, match="サブセットに無い文字"):
        render(Options(), "light")


def test_the_break_and_the_long_break_share_one_label():
    """休憩の長さは残り時間とリングが示すので、語を分ける必要がない。

    語を分けると同じ状態に2つの見た目を与えることになり、フォントにも
    `長 い L N G` と空白を抱え込む。
    """
    assert svg().count(">BREAK<") == 1, "同じ字が二重に描かれている"
    assert "LONG" not in svg()


# --- 重なり（元の pomodoro.svg の不具合） -----------------------------------

def visible(text: str, prefix: str) -> list[str]:
    """`prefix` で始まるクラスのうち、その時刻に見えているもの。"""
    shown = []
    for name in re.findall(rf"\.({prefix}[\w-]+)\{{opacity:", text):
        rule = re.search(rf"\.{re.escape(name)}\{{opacity:([\d.]+)\}}", text)
        if rule and float(rule.group(1)) == 1:
            shown.append(name)
    return shown


@pytest.mark.parametrize("second", [0, 750, 1560, 7080, 7799])
def test_only_one_label_is_drawn_at_a_time(second):
    """元の `pomodoro.svg` は FOCUS / 25 MIN / FINISHED を同じ中心に3枚置いており、
    終了時に3つが重なって読めなくなっていた。不透明度で排他にしてあれば起きない。
    """
    text = frozen(second, design="ring")
    assert len(visible(text, "l-")) == 1
    assert len(visible(text, "u-")) <= 1


def test_the_finished_dial_shows_no_duration():
    # 「完了」に長さは無い。残すと終わったのに 15分 と出る
    text = frozen(7800, design="ring", repeat="once")
    assert visible(text, "l-") == ["l-done"]
    assert visible(text, "u-") == []


def test_the_dial_tells_the_two_breaks_apart_by_their_length():
    # ring には残り時間が無いが、2行目の長さで短い休憩と長い休憩を区別できる
    assert ">5 MIN<" in frozen(1560, design="ring")
    assert ">15 MIN<" in frozen(7080, design="ring")


def test_the_matrix_rain_is_phosphor_green_in_the_dark():
    # 本家に寄せる。明色では沈むのでテーマの色に任せる
    from pomodoro.render import RAIN_DARK
    assert f"fill:{RAIN_DARK}" in svg(design="matrix", mode="dark")
    assert RAIN_DARK not in svg(design="matrix", mode="light")


def test_the_designs_are_ordered_by_shape():
    # 確認ページも配布物もこの順に出る。円系が隣り合っていないと見比べにくい
    assert DESIGNS == ("ring", "odometer", "minimal", "digital", "matrix")


@pytest.mark.parametrize("design", ("ring", "minimal"))
def test_the_finished_label_sits_where_the_two_lines_were(design):
    """完了は2行目を持たない。他と同じ高さに置くと、消えた行のぶんの空白が
    下に残って重心が上にずれる。1行のときは2行ぶんの光学中心へ下げる。
    """
    baselines = {}
    for element in re.findall(r"<text\b[^>]*/?>", svg(design=design)):
        name = re.search(r'class="d ([\w-]+)"', element)
        y = re.search(r'\by="([-\d.]+)"', element)
        if name and y:
            baselines[name.group(1)] = float(y.group(1))
    assert baselines["l-work"] < baselines["l-done"] < baselines["u-work"]
