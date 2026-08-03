"""SVGを組み立てる最小の道具。

外部ライブラリを使わないのは、配布物の実行時依存をゼロにするため。属性の
並び順を各メソッド内で固定しているのは、順序が揺れると意味のない差分が出て
「何が変わったのか」が読めなくなるため。

カレンダー版との違いは `<defs>` / `<clipPath>` / 入れ子の `<g>` を扱えること。
オドメーターの窓がそれで出来ている。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from pomodoro.numbers import format_number

# 置換順は & が先。後にすると既に入れた &amp; の & を二重に置換してしまう。
_ESCAPES = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&apos;"),
)


def escape_text(value: object) -> str:
    """SVGに埋める文字列をXMLエスケープする。

    設定値・ロケール文字列・将来の利用者入力がそのまま流れ込むため、描画側で
    一括して通す（呼び出し側の記憶に頼らない）。
    """
    out = str(value)
    for source, target in _ESCAPES:
        out = out.replace(source, target)
    return out


class Svg:
    """要素を追加した順に直列化するだけの器。"""

    def __init__(self, width: int, height: int, title: str | None = None,
                 desc: str | None = None) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"サイズは正の数である必要があります: {width}x{height}")
        self.width = width
        self.height = height
        self.title = title
        self.desc = desc
        self._defs: list[str] = []
        self._body: list[str] = []
        self._style: str | None = None
        self._background: str | None = None
        self._clip_ids: set[str] = set()
        self._depth = 0

    # --- 参照される側 -------------------------------------------------------

    def clip_rect(self, ident: str, *, x: float, y: float,
                  width: float, height: float) -> None:
        """1つの矩形だけを持つ `<clipPath>` を `<defs>` に置く。

        重複したidを後勝ちで黙って上書きすると、片方の窓だけが正しく切られる
        という気づきにくい壊れ方をするので拒否する。
        """
        if ident in self._clip_ids:
            raise ValueError(f"clipPath のidが重複しています: {ident!r}")
        self._clip_ids.add(ident)
        self._defs.append(
            f'<clipPath id="{escape_text(ident)}">'
            f'<rect x="{format_number(x)}" y="{format_number(y)}" '
            f'width="{format_number(width)}" height="{format_number(height)}"/>'
            f"</clipPath>"
        )

    # --- 構造 ---------------------------------------------------------------

    @contextmanager
    def group(self, *, cls: str | None = None, clip: str | None = None,
              transform: str | None = None) -> Iterator[None]:
        """`<g>` を開いて閉じる。

        文脈管理子にしているのは閉じ忘れを構文上不可能にするため。途中で例外が
        出ても閉じタグは出る——半端な文書を返すより、閉じたうえで例外を投げる。
        """
        if clip is not None and clip not in self._clip_ids:
            raise ValueError(
                f"未宣言の clipPath を参照しています: {clip!r}。"
                "先に clip_rect() で宣言してください"
            )
        attrs = ""
        if cls:
            attrs += f' class="{escape_text(cls)}"'
        if clip:
            attrs += f' clip-path="url(#{escape_text(clip)})"'
        if transform:
            attrs += f' transform="{escape_text(transform)}"'
        self._body.append(f"<g{attrs}>")
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            self._body.append("</g>")

    # --- 図形 ---------------------------------------------------------------

    def rect(self, *, x: float, y: float, width: float, height: float,
             fill: str, rx: float = 0, stroke: str | None = None,
             stroke_width: float = 1, cls: str | None = None) -> None:
        attrs = (f'x="{format_number(x)}" y="{format_number(y)}" '
                 f'width="{format_number(width)}" height="{format_number(height)}" '
                 f'fill="{escape_text(fill)}"')
        if rx:
            attrs += f' rx="{format_number(rx)}"'
        if stroke:
            attrs += (f' stroke="{escape_text(stroke)}" '
                      f'stroke-width="{format_number(stroke_width)}"')
        if cls:
            attrs += f' class="{escape_text(cls)}"'
        self._body.append(f"<rect {attrs}/>")

    def circle(self, *, cx: float, cy: float, r: float, fill: str,
               cls: str | None = None, stroke: str | None = None,
               stroke_width: float = 1) -> None:
        attrs = (f'cx="{format_number(cx)}" cy="{format_number(cy)}" '
                 f'r="{format_number(r)}" fill="{escape_text(fill)}"')
        if stroke:
            attrs += (f' stroke="{escape_text(stroke)}" '
                      f'stroke-width="{format_number(stroke_width)}"')
        if cls:
            attrs += f' class="{escape_text(cls)}"'
        self._body.append(f"<circle {attrs}/>")

    def text(self, content: str, *, x: float, y: float, fill: str, size: float,
             anchor: str = "middle", weight: str = "normal",
             family: str | None = None, cls: str | None = None,
             opacity: float | None = None) -> None:
        attrs = (f'x="{format_number(x)}" y="{format_number(y)}" '
                 f'fill="{escape_text(fill)}" font-size="{format_number(size)}" '
                 f'text-anchor="{escape_text(anchor)}"')
        if weight != "normal":
            attrs += f' font-weight="{escape_text(weight)}"'
        if family:
            attrs += f' font-family="{escape_text(family)}"'
        if cls:
            attrs += f' class="{escape_text(cls)}"'
        if opacity is not None:
            attrs += f' opacity="{format_number(opacity)}"'
        self._body.append(f"<text {attrs}>{escape_text(content)}</text>")

    def path(self, d: str, *, fill: str, stroke: str | None = None,
             stroke_width: float = 1, cls: str | None = None) -> None:
        """パス。`d` は呼び出し側が組み立てた座標列。

        属性値に割り込める文字を弾く。ここだけは文字列をそのまま流すので、
        エスケープではなく**拒否**にしている（壊れた図形を黙って出すより、
        組み立て側の誤りとして落ちるほうがよい）。
        """
        if any(character in d for character in '<>"&'):
            raise ValueError(f"パスに使えない文字が含まれています: {d!r}")
        attrs = f'd="{d}" fill="{escape_text(fill)}"'
        if stroke:
            attrs += (f' stroke="{escape_text(stroke)}" '
                      f'stroke-width="{format_number(stroke_width)}"')
        if cls:
            attrs += f' class="{escape_text(cls)}"'
        self._body.append(f"<path {attrs}/>")

    def raw(self, fragment: str) -> None:
        """組み立て済みの断片をそのまま置く（オドメーターの帯など）。"""
        self._body.append(fragment)

    # --- 付随物 -------------------------------------------------------------

    def style(self, css: str) -> None:
        """`<style>` を置く。**呼ぶ順序に関係なく文書の先頭に出る。**

        規則は中身を組み立て終えるまで決まらないのに、出力では前に無いといけない。
        置き場を分けておけば、描画のあとで渡せる。

        CSSはエスケープしない。`<` や `&` を通すと文書構造が壊れ、エスケープすると
        今度はCSSとして壊れる。どちらにも倒れないので、含めないことを条件にする。
        """
        if "<" in css or "&" in css:
            raise ValueError("style に < や & は入れられません")
        if self._style is not None:
            raise ValueError("style は1文書に1つだけです")
        self._style = css

    def background(self, fill: str) -> None:
        """画面全体の下地。`style` と同じく、順序によらず本文の手前に出る。"""
        if self._background is not None:
            raise ValueError("background は1文書に1つだけです")
        self._background = fill

    def comment(self, text: str) -> None:
        """XMLコメントを1つ置く。フォントの著作権表示など。"""
        if "--" in text or "<" in text or ">" in text:
            raise ValueError("コメントに -- や山括弧は入れられません")
        self._body.append(f"<!-- {text} -->")

    # --- 直列化 -------------------------------------------------------------

    def to_bytes(self) -> bytes:
        if self._depth:
            raise ValueError(f"閉じていないグループがあります: {self._depth}")
        head = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}"'
            + (' role="img"' if self.title else "")
            + ">"
        ]
        if self.title:
            head.append(f"<title>{escape_text(self.title)}</title>")
        if self.desc:
            head.append(f"<desc>{escape_text(self.desc)}</desc>")
        if self._defs:
            head.append("<defs>" + "".join(self._defs) + "</defs>")
        if self._style is not None:
            head.append(f"<style>{self._style}</style>")
        if self._background is not None:
            head.append(
                f'<rect x="0" y="0" width="{self.width}" height="{self.height}" '
                f'fill="{escape_text(self._background)}"/>'
            )
        return ("".join(head + self._body) + "</svg>\n").encode("utf-8")
