# Comfy Orchestrator（asobiba / main）

手元で用意した**固定のComfyUIワークフロー**を、自然文の指示に基づいてOllamaのLLM/LMMが選択し、事前登録された入力値を埋めるツールです。独立したCLIで、既存のasobibaプロジェクトに依存しません。

## 実行順序

1. 自然文と（任意で）参照画像を受け取る。
2. ComfyUIがアイドルなら以前の生成モデルの解放を要求する（非同期・設定でOFF可）。他のジョブがある場合は中断する。
3. Ollamaの `/api/generate` で固定ワークフローからIDを選択し、構造化されたパラメータを受け取る。
4. Ollamaに `keep_alive=0` を指定した明示的なアンロード要求を送る。**アンロードAPIが失敗した場合は生成を開始しない。**
5. 既定のワークフローに**登録されたパラメータだけ**適用し、必要なら参照画像をComfyUIへアップロードする。
6. ComfyUIの `/prompt` へ投入、`/history/{prompt_id}` で完了確認。結果のファイル情報をJSONで表示する。

ComfyUIやOllamaのプロセスは終了しません。Ollamaのアンロード完了応答を確認してから生成します。一方、ComfyUIの`/free`は非同期の要求受付であり、実VRAM解放完了の検証までは行いません。他のプロセスが占有するVRAM全量も保証しません。

## 初期セットアップ（Windows / PowerShell）

OllamaとComfyUIは**別途インストール・起動**してください。Python 3.11以上が必要です。外部Pythonパッケージは不要です。

```powershell
cd <asobibaの場所>\comfy-orchestrator
Copy-Item config.example.json config.json
# config.json の ollama.model を実際にインストール済みのモデル名にする
python -m comfy_orchestrator --config config.json validate
python -m unittest discover -s tests -v
```

**登録済みワークフロー:** `wai_t2i_basic`（`workflows/wai_t2i_basic.api.json`、`waiIllustriousSDXL_v170.safetensors`）。`config.example.json` にはPositive/Negative、1024×1024、28 Steps、CFG 5.5、Seedのノード対応が登録されています。`Copy-Item config.example.json config.json` で設定をコピーし、`ollama.model` にローカルで利用できる実際のモデル名を指定してください。`config.json` はGit管理対象外です。既存の `config.json` がある場合、コピーで上書きしないで登録内容をマージしてください。

画像生成の計算負荷を下げたい場合は、`config.json` 内のこのワークフローの `defaults` で `width`/`height` を768程度、`steps` を20程度から試せます（ただし、生成品質は変わります）。ワークフローJSONは元の設定を保持しています。ComfyUI側で同名のチェックポイントがインストールされている必要があります。

## 実行

```powershell
python -m comfy_orchestrator --config config.json validate
python -m comfy_orchestrator --config config.json run "夕暮れの海辺に立つ銀髪の少女、アニメ調" --dry-run
python -m comfy_orchestrator --config config.json run "夕暮れの海辺に立つ銀髪の少女、アニメ調"
python -m comfy_orchestrator --config config.json run "この画像の人物が振り返る短い動画" --image C:\path\reference.png
```

- `validate` は接続なしでJSONと入力先の整合性を検証します。ワークフロー0件のときは未設定と表示します。
- `--dry-run` はOllamaによる解釈とアンロードまで。ComfyUIへはアクセスしません。
- `--image` はOllamaの視覚入力に参照画像を渡すため、**画像を扱えるモデル**が必要です。該当ワークフローには `image` バインディングも必要です。
- 対応パラメータ: `positive_prompt`, `negative_prompt`, `width`, `height`, `steps`, `cfg`, `seed`, `frames`, `fps`, `denoise`。
- 保存済み出力はComfyUI側の出力ディレクトリに残ります。初期版はファイルの再ダウンロードやGUIを行いません。

## 安全と制約

- JSON schemaとローカルのバリデーションでワークフローID・値・入力先を制限します。LLMにはノードを作成・接続・削除させません。
- 他のComfyUIジョブを中断・削除しません。生成中はリソースを共有できないため、単一ユーザー・単一実行を推奨します。
- 作成済みワークフローのノードが存在しない、値域外、API形式ではない場合は投入前に拒否します。
- 現時点ではOllama/ComfyUIともローカルで動作していないため、実GPU・モデル動作の検証は未実施です。
