# Conventions

- 全モジュール冒頭に `from __future__ import annotations`。型ヒントは `str | None` 等 PEP 604 スタイル（Python 3.10+ 前提）。
- モジュール冒頭 docstring には設計意図（そのモジュールが守る安全上の制約）を書く。関数レベルは非自明な場合のみ。
- 状態ファイルへの書き込みは必ず `.tmp` に書いてから `os.replace`。直接書き込み・既存行の書き換えは禁止（`signal.jsonl` / `sent.jsonl` / `eod.jsonl` / `halt_log.jsonl` は追記専用）。
- 冪等性はファイル内のキー照合で担保する: `sender_gate` は `time_utc`、`eod_close` は日付キー、`halt_check` は5分スロットキー。処理前に必ず既存記録を照合する。
- パス解決は `lib/paths.py` に一元化。`LIVE_DYNAMIC_DATA`（state/logs/env）と `MARKET_DATA`(bars/tokens) の2ルート以外を参照しない。ハードコードパス禁止。
- 設定・資格情報は env ファイル（`.env.trade.base` → `.env.live_dynamic` の順、プロセス環境変数が優先）と `$BT_DYNAMIC_CONFIG` の config JSON から注入する。コード内デフォルトに接続先・戦略値を置かない。
- ブローカー API は `lib/broker_client.py`（発注・ポジション）と `lib/chart_client.py`（チャート）のみが呼ぶ。urllib 標準ライブラリのみ。ペイロードのフィールド名はブローカーの REST スキーマに従う（変えない）。
- ドメイン非依存の抽象名を使う: `ax1` = トレンド強度、`ax2` = ボラティリティ、`direction` = 方向オシレーター（bt-dynamic の規約を踏襲）。具体指標名（ADX/ATR/RSI）を実行層に書かない。
- 例外方針: 発注経路では例外を握りつぶさず記録して失敗として返す。読み取り経路（jsonl パース・フラグ読み込み）は壊れた行をスキップして継続する。
- テストは `tests/test_{module}.py`。一時ディレクトリ + monkeypatch の env 差し替えで書き、ネットワーク・資格情報に依存させない。浮動小数比較は `pytest.approx`。
