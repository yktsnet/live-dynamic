# live-dynamic

@context/conventions.md
@context/structure.md

## Identity (One-sentence Definition)

汎用部分 = bt-dynamic で検証した戦略をブローカー OpenAPI + systemd timer で無人運転する実弾実行層（参照実装・clone リファレンス）。
固有部分 = 戦略の実値（config JSON）・接続情報（env ファイル）。すべて `LIVE_DYNAMIC_DATA` 側の外部注入でリポ外。

フェーズ: **MVP期**。

## Invariants

- コード・ドキュメント・コミットに実ブローカー名・接続先 URL を書かない。接続先は `BROKER_API_BASE` / `BROKER_AUTH_BASE` の env 必須（コード内デフォルト禁止）。
- 戦略定数（セル対応表・TP/SL・閾値・銘柄 ID・ロット）はリポに置かない。`$BT_DYNAMIC_CONFIG` と env の注入のみ。`examples/` は教科書的ダミー値だけ。
- 状態ファイルの書き込みはすべて atomic（`.tmp` → `os.replace`）。`signal.jsonl` / `sent.jsonl` / `halt_log.jsonl` は追記のみ。
- ブローカー API 呼び出しは `lib/broker_client.py`（発注系）と `lib/chart_client.py`（チャート系）経由のみ。両者は標準ライブラリ（urllib）だけで書く。
- `ENABLE_EXEC_REQUESTS` の既定は dry_run（0）。既定値を変えない。

## コマンド

`shell.nix` が PyPI の bt-dynamic を含む再現環境（pip 不要）。

```bash
# テスト
nix-shell --run "PYTHONPATH=. pytest tests -q"

# dry_run デモ（資格情報不要）
nix-shell --run "
  export LIVE_DYNAMIC_DATA=~/live_dynamic_data MARKET_DATA=~/market_data \
         BT_DYNAMIC_CONFIG=examples/config.json PYTHONPATH=.
  python examples/generate_bars.py && python core/orchestrator.py"
```

Nix を使わない環境（CI 等）は `pip install -r requirements.txt pytest` で同等。

## アーキテクチャの要点

- 判定（`build_signal`、ブローカー非接続）と発注（`sender_gate`、冪等）を分離。間は `signal.jsonl` の受け渡しのみ。
- フェイルセーフは三層: OCO 自動配置（`oco_manager`）・EOD 強制決済（`eod_close`）・キルスイッチ（`halt_check` + `state/halt_flags.jsonl`）。
- systemd timer（`live-dynamic-service.nix`）が各スクリプトを oneshot で叩く。常駐プロセスなし。

## 検証手段

PR 前に `nix-shell --run "PYTHONPATH=. pytest tests -q"` を通す（25件・ネットワーク/資格情報不要）。CI（`.github/workflows/ci.yml`）は pip で同じものを回す。実弾経路・systemd 反映の確認は user が行う。
