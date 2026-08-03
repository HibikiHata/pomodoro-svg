"""pomodoro テスト共通設定。

実行時は PYTHONPATH=<repo>/src で `pomodoro` パッケージとして import されるため、
テストでも同じ import 形態に揃える（src. プレフィックスを使わない）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# <repo>/src を import パスへ追加（テストと実行時で import 名を一致させる）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
