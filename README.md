# live-dynamic

[bt-dynamic](https://github.com/yktsnet/bt-dynamic)（動的レジーム切替バックテスト）で検証した戦略を、ブローカーの OpenAPI に接続して systemd timer で無人運転する実弾実行層。バックテストと同じ config JSON を読むので、研究側で回した設定がそのまま本番の判定になる。

> **免責**: 本リポジトリは自動売買の運用設計を示す参照実装であり、投資助言ではない。実弾での利用は自己責任で行うこと。既定は dry_run（発注しない）であり、実発注には明示的な切替が必要。

## 設計の核

戦略のエッジ（セル対応表・閾値・TP/SL・通貨ペア）はこのリポには存在しない。すべて config / env の外部注入で、リポが持つのは実行層の安全設計だけである。

- **冪等性**: 送信済み記録（`sent.jsonl`）と `time_utc` を照合し、同じ判定スロットでは二度発注しない
- **dry_run 既定**: `ENABLE_EXEC_REQUESTS=0` が既定。切替は env ファイル1行、再起動不要
- **多層フェイルセーフ**: エントリー直後の OCO（TP/SL）自動配置、セッション終了時の EOD 強制決済、外部キルスイッチの三段構え
- **キルスイッチ**: `state/halt_flags.jsonl` にフラグを1行追記すれば、シグナル生成が止まり、ポジションは5分以内に強制決済される。書き込むのが異常検知システムでもエディタを開いた人間でもよい
- **運用の規律**: すべての状態ファイルは atomic write（`.tmp` → `os.replace`）・追記専用。ブローカー API 呼び出しは `lib/broker_client.py`（標準ライブラリのみ）に一元化

## 稼働仕様

| 項目 | 内容 |
|---|---|
| データ | 5分足（`MARKET_DATA/bars/`） |
| 判定 | 30分ごと（config の `bars_per_window` から導出） |
| ポジション | 単一銘柄・単一ポジション |
| OCO | エントリー後に TP/SL 注文を自動配置 |
| セッション | UTC 00:00 〜 `trade_end_hour` |
| EOD | セッション終了時に強制全決済 |
| キルスイッチ | halt フラグ検知で即時全決済（5分間隔） |
| トークン | 5分ごとに自動リフレッシュ |

## 構成

```
live-dynamic/
  core/          # 実行スクリプト（systemd timer から oneshot 起動）
    orchestrator.py   # build_signal → sender_gate をシーケンス実行
    build_signal.py   # バー読込 → 戦略判定 → signal.jsonl 追記（ブローカー非接続）
    sender_gate.py    # 最新シグナルを冪等に発注し sent.jsonl に記録
    halt_check.py     # halt フラグ監視 → 全決済
    eod_close.py      # セッション終了時の強制全決済
    token_refresh.py  # アクセストークンのリフレッシュ
    fetch_bars.py     # 5分足の取得・保存
  lib/           # 自己完結ライブラリ（外部依存は pandas のみ、API 層は標準ライブラリ）
  strategies/    # bt-dynamic パッケージへの接続層（エッジは config 注入）
  examples/      # ダミー config と合成バー生成（デモ・検証用）
  live-dynamic-service.nix  # systemd サービス / timer 定義（NixOS / home-manager）
```

シグナル生成（`build_signal`）と発注（`sender_gate`）は意図的に分離している。前者はブローカーに一切接続しないため、資格情報なしで検証でき、dry_run では後者もネットワークに出ない。

## 動かす（dry_run）

```bash
pip install -r requirements.txt

export LIVE_DYNAMIC_DATA=~/live_dynamic_data
export MARKET_DATA=~/market_data
export BT_DYNAMIC_CONFIG=examples/config.json
export PYTHONPATH=.

# 合成バーを生成（実データ不要）
python examples/generate_bars.py

# 判定 → 発注ゲート（既定 dry_run なので発注されない）
python core/orchestrator.py

cat $LIVE_DYNAMIC_DATA/state/signal.jsonl   # 戦略判定の出力
cat $LIVE_DYNAMIC_DATA/state/sent.jsonl     # dry_run=true の送信記録
```

## テスト

```bash
pip install -r requirements.txt pytest
PYTHONPATH=. pytest tests -q
```

冪等な送信ゲート・キルスイッチ判定・バー読込・戦略の判定ゲートを、すべて一時ディレクトリ + 合成データで検証する（ネットワーク・資格情報は不要）。

## 実弾運用の設定

`$LIVE_DYNAMIC_DATA/env/.env.trade.base` に接続情報を書く（**以下はすべてダミー値**）:

```
ACCOUNT_KEY=xxxx
CLIENT_KEY=xxxx
BROKER_CLIENT_ID=xxxx
BROKER_AUTH_BASE=https://auth.example-broker.com
BROKER_REDIRECT_URI=http://localhost:8080/callback
BROKER_API_BASE=https://api.example-broker.com/openapi
INSTRUMENT_ID=999
ASSET_TYPE=FxSpot
LOT_SIZE=10000
PIP_SIZE=0.01
TICK_SIZE=0.001
RR_PIPS_TP=20
RR_PIPS_SL=10
BT_DYNAMIC_CONFIG=/path/to/your/config.json
```

接続先 URL はコードにデフォルトを持たない。env に書かなければ動かない設計である。

`$LIVE_DYNAMIC_DATA/env/.env.live_dynamic` で発注を制御する:

```
ENABLE_EXEC_REQUESTS=0   # dry_run（既定）。1 で実発注
LOT_BASE=0.1
```

## キルスイッチ

`$LIVE_DYNAMIC_DATA/state/halt_flags.jsonl` に追記する:

```
{"ts": "2026-01-05T09:00:00Z"}                                # その UTC 日を停止
{"start": "2026-01-05T12:00:00Z", "end": "2026-01-05T14:00:00Z"}  # 時間帯を停止
{"start": "2026-01-05T12:00:00Z"}                             # 以降ずっと停止
```

停止中は `build_signal` がシグナルを出さず、`halt_check`（5分間隔）が建玉を強制決済する。

## systemd での無人運転

`live-dynamic-service.nix` を NixOS / home-manager 構成に取り込む:

```nix
services.live-dynamic = {
  enable = true;
  user = "youruser";
  appRoot = "/home/youruser/live-dynamic";
  dataRoot = "/home/youruser/live_dynamic_data";
  marketDataRoot = "/home/youruser/market_data";
  orchestrator = true;   # 月-金 30分ごと（セッション内）
  haltCheck = true;      # 月-金 5分ごと
  eodClose = true;       # 月-金 セッション終了時
  tokenRefresh = true;   # 常時 5分ごと
  fetchBars = true;      # 常時 5分ごと
};
```

## bt-dynamic との関係

- **bt-dynamic**（研究）: 9セル分類・判定・バックテストのエンジン。PyPI パッケージ
- **live-dynamic**（本リポ）: そのエンジンを import して実弾で回す実行層

`strategies/trend/strategy.py` は bt-dynamic の `classify` / `resolve_entry` / `IndicatorSet` をそのまま呼ぶ。バックテストで使った config JSON を `$BT_DYNAMIC_CONFIG` に指すだけで、検証済みの判定ロジックが本番に載る。
