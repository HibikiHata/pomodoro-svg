"""確認用の画像一式と、上から順に辿れる確認ページを作る（開発時のみ）。

    PYTHONPATH=src python3 -m pomodoro._generate.gen_preview

出力先は `preview/`（バージョン管理しない）。配布物は `dist/` で、そちらは
`gen_variants` が作る。

ポモドーロは**待たないと次の状態が見られない**。25分待たないと休憩が、7時間
待たないと完了が確認できないのでは、デザインの検討ができない。任意の時刻で
止めた静止画を位相ごとに出して、待ち時間ゼロで全部を見比べられるようにする。

静止画の値は `render._frozen` がトラックを評価して出す。**動く絵と同じ材料から
導くので、確認した絵と実際に動く絵が食い違わない**——別に組み立てると、そこが
必ずずれる。

**ページも同じ定義から生成する。** 画像を足したのにページに書き忘れる、という
ずれが起きないようにするため。カレンダーの gallery で同じ作りにしている。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pomodoro.config import DESIGNS, Options
from pomodoro.render import CANVAS, variants
from pomodoro.schedule import REST, WORK, cycle, total_seconds
from pomodoro.timeline import phase_stops

#: 位相の変わり目を実時間で見るための短縮版。1周4分なので2分眺めれば
#: 作業→休憩→作業まで確認できる
SHORT = Options(work=1, rest=1, sets=2, long_rest=1)

#: 確認したい瞬間。(識別子, 見出し, 説明)
MOMENTS: tuple[tuple[str, str, str], ...] = (
    ("start", "貼った直後", "t=0。利用者が最初に見る姿。リングは満ち、数字は満了時間"),
    ("work", "作業中", "1本目の折り返し。リングが半分、点はまだどれも薄い"),
    ("rest", "休憩", "1本終えた直後。色が休憩に変わり、点が1つ濃くなる"),
    # 長い休憩の瞬間は置かない。ラベルも色も短い休憩と同じで、点が全部濃い姿は
    # 「完了」で見られる——同じ絵を2枚並べても確認項目が増えない
    ("done", "完了", "1回きり設定の終端。`00:00` と専用の文言。**「長い休憩」のままだと休憩中と読めてしまう**"),
)


def instants(options: Options) -> dict[str, tuple[float, str]]:
    """各瞬間の (秒, repeat)。**位相の列から導く**ので設定を変えても追随する。

    どの瞬間も位相の**途中**を指す。固定の秒数を足すと、1分の位相では次の位相へ
    飛び出して別の絵を「休憩」として見せてしまう。

    存在しない位相の瞬間は返さない。`sets=1` には短い休憩が無い（作業の次が
    いきなり長い休憩）ので、無いものを長い休憩で代用すると同じ絵が2枚並ぶ。
    """
    phases = cycle(options.work, options.rest, options.sets, options.long_rest)
    stops = phase_stops(phases)
    total = total_seconds(phases)

    def midpoint(kind: str) -> int | None:
        for start, phase in stops:
            if phase.kind == kind:
                return start + phase.seconds // 2
        return None

    found = {"start": 0, "work": midpoint(WORK), "rest": midpoint(REST)}
    moments = {name: (second, "loop")
               for name, second in found.items() if second is not None}
    moments["done"] = (total, "once")
    return moments


def _write(out: Path, stem: str, options: Options,
           freeze: float | None = None) -> list[str]:
    written = []
    for mode, data in variants(options, freeze).items():
        (out / f"{stem}-{mode}.svg").write_bytes(data)
        written.append(f"{stem}-{mode}.svg")
    return written


def build(out: Path) -> tuple[int, int]:
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.svg"):
        stale.unlink()

    count = 0
    for design in DESIGNS:
        options = Options(design=design)
        count += len(_write(out, f"anim-{design}", options))
        for name, (second, repeat) in instants(options).items():
            frozen = Options(design=design, repeat=repeat)
            count += len(_write(out, f"{name}-{design}", frozen, second))
        # 位相の変わり目を実時間で見る短縮版。lightのみ（動きの確認なので）
        short = Options(design=design, work=SHORT.work, rest=SHORT.rest,
                        sets=SHORT.sets, long_rest=SHORT.long_rest)
        (out / f"short-{design}-light.svg").write_bytes(variants(short)["light"])
        count += 1

    (out / "README.md").write_text(page(), encoding="utf-8")
    total = sum(path.stat().st_size for path in out.glob("*.svg"))
    return count, total


def _row(prefix: str) -> list[str]:
    lines = ["| デザイン | light | dark |", "|---|---|---|"]
    for design in DESIGNS:
        width = CANVAS[design][0]
        lines.append(
            f"| `{design}` "
            f"| <img src=\"{prefix}-{design}-light.svg\" width=\"{width}\"> "
            f"| <img src=\"{prefix}-{design}-dark.svg\" width=\"{width}\"> |"
        )
    return lines


def page() -> str:
    default = Options()
    total = total_seconds(cycle(default.work, default.rest, default.sets,
                                default.long_rest))
    parts: list[str] = [
        "# ポモドーロ 動作確認",
        "",
        "**このページを github.com 上で開き、上から順に確認する。**",
        "ローカルのプレビューではブラウザの扱いが変わるので判定に使えない——",
        "実際、数字が既定の16pxで描かれていた欠陥はラスタライザでは再現せず、",
        "ブラウザで見て初めて確定した。",
        "",
        "| 段階 | 内容 | 所要 |",
        "|---|---|---|",
        "| 1 | デザイン確認（静止画） | **待ち時間なし** |",
        "| 2 | アニメーションが動くか | 1分 |",
        "| 3 | 位相の切り替わり | 2分 |",
        "| 4 | 裏タブ25分 | **25分**（放置なので拘束されない） |",
        "| 5 | ブラウザ差 | 任意 |",
        "",
        "---",
        "",
        "## 1. デザイン確認（待ち時間なし）",
        "",
        f"既定の設定（作業{default.work}分 / 休憩{default.rest}分 / "
        f"{default.sets}セット / 長い休憩{default.long_rest}分・日本語）。",
        "",
        "位相ごとに**その時刻で止めた静止画**を出してある。値は動く絵と同じ",
        "トラックから導いているので、ここで見た姿は実際にその時刻に出る姿と一致する。",
        "",
    ]
    for name, title, note in MOMENTS:
        parts += [f"### {title}", "", note, ""] + _row(name) + [""]

    parts += [
        "**見るところ**",
        "",
        "| 項目 | 期待 |",
        "|---|---|",
        "| 桁 | `25:00` が中央で揃い、右端が切れていない |",
        "| コロン | 数字の**上下中央**にある |",
        "| 暗色 | 数字が背景に沈んでいない |",
        "| 色 | 作業＝赤系、休憩＝緑系、長い休憩＝青系 |",
        "| 点 | 作業中は薄く、1本終えるごとに左から濃くなる |",
        "| 完了 | `00:00` と「完了」。リングは空 |",
        "| `minimal` | 点が無いのは**意図どおり**（README帯で主張しないため） |",
        "",
        "---",
        "",
        "## 2. アニメーションが動くか（1分）",
        "",
        "ここから下は**動く画像**。開いた瞬間が開始なので `25:00` から減る。",
        "",
    ] + _row("anim") + [
        "",
        "| 見るところ | 期待 | 失敗の見え方 |",
        "|---|---|---|",
        "| 秒の一番右の桁 | **1秒ごとにカクッと切り替わる** | 滑らかに動く＝`steps()` が効いていない |",
        "| リング／バー | 12時から時計回りに減る | 増える・動かない |",
        "| `matrix` の雨 | 開いた直後から降っている | 数秒間なにも降らない＝負の遅延が効いていない |",
        "| 数字の大きさ | リングや板に対して十分大きい | 小さすぎる＝`font-size` の継承が切れている |",
        "",
        "---",
        "",
        "## 3. 位相の切り替わり（2分）",
        "",
        "既定は25分待たないと休憩に入らないので、**1分/1分・2セット**の短縮版を置く。",
        "1周4分なので、2分眺めれば 作業→休憩→作業 まで見える。",
        "",
        "| デザイン | 短縮版（1分/1分・2セット） |",
        "|---|---|",
    ]
    for design in DESIGNS:
        parts.append(f"| `{design}` | <img src=\"short-{design}-light.svg\" "
                     f"width=\"{CANVAS[design][0]}\"> |")
    parts += [
        "",
        "| 見るところ | 期待 |",
        "|---|---|",
        "| 1分経過 | ラベルが「集中」→「休憩」、色が変わる |",
        "| 同時 | リングが**巻き戻って満ちる**（減り続けない） |",
        "| 同時 | 点が1つ濃くなる |",
        "| 2分経過 | また「集中」に戻る |",
        "",
        "---",
        "",
        "## 4. 裏タブ25分 — **これが本番の検証**",
        "",
        "**設計の根幹がここに懸かっている。** 「読み込んだ瞬間が開始」で成立するのは、",
        "裏タブでもタイマーが実時間で進む場合だけ。spike では**3分しか測っていない**。",
        "",
        "Chrome の Memory Saver は、メモリ逼迫時に限らず**バックグラウンドで一定時間",
        "使われていないタブを能動的に破棄**し、戻ると**自動でリロード**する。",
        "破棄されたタイマーは `25:00` を表示する——**開始直後と見分けがつかない**。",
        "JSが使えないので検出も復帰もできず、対処は文書に書くことだけになる。",
        "",
        "**手順**",
        "",
        "1. 上の「2. アニメーション」の `odometer` の値をメモする（例 `24:37`）と同時に時刻もメモ",
        "2. **別のタブに切り替える**（別ウィンドウを手前に出すだけでは不十分。背面タブにする）",
        "3. **25分放置**する。このタブに触らない",
        "4. 戻って値を読む",
        "",
        "**判定**",
        "",
        "| 読み | 意味 |",
        "|---|---|",
        "| メモした値から**25分進んでいる** | **設計どおり。** 裏で作業していてもタイマーが正しい |",
        "| **`25:00` 付近に戻っている** | **タブが破棄されリロードされた。** READMEに制限として明記が必要 |",
        "| 進んでいるが**25分未満** | 再生が間引かれている。25分のタイマーが実時間で長くなる |",
        "",
        "余裕があれば、Chrome の設定で Memory Saver を **Maximum** にして再度。",
        "既定（Balanced）で起きなくても、設定次第で起きるなら制限として書く必要がある。",
        "",
        "---",
        "",
        "## 5. ブラウザ差（任意）",
        "",
        "ここまで全部 Chrome の話。**Safari は `<img>` 経由SVGのメディアクエリで",
        "前例がある**ので、少なくとも 1 と 2 は見ておきたい。",
        "",
        "| ブラウザ | 1 デザイン | 2 アニメーション | 4 裏タブ |",
        "|---|---|---|---|",
        "| Chrome | | | |",
        "| Safari | | | |",
        "| Firefox | | | |",
        "",
        "---",
        "",
        "## 結果（確認したら埋める）",
        "",
        "| # | 項目 | 結果 | 備考 |",
        "|---|---|---|---|",
        "| 1 | デザイン（5種 × light/dark × 5状態） | | |",
        "| 2 | アニメーションが動く | | |",
        "| 3 | 位相の切り替わり | | |",
        "| 4 | **裏タブ25分** | | |",
        "| 5 | Safari / Firefox | | |",
        "",
        "---",
        "",
        "## 再生成",
        "",
        "```",
        "PYTHONPATH=src python3 -m pomodoro._generate.gen_preview",
        "```",
        "",
        "画像もこのページも同じ定義から作る（`_generate/gen_preview.py`）。",
        "画像を足したのにページに書き忘れる、というずれが起きないようにするため。",
        f"既定の1周期は {total} 秒。位相の時刻は設定から導くので、既定を変えても追随する。",
        "",
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="確認用の画像とページを作る")
    parser.add_argument("--out", type=Path, default=Path("preview"))
    args = parser.parse_args(argv)
    count, total = build(args.out)
    print(f"{count}枚 + README.md / 合計 {total / 1024:.0f}KB → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
