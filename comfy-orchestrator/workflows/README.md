# 固定ワークフロー配置場所

ここに ComfyUI の **API形式のJSON**（UIの通常保存JSONではない）を配置してください。

## 登録済み：wai_t2i_basic

- ファイル: `wai_t2i_basic.api.json`（ユーザー作成のAPIエクスポート）
- モデル: `waiIllustriousSDXL_v170.safetensors`（モデル本体はローカルComfyUI側に配置）
- 変更可能な入力: Positive `8.text`、Negative `5.text`、画像サイズ `10.width` / `10.height`、`11.steps` / `11.cfg` / `11.seed`
- 元の保存値: 1024×1024、28 Steps、CFG 5.5。LLMの入力がなくても画像品質設定の基準にできるよう `config.example.json` にも同じ初期値を設定しています。
- API出力は画像保存ノード `13` に到達します。使用前に `python -m comfy_orchestrator --config config.json validate` を実行してください。


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
