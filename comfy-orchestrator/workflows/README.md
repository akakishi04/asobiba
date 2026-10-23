# 固定ワークフロー配置場所

ここに ComfyUI の **API形式のJSON**（UIの通常保存JSONではない）を配置してください。

ComfyUI の `Save (API Format)` 等で書き出した実行用ノード辞書を使用します。実際の書き出し操作はComfyUIのバージョンで異なります。
ファイルを配置したら、`config.json` の `workflows` へID・種類・ファイル・入力のバインディングを登録します。
モデルチェックポイントや巨大な重みファイルはGitで管理しないでください。

`config.json` 内の登録例（実際のノードIDと入力名に置き換えること）:

```json
"workflows": {
  "my-t2i": {
    "kind": "t2i",
    "description": "標準的な静止画生成",
    "file": "workflows/my-t2i.api.json",
    "bindings": {
      "positive_prompt": {"node": "6", "input": "text"},
      "negative_prompt": {"node": "7", "input": "text"},
      "seed": {"node": "3", "input": "seed"},
      "steps": {"node": "3", "input": "steps"}
    },
    "defaults": {"negative_prompt": "", "steps": 25}
  }
}
```

I2I/I2Vで参照画像を渡す場合は、さらに `"image": {"node": "画像ロードノードID", "input": "image"}` を登録してください。
登録する各バインディングはAPI形式JSONにすでに存在するノード・入力名である必要があります。
この仕組みはノードの新規追加や結線変更をLLMには許可せず、既存の入力値だけを変更します。
