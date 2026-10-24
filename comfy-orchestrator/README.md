# Comfy Orchestrator（asobiba / main）

用意済みの **ComfyUIワークフロー**を自然文から実行する、Windows向けローカルGUIです。LLMの解釈には **LM Studio** を標準採用し、追加のOllama導入は不要です。Python 3.11+ と標準ライブラリだけで動きます（Tkinterは通常のWindows版Pythonに同梱）。

## まずGUIを起動する

1. **LM Studio 0.4.0以降**を起動し、**Developer / Local Server** からサーバーを有効にする（標準ポート `1234`）。
2. ComfyUIを通常どおり起動する（標準ポート `8188`）。`waiIllustriousSDXL_v170.safetensors` がComfyUIに配置済みであること。
3. Windowsで `comfy-orchestrator/run_gui.bat` をダブルクリック。あるいはPowerShellから:

   ```powershell
   cd M:\asobiba\comfy-orchestrator
   python -m comfy_orchestrator.gui
   ```

4. GUIの **「モデルを更新」** からLM Studioにインストール済みのモデルを選ぶ。
5. **「接続確認」→「設定を保存」** で接続と設定を確認する。
6. 自然文を入力して **「解釈のみテスト」** でLLMの変換結果を確認。
7. 問題なければ **「画像生成を開始」** でComfyUIに投げる。

ウィンドウの右側に生成結果をプレビューし、画像は `comfy-orchestrator/outputs/` へ保存します（Git管理外）。日本語入力に対応しています。

### 画面で調整できる項目

- LM Studio / ComfyUI のURL、LLMモデル選択、接続確認と設定保存
- 固定ワークフローの選択（自動選択または明示選択）
- 自然文、参照画像（**I2I/I2Vの登録後に有効**）、幅・高さ・Steps・CFG・Seed
- LLM解釈だけのテスト、ComfyUI生成、実行ログ、出力画像の一覧とプレビュー
- **「待機を中止」** はクライアント側の待機だけを停止し、ComfyUIに投入済みの生成ジョブは停止しません。

画面の軽量初期値は **768×768 / 20 Steps / CFG 5.0** です。ユーザーがエクスポートした固定ワークフロー原本は **1024×1024 / 28 Steps / CFG 5.5** のまま保持しています。精細さが必要ならGUIで設定を変更してください。

## 実行時のモデル解放とPC負荷

```text
日本語入力
  ↓
LM Studioの指定LLMをロード（すでにロード済みなら再利用）
  ↓
LLMが固定ワークフローと許可された入力をJSONで決定
  ↓
LM Studio APIで、そのLLMインスタンスのアンロード完了を確認
  ↓
ComfyUIへ固定ワークフローをキュー投入
  ↓
ComfyUIで画像生成 → 出力取得・表示
```

GPUメモリ節約のため、GUI初期状態で「LM Studioモデルを解釈後にアンロード」がONです。**選択したモデルがLM Studioの画面で事前ロードされていても解放します。** 別のLLMを巻き込んでアンロードしません。ComfyUI側の前回モデルの解放は、キューが空の場合に限って要求します。

実際のVRAM解放量は各プロセス・GPUドライバーに依存します。ComfyUIの `/free` は非同期要求であり、完全解放の保証ではありません。必要なモデルファイルのロード時間は発生します。

## 既存の固定ワークフロー

| ID | 種類 | API JSON |
|---|---|---|
| `wai_t2i_basic` | T2I / アニメイラスト | `workflows/wai_t2i_basic.api.json` |

`config.example.json` には、正確なノードID（Positive 8、Negative 5、Size 10、Sampler 11）が登録されています。今後I2I/T2V/I2V用のAPI形式JSONを登録すれば、GUIの選択肢に追加できます。

LLMはノードを追加・削除・再接続しません。JSON上で登録済みの入力だけ変更します。

## 既存の設定を持っている場合

`config.json` はGit管理されません。初回GUI起動時に存在しなければ `config.example.json` から自動生成します。以前のOllama用 `config.json` がある場合は、GUIが **LM Studio設定を追加** して移行できます（既存のOllama設定を削除しません）。設定保存前に必要に応じて確認してください。

トークン認証を有効にしているLM Studioを使う場合、環境変数 `LMSTUDIO_API_TOKEN` にトークンを設定します。GUIにトークン文字列を保存しません。

## CLI（GUIなしでも使用可能）

```powershell
cd M:\asobiba\comfy-orchestrator
Copy-Item config.example.json config.json  # 既存のconfig.jsonがある場合は実行しない
# config.jsonの llm.model に LM Studioのモデルkeyを記入
python -m comfy_orchestrator --config config.json validate
python -m comfy_orchestrator --config config.json run "夕暮れの海辺に立つ銀髪の少女、アニメ調" --dry-run
python -m comfy_orchestrator --config config.json run "夕暮れの海辺に立つ銀髪の少女、アニメ調"
```

`llm` がない古い設定ファイルの場合は、従来の `ollama` 経路も後方互換で使用できます。

## オフライン検証

```powershell
cd M:\asobiba\comfy-orchestrator
python -m compileall -q comfy_orchestrator
python -m unittest discover -s tests -v -p "test_*.py"
```

Windows GUI、LM Studioモデルの実ロード/解放、ComfyUIの実画像生成はローカルWindows環境で実機確認してください。自動テストは外部サービスなしで実行します。

## 安全性・制約

- LM Studio / ComfyUI はGUIから新たにインストール・起動せず、既存のローカルサーバーに接続します。
- 不正なワークフローID、API形式でないJSON、未登録ノードやパラメータ、範囲外の値は生成前に拒否します。
- モデルや仮想環境、キャッシュ、ローカル設定、生成画像はコミットしません。
- 他人のComfyUIジョブを削除・中断しません。複数実行する場合はGPU・VRAMの競合に注意してください。
- LM Studioの選択モデルを確実にアンロードできなければ生成を開始しません（アンロード設定ON時）。
- 出力プレビューはTkinterで表示できる形式を優先し、対応外の画像は保存ファイルを開いてください。
