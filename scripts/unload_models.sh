#!/bin/bash
# unload_models.sh — Ollama ロード済みモデルの手動アンロード
# 使用方法: bash scripts/unload_models.sh

echo "=== ロード中のモデルを確認 ==="
curl -s http://localhost:11434/api/ps | python3 -c "
import json, sys
data = json.load(sys.stdin)
models = data.get('models', [])
if not models:
    print('  ロード中のモデルはありません')
else:
    for m in models:
        vram_mb = (m.get('size_vram') or 0) // 1024 // 1024
        print(f'  - {m[\"name\"]} ({vram_mb}MB VRAM)')
"

echo ""
echo "=== アンロード実行 ==="
for model in "qwen2.5-coder:14b" "qwen2.5-coder:7b" "deepseek-r1:14b" "gemini-2.5-flash"; do
  curl -s -X POST http://localhost:11434/api/generate \
    -d "{\"model\": \"$model\", \"keep_alive\": 0}" \
    -H "Content-Type: application/json" > /dev/null 2>&1
  echo "  $model アンロード完了"
done

echo ""
echo "=== アンロード後の状態 ==="
curl -s http://localhost:11434/api/ps | python3 -c "
import json, sys
models = json.load(sys.stdin).get('models', [])
if models:
    print('残存:', [m['name'] for m in models])
else:
    print('  ロード中のモデルなし ✅')
"
