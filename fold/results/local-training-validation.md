# ローカル学習経路の検証記録

実行日: 2026-09-09。実行場所: 作成時のLinuxコンテナ。GitHub Actionsではない。

変更前のリポジトリ: `c8ea82dadf2d44361dcbc41c530d8abce0af3670`。
検証対象ソースのSHA-256: `e24ccd0bc74d5e2c09706615f9946dfa854dc26b39f1d2c4603ff30ac558e067`。
これは `fold_lm/*.py`、`tests_lm/*.py`、`configs/*.json` を相対パス順に並べ、各々の `path + NUL + bytes` を連結したハッシュ。

## 環境

Python 3.13.5、PyTorch 2.10.0+cpu、NumPy 2.3.5、CPU、FP32（カプセル精度・gradcheckはFP64）。学習時CPU threadsは2。

## 実行と結果

```bash
python -m fold_lm init
python -m fold_lm sample-data --documents 300
python -m fold_lm prepare
python -m fold_lm train --config configs/smoke.json --out runs/smoke --device cpu
python -m fold_lm evaluate --checkpoint runs/smoke/best.pt --device cpu
python -m fold_lm generate --checkpoint runs/smoke/best.pt --prompt 'A=1. B=A+2. C=B+3. Question: C? Answer:' --max-new-tokens 40 --temperature 0 --device cpu
python -m fold_lm train --resume runs/smoke/last.pt --max-steps 42 --device cpu
python -m fold_lm train --config configs/local-small.json --out runs/default-check --device cpu --max-steps 2
python -m unittest discover -s tests_lm -v
python -m compileall -q fold_lm tests_lm
```

| 項目 | 結果 |
|---|---|
| 新しい独立テスト | 22件通過 |
| カプセル数値比較 | 指定ポート内の更新列・圧縮前の因子撤回で元のfull solveと一致 |
| 勾配 | double精度の有限差分gradcheck通過。Writer/Reader/base J/base etaへ非ゼロ勾配 |
| 因果性 | 後続入力を変更してもprefix出力が一致 |
| 生成状態 | 1-token逐次実行とchunk実行が許容誤差内で一致。KVは固定窓に収まる |
| 学習再開 | CPUで6step連続と4step保存+2step再開のモデルstate_dictが完全一致 |
| データ検査 | 文書重複・train/val重複・壊れたデータ・上書きを検出 |
| 同時run保護 | 他プロセスのlockを消さずに実行を拒否 |
| 元データ | ローカル生成した300文書。train 277 / val 23 |
| 加工済みtoken数 | train 22,914 / val 1,983（BOS/EOSを含む） |
| smoke（20,174 parameters） | 40step学習・checkpoint保存に成功 |
| 固定検証subsetのNLL | step 0: 5.5880625765 → step 40: 2.6273674158 |
| 上記subset | 16 blocks、881 target tokens。両時点で同一subset |
| step 40の全validation NLL | 2.6208076944（36 blocks、1,960 target tokens） |
| 実CLIでの再開 | step 40 → 42に成功。subset NLL 2.5247008792 |
| small既定形状（383,796 parameters） | 2step学習成功。全validation NLL 5.5902318215 → 5.3468242412 |
| 生成コマンド | CPUで終了コード0。40stepモデルのgreedy出力は空白反復で、有用な回答ではない |
| 構文チェック | compileall通過 |

データfingerprint: `ec4ac3e4aef9d9e67f136e54bd330090766182756b4153fd1d781c79288b038f`。
loss低下は配線・最適化の確認であり、算術能力、言語理解、訂正性能の成功判定ではない。

## Git除外

`git check-ignore -v` で以下が `fold/.gitignore` によって除外されることを確認:

- `fold/data/raw/private.txt`, `fold/data/raw/private.jsonl`
- `fold/data/processed/train.bin`
- `fold/runs/first/last.pt`, `fold/runs/first/metrics.jsonl`
- `fold/checkpoints/model.safetensors`, `fold/.env`

ローカルの生成データ、checkpoint、metrics、仮想環境はコミット対象に含めない。

## 未検証・変更していない範囲

Windows実機、CUDA実機、大量データ、一般的な会話能力、意味的な訂正、長期ストリーム学習、動的なport/capability学習、GPU実時間・総メモリの優劣、MoE/MTPは未検証・未実装。CPU試験をGPUの性能結果と呼ばない。

既存の `fold_memory.py` / `demo.py` / `tests/` / v0.1 baselineは変更していない。この作業では新設の `tests_lm/` を検証し、既存28テストの再実行結果を新たに主張しない。
