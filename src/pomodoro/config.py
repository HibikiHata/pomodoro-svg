"""利用者が渡せる設定。

**サイズは持たない。** SVGはベクターなので、大きさは貼る側の `<img width>` で
決めればよく、ファイルに焼き込む理由がない。焼き込むとバリアントが縦に増える。

**`digits` も持たない。** 「リング＋数字」はオドメーターそのもので、デザインの
選択と重複する。オプションが2つの経路で同じ絵を指せる状態は、片方が必ず腐る。
"""
from __future__ import annotations

from dataclasses import dataclass

from pomodoro.labels import LOCALES
from pomodoro.theme import PALETTES

#: 並びは**形の近さ**で決める。確認ページも配布物もこの順に出るので、円系を
#: 隣に置いたほうが見比べやすい
DESIGNS: tuple[str, ...] = ("ring", "odometer", "minimal", "digital", "matrix")
REPEATS: tuple[str, ...] = ("loop", "once")
MODES: tuple[str, ...] = ("light", "dark")

#: 分の表示は2桁。ここを超えると桁があふれて別の時刻に見える
MAX_MINUTES = 99

#: セットの点はキャンバスに収める必要がある。`render._dots` が間隔を詰めて
#: 収めるが、詰めきると点が判別できなくなるので上限も設ける
MAX_SETS = 12


@dataclass(frozen=True)
class Options:
    work: int = 25
    rest: int = 5
    sets: int = 4
    long_rest: int = 15
    repeat: str = "loop"
    design: str = "ring"
    palette: str = "default"
    locale: str = "en"

    def __post_init__(self) -> None:
        _one_of("repeat", self.repeat, REPEATS)
        _one_of("design", self.design, DESIGNS)
        _one_of("palette", self.palette, tuple(sorted(PALETTES)))
        _one_of("locale", self.locale, LOCALES)
        # 長さそのものの検証は schedule.cycle が持つ。ここでは表示できるかを見る
        for name in ("work", "rest", "long_rest"):
            value = getattr(self, name)
            if isinstance(value, int) and value > MAX_MINUTES:
                raise ValueError(
                    f"{name} は{MAX_MINUTES}分以下である必要があります: {value}。"
                    "分の表示は2桁しかない"
                )
        if isinstance(self.sets, int) and not isinstance(self.sets, bool) \
                and self.sets > MAX_SETS:
            raise ValueError(
                f"sets は{MAX_SETS}以下である必要があります: {self.sets}。"
                "点が詰まりすぎて数えられない"
            )
        # 「長い休憩」が短い休憩より短いのは言葉として破綻している。90/20 のような
        # 長いスケジュールで既定の15分を引きずると、黙ってこの状態になる
        if self.sets > 0 and isinstance(self.long_rest, int) \
                and isinstance(self.rest, int) and self.long_rest < self.rest:
            raise ValueError(
                f"long_rest は rest 以上である必要があります: "
                f"{self.long_rest} < {self.rest}"
            )

    @property
    def slug(self) -> str:
        """ファイル名に使う識別子。`sets` と `repeat` は既定なら省く。

        貼るだけの人が見るのはURLなので、既定から外れた部分だけが名前に出る
        ようにする。全部を並べると `pomodoro-ring-25-5-4-15-loop-ja-...` になる。
        """
        parts = [self.design, str(self.work), str(self.rest)]
        if self.repeat != "loop":
            parts.append(self.repeat)
        if self.palette != "default":
            parts.append(self.palette)
        if self.locale != "en":
            parts.append(self.locale)
        return "-".join(parts)


def _one_of(name: str, value: object, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} は {'/'.join(allowed)} のいずれかです: {value!r}")
