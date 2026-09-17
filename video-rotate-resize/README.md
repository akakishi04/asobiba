# Video Rotate & Resize

Windows向けの小さなGUI動画変換ツールです。FFmpegを使って、動画の**実ピクセル回転**と**解像度変更**を1回の変換で行います。

## 機能

- 回転
  - なし
  - 時計回り90°
  - 反時計回り90°
  - 180°
- 解像度
  - 元の解像度
  - 1080p (1920×1080)
  - 720p (1280×720)
  - 4K (3840×2160)
  - カスタム
- NVIDIA NVENC (`h264_nvenc`) を自動検出して優先使用
- NVENCが使えない場合は `libx264` にフォールバック
- 音声は可能な限り再エンコードせずコピー
- 進捗表示、ログ表示、キャンセル
- 解像度変更ではアスペクト比を維持し、余った領域を黒帯で埋めるため映像を潰しません

## 必要なもの

- Windows 11
- Python 3.10以降（Tkinterを含む通常のWindows版Python）
- `ffmpeg` と `ffprobe` がPATHから実行できること

確認例:

```powershell
ffmpeg -version
ffprobe -version
```

## 起動

エクスプローラーから `run.bat` をダブルクリックするか、PowerShellで:

```powershell
cd video-rotate-resize
python app.py
```

## 基本操作

1. 「入力動画」の「参照...」から動画を選択する。
2. 回転方向を選ぶ。
3. 解像度を選ぶ。縦4Kを横1080pにする場合は「時計回り90°」+「1080p (1920×1080)」。
4. 「変換開始」を押す。
5. 入力動画と同じフォルダに、初期値では `<元ファイル名>_converted.mp4` が出力される。

## 変換方針

このアプリは回転メタデータだけを書き換える方式ではなく、FFmpegのフィルターで実際の映像を回転します。そのため再エンコードは発生しますが、プレイヤーごとの回転メタデータ解釈差に依存しません。

標準画質設定:

- NVENC: H.264 / preset `p6` / CQ 18
- CPU: H.264 / libx264 / CRF 18 / preset `medium`
- pixel format: `yuv420p`

## テスト

FFmpegを実行しないコマンド生成テスト:

```powershell
python -m unittest test_video_tool.py -v
```
