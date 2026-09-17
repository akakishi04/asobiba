# Video Rotate, Resize & AI Restore

Windows向けのGUI動画変換ツールです。通常の**実ピクセル回転 / 解像度変更**に加え、解像度を維持したまま動画を復元する **RVRT / SeedVR2** を選択できます。

## 通常変換

- 回転: なし / 時計回り90° / 反時計回り90° / 180°
- 解像度: 元の解像度 / 1080p / 720p / 4K / カスタム
- NVIDIA NVENC (`h264_nvenc`) を自動検出して優先使用
- NVENCが使えない場合は `libx264` にフォールバック
- 音声は可能な限り再エンコードせずコピー
- ログ表示、キャンセル
- 解像度変更ではアスペクト比を維持し、余った領域を黒帯で埋める

AIを「なし」にした場合は従来通りFFmpegだけで処理します。

## AI鮮明化

### RVRT（忠実復元 / デブラー）

公式RVRTの1x Video Deblurringモデルを使います。

- `005_RVRT_videodeblurring_GoPro_16frames`（既定）
- `004_RVRT_videodeblurring_DVD_16frames`

出力解像度は入力（または回転/リサイズ後）の解像度を維持します。

### SeedVR2（AI復元）

公式SeedVR2 standalone CLIを使います。

既定値:

- Model: `seedvr2_ema_3b_fp8_e4m3fn.safetensors`
- Batch size: `5`
- BlockSwap: `20`
- Temporal overlap: `2`
- Preserve VRAM: ON
- I/O component offload: ON
- VAE tiling: ON
- 処理短辺: `0`（最終出力の短辺をそのまま使用）

SeedVR2の処理短辺を小さくしても、最終MP4は指定した出力解像度へ戻します。ただし内部で縮小して処理するため、ネイティブ解像度処理より復元できる細部は減ります。

### RVRT → SeedVR2

高品質モードです。

```text
入力
 ↓
必要なら回転 / リサイズ
 ↓
RVRT（1x Deblur）
 ↓
SeedVR2
 ↓
元動画の音声を戻す
 ↓
MP4
```

RVRTとSeedVR2は同時にGPUへ常駐させず、別プロセスで順番に実行します。

## AI処理時の入出力

AI処理では中間映像をできるだけ劣化させないため、PNGフレームまたはFFV1ロスレス動画を使います。

最終段階では、元FPS（取得できた場合）、元動画の音声、元動画のメタデータ、指定した最終解像度を使ってMP4を作成します。

### VFR動画について

AIモデルはフレーム列として処理するため、可変フレームレート（VFR）の厳密な各フレーム時刻は保持せず、`ffprobe`で取得した平均FPSを使うCFR動画として再構成します。

## 必要なもの

基本機能:

- Windows 11
- Python 3.10以降（Tkinterを含むWindows版）
- `ffmpeg`
- `ffprobe`

AI機能:

- RVRT公式リポジトリ + RVRTが動くPython環境
- SeedVR2 standalone CLIリポジトリ + SeedVR2が動くPython環境
- NVIDIA GPU推奨

RVRTとSeedVR2は依存関係が大きく異なるため、**別のPython仮想環境を推奨**します。

## AIエンジンの設定

アプリを起動し、`AI設定...` を開きます。

### RVRT

設定するもの:

- `RVRTフォルダ`: `main_test_rvrt.py` があるフォルダ
- `RVRT Python`: RVRTの依存関係を入れたPython実行ファイル
- `RVRTモデル`: GoPro Deblur（推奨） / DVD Deblur

公式リポジトリ:

```powershell
git clone https://github.com/JingyunLiang/RVRT.git
```

依存関係はRVRT側の `requirements.txt` に従ってください。公式実装はPython 3.8 / PyTorch >= 1.9.1を基準にしています。

学習済みRVRT weightは、初回実行時に公式スクリプトが必要に応じてダウンロードします。

### SeedVR2

設定するもの:

- `SeedVR2フォルダ`: `inference_cli.py` があるフォルダ
- `SeedVR2 Python`: SeedVR2の依存関係を入れたPython実行ファイル
- Model / Batch / BlockSwap / 処理短辺

公式Standalone CLIを含む実装:

```powershell
git clone https://github.com/comfyorg/comfyui_seedvr2.git
```

依存関係はSeedVR2側のREADME / `requirements.txt` に従ってください。モデルはCLI側が必要に応じてダウンロードします。

設定内容はローカルの `ai_config.json` に保存されます。このファイルはGit管理対象外です。

## 4070 Ti SUPER 16GB向け初期値

まずは以下から開始します。

```text
SeedVR2:
  3B FP8
  Batch = 5
  BlockSwap = 20
  Temporal overlap = 2
  VAE tiling = ON
```

1080p前後ではまずネイティブ短辺を試します。

4Kや2160×3840のような高解像度でOOMになる場合は、`AI設定...` の「処理短辺」を `1440`、`1080`、`1072` などへ下げて試せます。最終ファイル自体の解像度は維持されます。

## 起動

`run.bat` をダブルクリックするか、PowerShellで:

```powershell
cd video-rotate-resize
python app_ai.py
```

従来GUIの `app.py` も残してあります。`run.bat` はAI対応版 `app_ai.py` を起動します。

## 基本操作

1. 入力動画を選択。
2. 回転を選択。
3. 解像度を選択。
4. 必要ならAI鮮明化を選択。
5. AIを使う場合は最初に `AI設定...` で各エンジンを登録。
6. `変換開始`。
7. 出力先へMP4が保存される。

AIだけ使いたい場合は、`回転 = なし`、`解像度 = 元の解像度` にしてAI鮮明化だけ選択します。

## 通常変換の標準画質

- NVENC: H.264 / preset `p6` / CQ 18
- CPU: H.264 / libx264 / CRF 18 / preset `medium`
- pixel format: `yuv420p`

## テスト

モデルをダウンロードせずに、コマンド生成と設定処理をテストできます。

```powershell
python -m unittest -v
```

テスト対象には、既存の回転/リサイズ、NVENC/libx264、FFV1中間、PNG抽出、元音声の再mux、RVRT/SeedVR2コマンド、AI設定保存/復元、最終解像度維持を含みます。

## 注意

- AI処理は通常変換より非常に時間がかかります。
- SeedVR2は復元時に存在しなかった細部を生成する場合があります。
- RVRTは比較的忠実度優先ですが、任意の実写劣化に対して完全な復元を保証するモデルではありません。
- RVRT公式プロジェクトの大部分は **CC BY-NC** です。商用利用を検討する場合はRVRT側のライセンス条件を確認してください。
- SeedVR2側も使用する実装・weightのライセンスをそれぞれ確認してください。
