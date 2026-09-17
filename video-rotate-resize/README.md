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

忠実度寄りの1x Video Restorationです。

利用可能なDeblurモデル:

- `005_RVRT_videodeblurring_GoPro_16frames`（既定 / 推奨）
- `004_RVRT_videodeblurring_DVD_16frames`

Windowsで古いRVRT公式コードのCUDA拡張をローカルビルドする代わりに、RVRT互換の `vsrvrt` バックエンドを専用環境へインストールします。学習済みweightは元のRVRTリリースを使用します。

長い動画は既定で16フレーム単位・4フレームオーバーラップに分割し、境界をブレンドします。RVRT内部ではVRAM量に応じた空間/時間タイルも利用します。

### SeedVR2

生成力の強いVideo Restorationです。`comfyorg/comfyui_seedvr2` のStandalone CLI (`inference_cli.py`) を使います。

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

高品質カスケードです。

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

## AI自動セットアップ

GUIの **`AI自動セットアップ`** を押すと、AI用環境を自動構築します。

自動処理:

1. Python 3.12を検索。
2. WindowsでPython 3.12が無ければ `winget` でユーザー領域へインストール。
3. `ai_engines/SeedVR2/` にSeedVR2をcloneし、アプリと互換確認済みのrevisionへ固定。
4. `.venv-rvrt/` を作成。
5. RVRT用CUDA PyTorch + `vsrvrt` をインストール。
6. `.venv-seedvr2/` を作成。
7. SeedVR2用CUDA PyTorch + requirementsをインストール。
8. CUDA / RVRTバイナリ / SeedVR2 CLIを検証。
9. 生成したパスを `ai_config.json` へ自動登録。

途中で失敗した場合は、問題を修正後にもう一度 `AI自動セットアップ` を押してください。既存clone/venvを再利用して再実行します。

GUIを使わずセットアップだけ実行する場合:

```powershell
.\setup_ai.bat
```

### 自動セットアップの配置

```text
video-rotate-resize/
├─ ai_engines/
│  └─ SeedVR2/          # cloneしたSeedVR2
├─ .venv-rvrt/          # RVRT専用環境
├─ .venv-seedvr2/       # SeedVR2専用環境
├─ ai_config.json       # ローカル設定
└─ ...                  # Git管理するアプリ本体
```

`ai_engines/`、`.venv-*`、`ai_config.json`、モデル/キャッシュ類は `.gitignore` 対象です。**AI本体・仮想環境・ダウンロードモデルがasobibaのGitへ追加されることはありません。**

RVRT weightは `vsrvrt` のユーザーキャッシュへ、SeedVR2 weightはSeedVR2側のモデルディレクトリへ初回使用時に自動取得されます。

## 必要なもの

通常機能:

- Windows 11
- Python 3.10以降（Tkinterを含むWindows版）
- `ffmpeg`
- `ffprobe`

AI自動セットアップ:

- NVIDIA GPU
- 新しいNVIDIAドライバ
- Git for Windows (`git`)
- インターネット接続
- `winget`（Python 3.12が未導入の場合のみ）
- 数GB以上の空きディスク容量

AI用Python 3.12は通常のアプリ起動Pythonとは分離されます。

## 固定しているAIランタイム

再現性を優先し、セットアップ時に主要バージョンを固定しています。

### RVRT

- Python 3.12 venv
- `vsrvrt == 1.1.3`
- `torch == 2.7.1`
- CUDA 12.8 wheel index
- FP16推論

### SeedVR2

- Python 3.12 venv
- SeedVR2 standalone CLI互換revisionへ固定
- `torch == 2.6.0`
- `torchvision == 0.21.0`
- `torchaudio == 2.6.0`
- CUDA 12.6 wheel index

上流リポジトリの更新で突然CLIが壊れないよう、SeedVR2は自動セットアップ時に既知互換revisionへdetached checkoutします。

## AI処理時の中間形式

AI処理では不要な再圧縮を避けるため、PNGフレームまたはFFV1ロスレス動画を中間形式に使います。最終段階だけH.264へエンコードし、元動画の音声を戻します。

VFR動画はAI処理上フレーム列へ変換されるため、厳密な各フレーム時刻は保持せず、`ffprobe` の平均FPSを使うCFR動画として再構成します。

## 起動

エクスプローラーから `run.bat` をダブルクリックするか、PowerShellで:

```powershell
cd video-rotate-resize
python app_ai.py
```

`run.bat` も `app_ai.py` を起動します。

## 初回操作

1. `run.bat` で起動。
2. `AI自動セットアップ` を押す。
3. セットアップ完了後、入力動画を選択。
4. 回転・解像度を設定。
5. `AI鮮明化` から `RVRT / SeedVR2 / RVRT → SeedVR2` を選択。
6. `変換開始`。

**元解像度のまま鮮明化だけしたい場合**は、`回転 = なし`、`解像度 = 元の解像度` にしてAI方式だけ選択します。

## 手動AI設定

`AI設定...` では自動セットアップ後の値を上書きできます。

RVRT:

- RVRT Python
- GoPro / DVD Deblurモデル
- Chunk size / overlap

SeedVR2:

- SeedVR2フォルダ
- SeedVR2 Python
- Model
- Batch
- BlockSwap
- 処理短辺

通常は自動セットアップの値をそのまま使用してください。

## 4070 Ti SUPER 16GB向けSeedVR2初期値

```text
3B FP8
Batch = 5
BlockSwap = 20
Temporal overlap = 2
VAE tiling = ON
```

16GBでネイティブ1080p/4K処理できる保証はありません。OOM時はまずSeedVR2の処理短辺を下げてください。

RVRTはFP16 + 256px空間タイル + 短い時間チャンクを利用するため、SeedVR2より16GB環境で扱いやすい構成です。

## 通常変換の標準画質

- NVENC: H.264 / preset `p6` / CQ 18
- CPU: H.264 / libx264 / CRF 18 / preset `medium`
- pixel format: `yuv420p`

## テスト

AIモデル自体をロードせず、コマンド生成・設定・自動セットアップ配置・動画変換コマンドをテストできます。

```powershell
python -m unittest -v
```

実際のCUDA推論はローカルGPU上での初回テストが必要です。

## 注意

- 初回AIセットアップは大きなPyTorch wheel等を取得するため時間と通信量を使います。
- AI処理は通常変換より大幅に時間がかかります。
- SeedVR2は存在しなかった細部を生成する場合があります。
- RVRTは忠実度寄りですが、任意の実写劣化を完全に復元するモデルではありません。
- RVRT / `vsrvrt` はCC-BY-NC系ライセンスです。商用利用時はライセンス条件を確認してください。
- SeedVR2についても利用する実装・weightのライセンスを確認してください。
