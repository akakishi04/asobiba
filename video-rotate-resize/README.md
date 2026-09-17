# Video Rotate, Resize & AI Restore

Windows向けのGUI動画変換ツールです。従来の**実ピクセル回転 / 解像度変更**を維持しつつ、解像度を維持した動画復元として **RVRT / SeedVR2 / RVRT → SeedVR2** を追加しています。

## 機能

### 通常変換

- 回転: なし / 時計回り90° / 反時計回り90° / 180°
- 解像度: 元の解像度 / 1080p / 720p / 4K / カスタム
- NVIDIA NVENC (`h264_nvenc`) を自動検出して優先
- NVENCが使えない場合は `libx264` にフォールバック
- 音声は可能な限りコピー
- アスペクト比維持 + 必要時は黒帯
- ログ、進捗、キャンセル

AIを「なし」にすれば従来どおりFFmpegだけで処理します。

### RVRT

忠実度寄りの1x Video Restorationです。現在は公式RVRTのDeblurモデルを利用します。

- `005_RVRT_videodeblurring_GoPro_16frames`（既定 / 推奨）
- `004_RVRT_videodeblurring_DVD_16frames`

入力動画をPNGフレームへ展開し、RVRT処理後に元FPSと元音声を使ってMP4へ戻します。

### SeedVR2

生成力の強いVideo Restorationです。4070 Ti SUPER 16GBでの利用を考え、公式研究実装ではなく `comfyorg/comfyui_seedvr2` のStandalone CLI (`inference_cli.py`) を利用できる構成です。

既定値:

- Model: `seedvr2_ema_3b_fp8_e4m3fn.safetensors`
- Batch: `5`
- BlockSwap: `20`
- Temporal overlap: `2`
- Preserve VRAM: ON
- I/O component offload: ON
- VAE tiling: ON
- VAE tile: `512`
- overlap: `128`
- 処理短辺: `0` = 入力の短辺を使用

高解像度でVRAM不足になる場合は、AI設定の「処理短辺」を `1440` / `1080` / `1072` などへ下げられます。最終MP4は指定した出力解像度へ戻します。

### RVRT → SeedVR2

高品質モードです。

```text
入力動画
  ↓
必要なら回転 / リサイズ
  ↓
RVRT 1x Deblur
  ↓
FFV1ロスレス中間動画
  ↓
SeedVR2
  ↓
元動画の音声・メタデータを再mux
  ↓
MP4
```

RVRTとSeedVR2をGPUへ同時常駐させず、別プロセスで順番に実行します。

## AI処理時の中間形式

AI処理では不要な再圧縮を避けるため、PNGフレームまたはFFV1ロスレス動画を中間形式に使います。最終段階だけH.264へエンコードし、元動画の音声を戻します。

VFR動画はAI処理上フレーム列へ変換されるため、厳密な各フレーム時刻は保持せず、`ffprobe` の平均FPSを使うCFR動画として再構成します。

## 必要なもの

基本機能:

- Windows 11
- Python 3.10以降（Tkinterを含むWindows版）
- `ffmpeg`
- `ffprobe`

AI機能:

- RVRT公式リポジトリ + RVRT用Python環境
- SeedVR2 Standalone CLIリポジトリ + SeedVR2用Python環境
- NVIDIA GPU推奨

RVRTとSeedVR2は依存関係が異なるため、**別Python環境を推奨**します。

## AIエンジン設定

GUIの `AI設定...` から設定します。設定はローカルの `ai_config.json` に保存され、Git管理対象外です。

### RVRT

- `RVRTフォルダ`: `main_test_rvrt.py` があるフォルダ
- `RVRT Python`: RVRT依存関係を入れたPython
- `RVRTモデル`: GoPro Deblur / DVD Deblur

```powershell
git clone https://github.com/JingyunLiang/RVRT.git
```

RVRT公式スクリプトは必要な学習済みweightを初回実行時に取得します。

### SeedVR2

- `SeedVR2フォルダ`: `inference_cli.py` があるフォルダ
- `SeedVR2 Python`: SeedVR2依存関係を入れたPython
- Model / Batch / BlockSwap / 処理短辺

```powershell
git clone https://github.com/comfyorg/comfyui_seedvr2.git
```

Standalone CLIのセットアップは同リポジトリのREADMEに従ってください。

## 起動

エクスプローラーから `run.bat` をダブルクリックするか、PowerShellで:

```powershell
cd video-rotate-resize
python app_ai.py
```

`run.bat` も `app_ai.py` を起動します。

## 基本操作

1. 入力動画を選択。
2. 回転を選択。
3. 解像度を選択。
4. `AI鮮明化` から `なし / RVRT / SeedVR2 / RVRT → SeedVR2` を選択。
5. AIを使う場合は `AI設定...` でエンジンを登録。
6. `変換開始`。

**元解像度のまま鮮明化だけしたい場合**は、`回転 = なし`、`解像度 = 元の解像度` にしてAI方式だけ選択します。

## 4070 Ti SUPER 16GB向けSeedVR2初期値

```text
3B FP8
Batch = 5
BlockSwap = 20
Temporal overlap = 2
VAE tiling = ON
```

SeedVR2 Standalone側はVRAM消費が大きいため、16GBで必ずネイティブ1080p/4K処理できる保証はありません。OOM時はまず処理短辺を下げてください。

## 通常変換の標準画質

- NVENC: H.264 / preset `p6` / CQ 18
- CPU: H.264 / libx264 / CRF 18 / preset `medium`
- pixel format: `yuv420p`

## テスト

AIモデル自体をロードせず、コマンド生成・設定・動画変換コマンドをテストできます。

```powershell
python -m unittest -v
```

## 注意

- AI処理は通常変換より大幅に時間がかかります。
- SeedVR2は存在しなかった細部を生成する場合があります。
- RVRTは忠実度寄りですが、任意の実写劣化を完全に復元するモデルではありません。
- RVRT公式プロジェクトのライセンスは商用利用前に必ず確認してください。
- SeedVR2についても利用する実装・weightのライセンスを確認してください。
