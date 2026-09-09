# ローカル学習ガイド

更新: 2026-09-09。小型試作の実行手順。CPUで実行検証済み、Windows/CUDA実機は未検証。

## 1. 取得とPython環境

Windows PowerShellの例。Python 3.11〜3.13を想定し、実測は3.13.5です。Python未導入の場合は先に導入してください。

```powershell
git clone https://github.com/akakishi04/asobiba.git
cd asobiba\fold
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

既にクローンしている場合は、そのリポジトリで変更を確認して `git pull --ff-only` し、`fold/` に移動します。未コミットの変更を消す操作は不要です。

以下のPyTorchインストールは **CPUかNVIDIA GPUのどちらか一方** を選びます。既存のグローバルPython環境ではなく、この仮想環境へ入れます。

```powershell
# CPU用
.\.venv\Scripts\python.exe -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu

# NVIDIA GPU用の選択肢（CUDA 12.8対応ビルド。対応GPU/ドライバが必要）
# .\.venv\Scripts\python.exe -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128

# 共通の依存を揃えて確認
.\.venv\Scripts\python.exe -m pip install -r requirements-training.txt
.\.venv\Scripts\python.exe -m fold_lm doctor
.\.venv\Scripts\python.exe -m fold_lm init
```

PyTorch 2.10.0のCPU/cu128配布先は[公式の過去バージョン一覧](https://pytorch.org/get-started/previous-versions/#v2100)に基づきます。GPUを使うつもりなのにdoctorが `cuda_available: false` の場合、学習前にインストールとドライバを確認します。`--device cuda` は使えない場合に失敗し、黙ってCPUへ切り替えません。`--device auto` はCUDAが使えればCUDA、それ以外はCPUです。

Linuxでは `python3 -m venv .venv` と `.venv/bin/python` を使います。macOSのMPSは対象外で、CPU経路のみです。依存のダウンロードに通信は使いますが、データ前処理・学習・生成コードはネットワークへアクセスしません。

## 2. データを置く

```text
fold/
  data/                    Git管理対象外
    raw/                   自分で置くUTF-8ファイル
      notes.txt
      corpus.jsonl
    processed/             prepareが新しく作る
  runs/                    Git管理対象外
  configs/                 共有設定なのでGit管理対象
```

### TXT

**空行で区切った段落を、それぞれ独立した文書として扱います。** UTF-8（BOMありも可）です。単一の巨大ファイルに空行が一つもない場合、文書が一つになるため自動の学習/検証分割はできません。文書単位で分けるか、別の検証ファイルを指定します。

### JSONL

1行に1個のオブジェクト。`text` は必須の文字列です。追加のフィールドは学習に使いません。

```jsonl
{"text":"最初の文章です。"}
{"text":"Aは1。BはAより2大きい。CはBより3大きい。Cは6。"}
{"text":"利用者：こんにちは。\n応答：こんにちは。"}
```

空文字はスキップ、壊れたJSONや `text` の欠落はエラーにします。`messages` 形式の会話データは自動変換しません。必要な話者・区切りを含む `text` へ事前に整形してください。初版は全文の次トークン損失であり、アシスタントの回答部分だけに損失をかけるSFTではありません。

同じ内容は完全一致のハッシュで重複排除します。近似重複や同じ話題の派生文書は検出しません。段落単位の自動分割で同一作品の別段落が両側へ入る場合があるため、厳密な評価では出典・作品・生成テンプレートなどを分けた明示的な検証データを用意します。単一文書16 MiB超は、黙って切り捨てずエラーにします。

## 3. 前処理

全コマンドは `fold/` から実行します。以下は `python` が仮想環境を指している表記です。PowerShellでactivateしない場合、`python`を `.\.venv\Scripts\python.exe` に置き換えます。

```bash
python -m fold_lm prepare --input data/raw --output data/processed
```

文書ハッシュとseedによって、既定では約90%/10%に分けます。小さなデータでは片方が空になる場合があり、その場合は成功扱いにしません。分割後に各文書を系列へ切り出すため、文書をまたぐ教師ラベルは作りません。

検証データを自分で分ける場合:

```bash
python -m fold_lm prepare --input data/raw/train --val-input data/raw/val --output data/processed
```

同じ文書が両方に入っていたらエラーにします。既に存在する出力ディレクトリは上書きしません。データを更新した場合は `data/processed-v2` など新しい出力先にしてください。学習再開時は元の加工済みデータが必要です。

トークナイザは追加ダウンロード不要の **UTF-8 byte、語彙259**（256 byte + PAD/BOS/EOS）です。日本語に未知文字はありませんが、1文字が複数tokenになります。通常のBPE/サブワードLMとperplexityを直接比較しないでください。

出力は `train.bin` / `val.bin`、文書索引、トークナイザ仕様とSHA-256を含む `manifest.json` です。学習開始時に整合性を検査し、入力はメモリマップで読みます。巨大データでは全ファイルのハッシュ検査と文書ハッシュ・索引のメモリ費用が生じます。

## 4. 学習開始

```bash
python -m fold_lm train --config configs/local-small.json --data data/processed --out runs/first --device auto
```

既定は383,796パラメータ、2層、width 128、局所窓64、系列256 byte token、batch 4、2,000 optimizer stepsです。これは実行確認・研究用の小型モデルで、一般的な大規模会話モデルではありません。

`configs/smoke.json` は20,174パラメータの動作確認用。共有configをコピーし、`seq_len`、`batch_size`、`grad_accum`、層数などを調整できます。`grad_accum` は実効バッチを増やしますが、学習予算が同じになるとは限りません。全ての設定と環境はrunに記録します。学習率は初版では一定です。

```text
runs/first/
  last.pt            定期保存された再開用のモデル・optimizer・乱数状態
  best.pt            観測した検証損失が最小だったcheckpoint
  metrics.jsonl      step、学習/検証損失、token数など
  config.json        実際の設定
  environment.json   実行環境
  summary.json       正常終了時の要約
```

既定では100 stepごとと終了時に保存します。`max_steps` の指定で、実験の長さを明示的に変更できます。既存runへ新規学習を上書きすることは拒否します。runの `.training.lock` で同時書き込みを防ぎます。異常終了で残ったlockは、該当runの学習プロセスが動いていないことを確認してから、そのlockだけを手動削除してください。

初版の学習はFP32、単一CPU/CUDA device、ランダムに選んだ文書内の系列ブロックを使用します。**学習ブロックごとに作業記憶を初期化し、ブロック内のchunk間では勾配を切りません。** 全文ストリームをまたいで状態を保持するTBPTTや分散学習、AMPはまだありません。

## 5. 中断と再開

Ctrl+Cで停止できます。中途半端なoptimizer更新を保存しないため、再開位置は最後に完全保存されたcheckpointです。保存間隔内の未保存stepは再実行します。

```bash
python -m fold_lm train --resume runs/first/last.pt --max-steps 4000 --device auto
```

`4000`は通算の到達目標です。モデル設定・optimizer・乱数・samplerを復元します。再開時に別の `--config` を同時指定することは拒否します。別のパスへ移した同一データなら `--data` を追加できますが、fingerprintが異なるデータへの継続は拒否します。CPU/GPU/ライブラリを変更した場合のビット単位再現は保証しません。

checkpointは `torch.load(..., weights_only=True)` で読みます。自分で作った信頼できるcheckpointを使用してください。[公式の保存・読み込み説明](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html)も参照。

## 6. 評価・文章生成

```bash
python -m fold_lm evaluate --checkpoint runs/first/best.pt --device auto
python -m fold_lm generate --checkpoint runs/first/best.pt --prompt "こんにちは" --max-new-tokens 200
```

`evaluate` は既定で加工済みデータの検証側を全件評価します。学習途中の既定評価は最大20 batchなので、全件評価と数値が一致しない場合があります。検証側をモデル選択に使っているため、これは独立した最終test成績ではありません。

長いpromptは `--prompt-file data/prompt.txt` でも渡せます。生成時は局所KVとFOLD-R状態を引き継ぎ、prompt全体のlogitsを保持せずchunkで処理します。`--temperature 0` はgreedy、`--top-k 0` はtop-k制限なしです。

`max-new-tokens`もbyte単位です。未学習に近いモデルは不正なUTF-8 byte列を出すことがあり、表示では置換文字になります。短い動作確認学習から、自然な会話や正しい算術ができるとは限りません。

## 7. データなしで動作確認する場合

本番のrawデータと混ぜないよう、別ディレクトリを使います。

```bash
python -m fold_lm sample-data --output data/smoke-raw/sample.jsonl --documents 300
python -m fold_lm prepare --input data/smoke-raw --output data/smoke-processed
python -m fold_lm train --config configs/smoke.json --data data/smoke-processed --out runs/smoke --device cpu
python -m unittest discover -s tests_lm -v
```

人工データは英語・日本語の関係問題のテンプレートです。loss低下は学習経路の動作確認であり、関係推論、長期訂正、未知テンプレートへの汎化を実証するベンチマークではありません。

## 実装の境界

`docs/architecture-v0.2.md` は全体の目標設計として維持します。この実装は小型学習経路を先に開通させる独立試作です。`research-plan.md` のP1〜P10全体を合格した扱いにはしません。

| 項目 | この試作 |
|---|---|
| 微分可能なFOLD-Rカプセル | y0/g/V/Kのcompileとresponseを実装。署名付き更新、撤回、有限差分を独立テスト |
| LMの短期経路 | 固定窓Attention、Dense gated FFN、残差・LayerNorm、byte埋め込みと共有出力重み |
| LMの長期経路 | 固定数のbank、固定Q/U、学習するベースJ/etaとWriter/Reader。LMからは正の因子追加だけ |
| 固定shape/chunk | 同shapeの更新をcausal prefix sumで集計しbatched solve。chunk境界で累積状態を引き継ぐ |
| 未commit操作への応答 | chunk内の現在tokenまでの更新を含んで読む。未来tokenを含めない |
| 完全なH1/H2運用 | 未実装。意味的なfactor ID、scope、archive、圧縮時期・境界選択はない |
| 意味的な訂正 | 未実装。文章中のRETRACT/REPLACEを正しい操作へ変換する保証はない |
| Capability Contract | 数理APIは指定ポート座標だけを受ける。自然言語要求のcoverage分類器はない |
| GPU最適化、MoE、MTP | 未実装。GPU実時間・メモリ優位は未計測 |

Q/Uは固定、Jは明示したprior `I + A A^T` とします。通常LM経路でのJ更新はPSD因子の追加なので正定値性を保つ設計ですが、条件数の悪化や有限精度問題がなくなるわけではありません。無言のjitterやforgettingは使いません。損失・勾配の非有限値はエラーにします。

カプセル演算は[PyTorchのsolve](https://docs.pytorch.org/docs/2.10/generated/torch.linalg.solve.html)を使います。[SDPA](https://docs.pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html)はchunkと有限KV窓にのみ適用します。記憶状態が小さいことだけで、学習activation・optimizer・索引・入出力まで省メモリとは主張しません。

## Git除外の確認

`fold/` で確認できます。

```bash
git check-ignore -v data/raw/private.txt data/processed/train.bin runs/first/last.pt runs/first/metrics.jsonl
git status --short
```

`data/`内は生データも加工済みデータも丸ごと除外します。`.gitignore`は既に追跡されているファイルを履歴から消す機能ではなく、`git add -f`も防ぎません。今回確認した更新前のリポジトリにはデータ用ディレクトリの追跡ファイルはありません。GitHubに反映するのはコード・共有設定・文書だけです。
