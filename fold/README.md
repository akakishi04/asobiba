# FOLD-R — 訂正応答型・関係圧縮メモリ

**状態: アーキテクチャ研究案 + FOLD v0.1数学カーネルの参照実装。FOLD-R言語モデルは未実装です。**

FOLD-Rは、長い履歴をtoken列のまま保持する代わりに、潜在的な関係と「どの問い合わせ・訂正に応答できる状態を残すか」を学習し、長期記憶を訂正可能な応答capsuleへ圧縮するLLMアーキテクチャ案です。

> 「何を覚えるか」だけでなく、**何を後から問い合わせ・訂正できる状態で残すか**を学習する。

Schur補完、低ランク行列更新、local attention、MoE、multi-token predictionなどの基礎要素そのものは既知です。FOLD-Rの新規性、言語能力、Transformer/SSM等への優位性は未検証です。

## 現在の正規設計

**[docs/architecture-v0.2.md](docs/architecture-v0.2.md)** を現在の正規アーキテクチャとします。

```text
Token
  ↓
Fixed-window Local Context Mixer
  ↓
Writer / Memory Controller
  ↓
H1 Hot Relational Buffer
  ↓ chunk commit
FOLD-R Capsule Compiler
  ↓
H2 Response Capsule Bank
  ↕ Reader
Context / Memory Fusion
  ↓
Dense baseline → conditional compute ablation
  ↓
Next-token head + optional MTP heads
```

正規構成には**global full-history self-attentionを含めません**。短期文脈は固定窓、長期記憶はFOLD-Rで担当させます。

v0.2では、長文Attention/KVだけでなく、FOLD-Rが成功した後に支配的になり得る次のボトルネックも設計上分離しました。

- Dense FFNのweight bandwidth
- 1-token自己回帰decodeの逐次性
- 動的グラフ・小行列solveのGPU非効率
- 学習時activation / optimizer / multi-GPU通信

ただし、これらを一度に新方式へ置換しません。**まずFOLD-Rの長期記憶効果を成立させ、その後に実測で残ったボトルネックだけを置換します。**

## 文書

| ファイル | 内容 |
|---|---|
| [docs/architecture-v0.2.md](docs/architecture-v0.2.md) | **正規設計**。記憶階層、FOLD-R capsule、Capability Contract、GPU制約、FFN/MTP方針 |
| [docs/theory.md](docs/theory.md) | FOLD v0.1の数学的背景、Schur補完、保証条件、限界、先行研究 |
| [docs/research-plan.md](docs/research-plan.md) | v0.2を実装・学習・比較する段階計画と合否基準 |
| [fold_memory.py](fold_memory.py) | v0.1 float64密行列参照実装。関係追加、求解、境界圧縮 |
| [demo.py](demo.py) | 3変数例、ランダム検証、内部更新とfill-inの反例 |
| [tests/test_fold_memory.py](tests/test_fold_memory.py) | v0.1数学的性質・失敗条件の28テスト |
| [results/baseline.json](results/baseline.json) | v0.1固定seed実行結果 |
| [results/validation.md](results/validation.md) | v0.1検証環境・結果・検証対象外 |
| [AGENTS.md](AGENTS.md) | このフォルダを扱う開発エージェント向け指針 |

## 現在実装済みの範囲

現在リポジトリに実装済みなのは**FOLD v0.1の二次形式メモリ**です。

```text
B - A = 2, C - B = 3
          ↓ Bを消去
       C - A = 5

A = 1 を与える → 圧縮前後とも C = 6
A = 4 を別条件として与える → 圧縮前後とも C = 9
```

これは、残した境界へのprofile energyをSchur補完で保存する参照実装です。消した内部への任意の後続訂正には対応しません。

FOLD-R v0.2では、この弱点を中心課題に変え、**保護する読み出し方向Qと訂正方向UをcapsuleのCapability Contractとして持ち、その範囲内の訂正列に応答する設計**へ進めます。

## まだ未実装

- FOLD-R response capsuleの正規リポジトリ実装
- `ASSERT / RETRACT / REPLACE / ASSUME / QUERY` のMemoryOp意味論
- H1 Hot Bufferとchunk commit
- Capability Contract / coverage判定
- PyTorch微分可能カーネル
- ニューラルWriter / Reader / Router / Port Selector
- tokenizer、embedding、Local Context Mixer、LM Head
- fixed-shape GPU bucket / batched solve
- conditional compute
- multi-token prediction / speculative decode
- 一般文章または会話データでの学習

したがって、現段階で「Transformerを置換できた」「高速化できた」とは扱いません。

## v0.1参照実装の実行

Python 3.11以上を想定。保存済み結果は **Python 3.13.5 / NumPy 2.3.5 / Linux** で検証しました。

### Windows PowerShell

```powershell
cd fold
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe demo.py --seed 20260909 --trials 100
```

### Linux / macOS

```bash
cd fold
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python demo.py --seed 20260909 --trials 100
```

## 研究上の中心仮説

> **将来の問い合わせ・訂正が持つ有効次元が小さい系列では、因果的に学習したread/update capabilityを応答capsuleへ圧縮することで、長期履歴をtoken/KVとして保持する方式より少ない総コストで、同等の予測・訂正性能を維持できるか。**

評価ではcapsule本体だけでなく、H0/H1、索引、factor ID、provenance、routing、solve、padding、学習時中間状態、必要ならarchiveまで総コストへ含めます。
