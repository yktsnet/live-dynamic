# VHS demo: live-dynamic
# 生成: リポルートで `nix-shell --run 'vhs examples/demo.tape'`（shell.nix が python 環境を供給、vhs は home.nix 導入済み）
# 示したいこと: 合成バーから判定→発注ゲートまで一周しても、既定 dry_run のため
#               送信記録に dry_run: true が残るだけ（ブローカー非接続）
# 尺規範: 10秒前後

Output examples/demo.gif

Set FontSize 18
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 20ms

Hide
Type "rm -rf demo-data demo-market demo-data-config.json"
Enter
Type `python -c "import json; c = json.load(open('examples/config.json')); c['parameters'].update(trade_end_hour=24, direction_band=0.5); c['regime_strategy'] = {f'{a},{b}': 'follow' for a in range(3) for b in range(3)}; json.dump(c, open('demo-data-config.json','w'))"`
Enter
Type "export LIVE_DYNAMIC_DATA=./demo-data MARKET_DATA=./demo-market BT_DYNAMIC_CONFIG=./demo-data-config.json PYTHONPATH=."
Enter
Type "mkdir -p demo-data/state && python examples/generate_bars.py > /dev/null"
Enter
Type "clear"
Enter
Show

Type "# 判定 -> 発注ゲートを一周する（既定は dry_run、ブローカー非接続）"
Enter
Sleep 400ms

Type "ls demo-data/state/"
Enter
Sleep 800ms

Type "python core/orchestrator.py"
Enter
Sleep 2500ms

Type "ls demo-data/state/"
Enter
Sleep 1000ms

Type "python -m json.tool demo-data/state/sent.jsonl"
Enter
Sleep 2800ms

Hide
Type "rm -rf demo-data demo-market demo-data-config.json"
Enter
Show
