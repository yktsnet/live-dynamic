# Structure

```
live-dynamic/
├── core/                       # systemd timer から oneshot 起動される実行スクリプト
│   ├── orchestrator.py           # build_signal → sender_gate をシーケンス実行（30分ごと）
│   ├── build_signal.py           # バー読込 → 戦略判定 → signal.jsonl 追記。ブローカー非接続
│   ├── sender_gate.py            # 最新シグナルを冪等に発注し sent.jsonl に記録。dry_run 既定
│   ├── halt_check.py             # halt フラグ検知 → 全決済（5分ごと）
│   ├── eod_close.py              # セッション終了時の強制全決済（日次）
│   ├── token_refresh.py          # アクセストークンのリフレッシュ（5分ごと）
│   └── fetch_bars.py             # 5分足の取得・保存（5分ごと）
├── lib/                        # 自己完結ライブラリ
│   ├── paths.py                  # パス解決の唯一の入口（LIVE_DYNAMIC_DATA / MARKET_DATA）
│   ├── env_auth.py / env_loader.py  # env ファイルの読み込み（環境変数優先）
│   ├── broker_client.py          # 発注・ポジション API クライアント（urllib のみ）
│   ├── chart_client.py           # チャート API クライアント（fetch_bars 用）
│   ├── token_io.py               # トークンファイル R/W（MARKET_DATA/state/tokens/）
│   ├── bar_loader.py             # 5分足の読み込み（当日 + warmup 日数）
│   ├── oco_manager.py / oco_repo.py / oco_env.py  # TP/SL ブラケットの配置・照合・価格計算
│   ├── halt_io.py                # キルスイッチフラグの読み込み・判定
│   └── force_close.py            # 全ポジション強制決済（eod_close / halt_check 共用）
├── strategies/trend/strategy.py  # bt-dynamic パッケージへの接続層。判定は classify/resolve_entry に委譲
├── examples/                   # ダミー config と合成バー生成（デモ・検証用）
├── tests/                      # pytest（一時ディレクトリ + 合成データのみ）
└── live-dynamic-service.nix    # systemd サービス / timer 定義（ユーザ・パスはオプション注入）
```

## データフロー

```
fetch_bars ──▶ MARKET_DATA/bars/*.jsonl（5分足・日別ファイル）
                     │ bar_loader
build_signal ── strategy.decide（bt_dynamic.classify / resolve_entry, config 注入）
                     │ signal.jsonl（追記）
sender_gate ── time_utc 照合（冪等）→ ENABLE_EXEC_REQUESTS ゲート → broker_client
                     │ sent.jsonl（追記）→ 成功時 oco_manager.ensure()
halt_check / eod_close ──▶ force_close（全決済）──▶ halt_log.jsonl / eod.jsonl
token_refresh ──▶ MARKET_DATA/state/tokens/live_current.json（fetch と発注で共有）
```

`LIVE_DYNAMIC_DATA` = このアプリの state/logs/env、`MARKET_DATA` = バーとトークンの共有ルート。リポ内に状態・秘密は持たない。
