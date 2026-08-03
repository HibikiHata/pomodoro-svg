"""数値の文字列化。決定的出力の土台。

浮動小数の既定表現は環境やバージョンで揺れうる。揺れると、内容が同じでも
バイト列が変わって意味のない差分が出る。桁を固定して揺れを断つ。
"""
from __future__ import annotations


def format_number(value: float, digits: int = 3) -> str:
    """整数はそのまま、小数は固定桁で丸めて余分な0を落とす。"""
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def format_percent(value: float) -> str:
    """キーフレームの位置。整数でも `%` の前に小数点を残さない。

    刻み幅（`keyframes.EPSILON`＝1e-3%）の100倍の分解能（1e-5%）を持たせてある。同じ文字列に
    丸められた停止点は片方が消えるので、余裕を取る必要がある。
    """
    return f"{value:.5f}".rstrip("0").rstrip(".") or "0"
