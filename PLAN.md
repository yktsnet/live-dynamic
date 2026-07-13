# PLAN

live-dynamic の公開までの構想と作業プラン。README 完成時に本ファイルの生きている内容を README / docs へ統合して削除する。設計判断の根拠は JUDGE.md を参照。

## 構想

`bt-dynamic`（研究・バックテスト）と対になる実弾実行層。バックテストで検証した戦略をブローカーの OpenAPI に接続し、systemd timer で無人運転する参照実装として公開する。

伝えたいストーリーは「バックテストを本番に持っていくとき何を守るか」。冪等性、dry_run 既定、多層フェイルセーフ（OCO / EOD / キルスイッチ）、トークンのライフサイクル管理を、動くコードと README / VHS デモで示す。

- 移植元: `~/dotfiles/apps/ops_dynamic`（het で稼働中の本番系。今後も本番はそちらで動き続ける）
- 配布: GitHub 公開のみ。PyPI なし
- 前身: `~/dotfiles/apps/00archive/ops`（約 7,900 行）と `ops2`（約 2,000 行）。コードは持ち込まず、Design Decisions で削ぎ落としの経緯として言及する
- 既存の `github-private/ops_dynamic`（private リモート）は本番系のミラーであり、本リポとは別物。公開後の扱い（archive するか）は公開時に判断

## スコープ

公開に含める。

- `core/`: orchestrator, build_signal, sender_gate, abn_check, eod_close, token_refresh, fetch_bars
- `lib/`: broker_client, oco_manager, oco_repo, token_io, bar_loader, env 系, snap 系（キルスイッチ IF に改修）
- `strategies/`: bt-dynamic を pip 依存で参照する接続層。戦略定数は config 注入に改修
- Nix systemd サービス定義（timer 構成ごと見せる）
- VHS デモ（dry_run + 合成シグナルでパイプラインを一周）

含めない。

- 戦略定数の実値（セル対応表、TP/SL、指標パラメータ、通貨ペア、ロット、セッション時刻）
- 実ブローカー名・接続先 URL（`BROKER_*` env の完全外部注入。コード内デフォルトも置かない）
- 非公開系に依存する ABN 判定の中身
- 本番の state / logs / env

## 作業ステップ

1. **コア移植**: dotfiles/apps/ops_dynamic から core / lib / strategies / Nix 定義を持ち込む。`__pycache__` や本番残渣は除外
2. **bt-dynamic を pip 依存に切替**: strategy.py の PYTHONPATH ハックを廃し、PyPI の bt-dynamic を import する形に書き換える
3. **戦略定数の外部注入化**: strategy.py にハードコードされた REGIME_STRATEGY / TP / SL / ATR 窓 / セッション時刻を config JSON（bt-dynamic と同形式）へ追い出す
4. **キルスイッチ汎用化**: snap_io / abn_check を「外部フラグファイル監視 → 全決済」の汎用 IF に改修し、非公開系への言及を消す
4b. **ブローカー匿名化**: 実ブローカー名をコード・コメント・ファイル名から除去し、接続先を env 完全注入に改修。固有の識別子名は汎用名に改める
5. **README のダミー化**: 設定例の実値（銘柄 ID、pips、ロット）をダミー値に差し替え、免責事項と dry_run 既定を明記
6. **動作確認**: 合成バーデータ + dry_run でパイプライン（build_signal → sender_gate → sent.jsonl）が一周することを確認
7. **VHS デモ**: 上記の一周を demo.tape 化（vhs-demo スキル。ttyd はシステム導入版を使う）
8. **公開パイプライン**: repo-standardize → repo-readme（PLAN / JUDGE を統合して削除）→ readme-i18n → repo-publish → repo-about
9. **公開後**: github-public/ へ配置換え。dotfiles 側 ops_dynamic の扱い（本番系として残す）を README に一言記録

## フェーズ

MVP 期（bt-dynamic と同じ立ち上がり方）。公開が済み構造が固まった時点で Issue ドリブン期への移行を検討する。
