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

**Seedの扱い:** GUIのSeedが空欄なら、毎回アプリ側で安全な32bit乱数を生成します。Seedを明示入力した場合は、その値を優先して再現性を保ちます。LLMにはSeedの選択を任せず、不正なSeedを返しても採用しないため、LLM由来のSeed範囲エラーで画像生成が停止しません。


## 日本語入力・画面の見やすさ

GUIの入力欄を**コンパクトな6行のエディタ**に変更し、`Meiryo UI`・広めの行間・余白を採用しています。長い文章は欄内スクロールで入力できます。画面右上の **「ダーク表示」** で明暗を切替可能です。入力欄右上の `A−` / `A+` ボタンで**文字サイズを10～20pt**の範囲で調整できます。既存の入力文を消さずに切り替えられます。

色設定と文字サイズは「設定を保存」で `config.json` に保存され、次回起動時に復元します（Git管理対象外）。画像生成、ワークフロー、LLM解釈には影響しません。

**日本語IME変換中文字のフォント補正:** Tkinterでは、文字の確定前だけWindows IME側の別フォントで大きく表示されることがあります。Windows環境では入力欄にフォーカスしたときとIMEキー入力時に `ImmSetCompositionFontW`（Win32標準API）を使用し、入力欄と同じフォント名・サイズをIMEへ通知します。フォントサイズ変更にも追従します。IMEやWindows側の実装差で反映されない場合があるため、最終的な効果はWindows実機で確認してください。

**別問題：IMEの予測候補ウィンドウ**（「Tabキーを押して選択します」の一覧）はWindows側のUIで、上記の補正対象ではありません。必要な場合のみMicrosoft IMEの「予測入力」で別途設定してください。

## LM Studioのトークン設定

標準値を **コンテキスト長8,192 tokens / 最大生成4,096 tokens** に設定しています。出力のばらつきは従来どおり `temperature=0.2` です。

- `config.example.json` の `llm.context_length=8192`：LM Studioのモデルを新規ロードするときのコンテキスト上限。
- `llm.max_tokens=4096`：`/v1/chat/completions` に渡す最大生成トークン数。**常に4,096トークン生成するわけではなく上限**です。
- 既存GUI設定が旧標準値の4,096コンテキスト・2,048出力だった場合は、次回のGUI起動時に新しい標準値へ一度だけ移行します。その後GUIで「設定を保存」または生成を実行すると、変更がGit管理外の `config.json` に保存されます。既に標準値以外を指定したユーザー設定は保護します。
- LM Studio側で既にモデルがロードされている場合は、そのモデルインスタンスのコンテキスト設定が優先されます。新しい8,192トークン枠を確実に使いたい場合は、LM Studio側で既存インスタンスをアンロードしてからGUIで解釈を実行してください。
- 推論用トークンの上限を増やすため、場合によってはLLMの計算時間やVRAM使用量が増えます。必要なら `config.json` で値を調整できます。

## LM Studioでタイムアウトする場合

Thinkingを使用するローカルLLMは、4,096 tokensの生成上限を活用すると解釈に4分以上かかることがあります。以前の `llm.timeout_seconds=240` は全APIで共通だったため、実際の応答が完成する前に通信が切れる場合がありました。

- `llm.inference_timeout_seconds=600`：LM Studioの **`/v1/chat/completions` だけ**に適用する通信待機上限（10分）
- `llm.timeout_seconds=240`：モデル一覧、ロード、アンロードなど従来のAPI操作用（4分）
- `comfyui.generation_timeout_seconds=1800`：画像生成の完了を待つ時間（従来どおり30分）

GUI起動時、既存のローカル `config.json` に新項目がなければ600秒を補完します。GUIの「設定を保存」で反映されます。手動で増減する場合はローカル `config.json` の `llm.inference_timeout_seconds` を編集してください（30～3,600秒）。

タイムアウト時は、どのLM Studio API操作で発生したか表示します。**延長しても確実に成功する保証はありません。** メモリ不足、モデルの応答停止、極端に低いtoken/s等でも応答が遅くなるため、再発する場合はLM Studioのログと実測速度を確認してください。自動リトライは行わず、重複実行を避けます。

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
| `wai_i2i_basic` | I2I / 参照画像から描き直し | `workflows/wai_i2i_basic.api.json` |

`config.example.json` には、ノードIDと入力の対応を登録済みです。I2Iは元画像を`LoadImage (16)`で読み込み、`VAEEncode (17)`を通して`KSampler (11)`へ送る構成です。元の出力設定のDenoiseは `0.53` です。

### I2Iの使い方（Windows GUI）

1. **参照画像** からPNG/JPEG/WebPを選択します。画像が選ばれるとワークフローが `wai_i2i_basic` に自動切替されます。
2. 日本語で「服の色を青に」「表情を笑顔に」など変更内容を入力します。
3. **Denoise (I2I)** を調整します。目安は `0.3`（原形を強く維持）～ `0.7`（大きく描き直し）で、初期値は `0.53` です。
4. 「解釈のみテスト」で指示の変換を確認し、「画像生成を開始」でComfyUIに送ります。

- **I2Iの出力解像度は参照画像と同じ**です。元画像が224×224なら生成も224×224です。GUIの幅・高さはI2Iで無効化します。高解像度化は別のリサイズ／アップスケール用ワークフローで対応します。
- **LLMの画像解析は初期設定でOFF**です。参照画像は直接ComfyUIにアップロードし、LM Studioには自然文だけを送ります。画像対応LMMを使い、画像内容も読ませたい場合はローカルの`config.json`で`llm.send_reference_to_llm=true`に変更してください。その場合は画像の送信による推論負荷が増えます。
- I2Iは画像全体を描き直す方式です。特定部分だけをマスクして変更するInpaintingは未実装です。
- T2Iは従来どおり維持し、参照画像欄を空にすると戻せます。LLMにはノードの追加・削除・再接続を許可しません。


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
