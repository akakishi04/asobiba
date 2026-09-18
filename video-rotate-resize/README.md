# Video Rotate, Resize & AI Restore

Windows向けのGUI動画変換ツールです。従来の**実ピクセル回転 / 解像度変更**を維持しつつ、解像度を維持した動画復元として **RVRT / SeedVR2 / RVRT → SeedVR2** を追加しています。

## 機能

### 通常変換

- 動画ファイルをウィンドウまたは「入力動画」欄へDrag & Drop
- 回転: なし / 時計回り90° / 反時計回り90° / 180°
- 解像度: 元の解像度 / 1080p / 720p / 4K / カスタム
- NVIDIA NVENC (`h264_nvenc`) を自動検出して優先
- NVENCが使えない場合は `libx264` にフォールバック
- 音声は可能な限りコピー
- アスペクト比維持 + 必要時は黒帯
- ログ、進捗、キャンセル

AIを「なし」にすれば従来どおりFFmpegだけで処理します。

### Drag & Drop

`run.bat` から起動した場合、動画をGUIへ直接ドロップできます。

対応拡張子:

- `.mp4`
- `.mov`
- `.mkv`
- `.m4v`
- `.avi`
- `.webm`

複数ファイルを同時にドロップした場合は、現在の単一入力設計に合わせて最初の対応動画を入力へ設定します。スペースを含むWindowsパスにも対応します。

D&Dには `tkinterdnd2` を利用します。未導入の場合、`launcher.py` が現在のアプリ用Pythonを使って次のローカルフォルダへ自動導入します。

```text
video-rotate-resize/.app_deps/
```

`.app_deps/` はGit管理対象外です。D&D依存関係の導入に失敗した場合でも、アプリ自体は従来の「参照...」ボタンを使える状態で起動します。

### RVRT

忠実度寄りの1x Video Restorationです。

利用可能なDeblurモデル:

- `005_RVRT_videodeblurring_GoPro_16frames`（既定 / 推奨）
- `004_RVRT_videodeblurring_DVD_16frames`

Windowsで古いRVRT公式コードのCUDA拡張をローカルビルドする代わりに、RVRT互換の `vsrvrt` バックエンドを専用環境へインストールします。学習済みweightは元のRVRTリリースを使用します。

長い動画は既定で16フレーム単位・4フレームオーバーラップに分割し、境界をブレンドします。入力動画はFFmpegを1回だけ起動して `rawvideo` pipeで連続供給するため、チャンクごとのFFmpeg再起動や全動画PNG展開は行いません。復元済みフレームも確定したものからFFV1へ順次書き込み、RAMには境界Overlap分だけを残します。

### SeedVR2

生成力の強いVideo Restorationです。`comfyorg/comfyui_seedvr2` の固定revisionを利用します。セットアップ時の互換確認にはStandalone CLIを使いますが、実際の長尺処理は同revisionのgeneration APIを直接利用し、モデルを1回だけロードしたまま全チャンクを処理します。

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
- 長尺Chunk: `45` フレーム
- 長尺Overlap: `5` フレーム

入力は先頭から1回だけ順次読み込み、過去フレームをチャンクごとに再スキャンしません。処理済み出力は大量PNGではなくFFV1ロスレス動画へ逐次書き込みます。高解像度でVRAM不足になる場合は、AI設定の「処理短辺」を `1440` / `1080` / `1072` などへ下げられます。最終MP4は指定した出力解像度へ戻します。

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

RVRTとSeedVR2をGPUへ同時常駐させず、別プロセスで順番に実行します。RVRTのFFV1出力をSeedVR2が直接読み込むため、両者の間で数万枚のPNGへ展開し直しません。

## 実行負荷 / GPU余力

`AI設定...` の **実行負荷** から次のプロファイルを選べます。

- **最大速度**: GPUデューティ目標 100%。現在のBlockSwap値をそのまま使用。
- **バランス**: 75%。Windows子プロセスを低優先度にし、SeedVR2 BlockSwapを最低24へ引き上げ。
- **他作業優先**: 50%。低優先度 + SeedVR2 BlockSwapを最低28へ引き上げ。
- **カスタム**: 20〜100%のGPUデューティ目標を指定。

GPUデューティ目標はドライバ側のハードな使用率制限ではありません。RVRTではチャンク境界、SeedVR2では内部Batch境界で実測処理時間に応じた休止を挟み、平均的な計算負荷を下げます。そのため「他作業優先」でもAI処理中の瞬間的なGPU使用率が高くなることはあります。SeedVR2はBlockSwapも強めるためVRAM余力も増えやすい一方、RVRTはバックエンドのモデル常駐分まで厳密に予約制御するものではありません。

プロファイルは解像度や復元モデルを勝手に下げません。時間がかかっても画質設定を維持しながら別作業をしやすくするための設定です。

## 一時停止 / 再開

RVRT / SeedVR2 のAI復元中は **一時停止** ボタンを利用できます。OSレベルでCUDAプロセスを強制Suspendするのではなく、安全な推論境界で協調停止します。

- RVRT: 現在のChunk完了後に停止
- SeedVR2: 現在の内部BatchまたはPhase境界で停止
- 停止中は可能な範囲で現在のAIモデルをGPUからCPUへ退避し、`torch.cuda.empty_cache()` でVRAMを返却
- 再開時は必要なモデルだけGPUへ戻して、その位置から処理継続
- Pause中の待ち時間はETA速度サンプルに含めない
- キャンセルはPauseとは別で、従来どおり処理を終了

ボタンを押した直後は「一時停止要求中」と表示されます。GPUカーネルの途中では停止しないため、現在のChunk/Batchが重い場合は実際に「一時停止中」へ移るまで時間がかかることがあります。停止中はモデルをCPUへ退避するため、システムRAM使用量は増える場合があります。

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
├─ .app_deps/           # D&Dなど軽量GUI依存
├─ ai_config.json       # ローカル設定
└─ ...                  # Git管理するアプリ本体
```

`ai_engines/`、`.venv-*`、`.app_deps/`、`ai_config.json`、モデル/キャッシュ類は `.gitignore` 対象です。**AI本体・仮想環境・ダウンロードモデル・ローカルGUI依存がasobibaのGitへ追加されることはありません。**

RVRT weightは `vsrvrt` のユーザーキャッシュへ、SeedVR2 weightはSeedVR2側のモデルディレクトリへ初回使用時に自動取得されます。

## 必要なもの

通常機能:

- Windows 11
- Python 3.10以降（Tkinterを含むWindows版）
- `ffmpeg`
- `ffprobe`
- インターネット接続（D&D用 `tkinterdnd2` の初回自動導入時のみ。D&D不要ならなくても通常の参照操作は可能）

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

最適化経路ではAI間の受け渡しと復元結果の逐次保存にFFV1ロスレス動画を使います。RVRT入力はFFmpeg `rawvideo` pipe、SeedVR2入力は動画を順次読み込む方式で、動画全体をPNGへ展開しません。最終段階だけH.264へエンコードし、元動画の音声を戻します。

処理中の一時ファイルは完成動画の出力先フォルダに `.video_ai_XXXXX/` として作成され、正常終了・キャンセル時に削除されます。新方式では一時ディレクトリに数万枚のPNGを保持しません。

VFR動画はAI処理上フレーム列へ変換されるため、厳密な各フレーム時刻は保持せず、`ffprobe` の平均FPSを使うCFR動画として再構成します。

## 起動

D&Dを含む通常起動は `run.bat` を使用してください。

```powershell
cd video-rotate-resize
.\run.bat
```

PowerShellからPythonで直接起動する場合:

```powershell
python launcher.py
```

`launcher.py` はD&D依存関係を `.app_deps/` へ必要時だけ導入した後、既存の `app_ai.py` を起動します。`python app_ai.py` で直接起動した場合はAI/回転/リサイズ機能は使えますが、D&D拡張は注入されません。

## 初回操作

1. `run.bat` で起動。
2. 必要なら `AI自動セットアップ` を押す。
3. 動画をウィンドウへD&Dするか「参照...」から入力動画を選択。
4. 回転・解像度を設定。
5. `AI鮮明化` から `なし / RVRT / SeedVR2 / RVRT → SeedVR2` を選択。
6. `変換開始`。

**元解像度のまま鮮明化だけしたい場合**は、`回転 = なし`、`解像度 = 元の解像度` にしてAI方式だけ選択します。

## 手動AI設定

`AI設定...` では自動セットアップ後の値を上書きできます。

共通:

- 実行負荷: 最大速度 / バランス / 他作業優先 / カスタム
- カスタム時GPUデューティ目標: 20〜100%

RVRT:

- RVRT Python
- GoPro / DVD Deblurモデル
- Chunk / Overlap（フレーム数）

SeedVR2:

- SeedVR2フォルダ
- SeedVR2 Python
- Model
- Batch
- BlockSwap
- 処理短辺
- 長尺Chunk / Overlap（フレーム数）

通常は自動セットアップの値をそのまま使用してください。

## 4070 Ti SUPER 16GB向けSeedVR2初期値

```text
3B FP8
Batch = 5
BlockSwap = 20
Temporal overlap = 2
VAE tiling = ON
```

16GBでネイティブ1080p/4K処理できる保証はありません。OOM時はまず「他作業優先」またはBlockSwap増加を試し、それでも不足する場合に処理短辺を下げてください。

RVRTはFP16 + 短い時間チャンクを利用します。新しいrawvideo pipe経路では入力PNGの書き出し・読み戻しを行わず、モデルは動画全体で1回だけロードします。

## 通常変換の標準画質

- NVENC: H.264 / preset `p6` / CQ 18
- CPU: H.264 / libx264 / CRF 18 / preset `medium`
- pixel format: `yuv420p`

## テスト

AIモデル自体をロードせず、コマンド生成・設定・自動セットアップ配置・動画変換コマンドをテストできます。

```powershell
python -m unittest -v
```

ソースレベルではストリーミング経路・リソースプロファイル・コマンド生成をテストします。実際のD&Dと、RVRT/SeedVR2の新しいpersistent streaming経路はWindows + ローカルGPU上での実機検証が必要です。

## 注意

- 初回D&D起動時は `tkinterdnd2` を `.app_deps/` へ取得します。
- 初回AIセットアップは大きなPyTorch wheel等を取得するため時間と通信量を使います。
- AI処理は通常変換より大幅に時間がかかります。
- SeedVR2は存在しなかった細部を生成する場合があります。
- RVRTは忠実度寄りですが、任意の実写劣化を完全に復元するモデルではありません。
- RVRT / `vsrvrt` はCC-BY-NC系ライセンスです。商用利用時はライセンス条件を確認してください。
- SeedVR2についても利用する実装・weightのライセンスを確認してください。
