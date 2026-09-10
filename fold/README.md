# FOLD-R + Structural Reasoning

**研究用プロジェクト。現在の設計決定はv0.4。LMコアでは Shared Core + Layer Modulation を Gate 1 の第一候補とし、v0.3 の構造推論設計は維持します。学習済みの創造的LLMではありません。**

Gate 1 では、軽量・高速・高精度な小型LMを目標に、層ごとに大きなDense重みを複製する代わりに、少数の共有コアと小さな層別調整値を使います。必要箇所だけ例外重みを許可し、保存容量・resident weight bytes・peak VRAM・実速度・品質をDense baselineと分離比較します。

FOLD-Rの訂正可能な応答記憶に、複数視点の抽象化・遠い分野の構造照合・仮説探索を組み合わせるv0.3設計も継続します。ただし Gate 1 のLMコア評価では外部推論器で品質不足を隠さず、コア単体の容量・速度・品質を先に検証します。

## 実装と配布の区別

**GitHubへのコード反映は一部のみです。** 今回の連携ツールでは、学習前処理と推論の探索本体の書き込みが拒否されました。ローカルで検証した全コードと、リポジトリ内のファイルを混同しないでください。

| 機能 | このリポジトリ |
|---|---|
| FOLD v0.1のSchur補完参照カーネル | 既存実装を維持 |
| 微分可能FOLD-R response capsule | `fold_lm/capsule.py` |
| 二系統署名・bounded LSH候補検索 | `fold_reasoning/index.py` |
| Shared Core + Layer Modulation | v0.4で設計固定。Gate 1比較実装は未完了 |
| 部品デモ・13テスト | 実行可能 |
| 完全な予算付き探索・cache・batch評価デモ | 会話配布のローカルZIPのみ |
| 小型LMの学習・再開・生成 | 会話配布のローカルZIPのみ |
| 学習する抽象化・類推・Router、LM統合 | 未実装 |

詳細: [配布状態](docs/distribution-status.md)。ローカル版は`fold_v0.3_local_tools.zip`として会話で配布します。元データ・重み・実行ログは含みません。

## リポジトリ内の部品を実行

Windows PowerShell、`asobiba/fold`から:

```powershell
py -m venv .venv
$python = ".\\.venv\\Scripts\\python.exe"
& $python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
& $python -m pip install -r requirements-reasoning.txt
& $python -m fold_reasoning.components_demo
& $python -m unittest discover -s tests_reasoning -p test_components.py -v
```

CPU用の例です。Python 3.13.5 / PyTorch 2.10.0+cpu / NumPy 2.3.5で検証。Windows・CUDA実機は未検証。既に同じ仮想環境がある場合は再作成不要です。

## 文書

| 文書 | 役割 |
|---|---|
| [architecture-v0.4.md](docs/architecture-v0.4.md) | 現在のGate 1 LMコア設計。共有コア、層別modulation、容量・速度・品質の判定 |
| [architecture-v0.3.md](docs/architecture-v0.3.md) | 構造推論設計。抽象化・検索・仮説・予算・再利用 |
| [reasoning-guide.md](docs/reasoning-guide.md) | 部品デモとローカル版全体デモの実行 |
| [reasoning-plan.md](docs/reasoning-plan.md) | 推論系R0〜R8と学習・評価の境界 |
| [distribution-status.md](docs/distribution-status.md) | GitHubにあるもの／ローカルZIPのみのもの |
| [architecture-v0.2.md](docs/architecture-v0.2.md) | FOLD-R記憶、H0/H1/H2、Capability Contract |
| [research-plan.md](docs/research-plan.md) | v0.2記憶系のP0〜P10。今回一括完了したわけではない |
| [theory.md](docs/theory.md) | v0.1のSchur補完の数学背景 |
| [reasoning-validation.md](results/reasoning-validation.md) | 今回の検証と計測範囲 |

## データはGit管理しない

`data/`, `datasets/`, `runs/`, `indices/`, `program_cache/`, `checkpoints/`, `outputs/`, `.cache/`, モデル重みを除外します。空ディレクトリはGitが保持しないため、必要なコマンドが作成します。

```powershell
git check-ignore -v data/raw/private.jsonl runs/reasoning/report.json indices/local.bin program_cache/local.json
```

`.gitignore`は既に追跡済みのファイルを追跡解除するものではありません。今回のコミットへユーザーコーパスや学習重みは追加しません。

## v0.1カーネル

既存の実行方法を維持します。

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python demo.py --seed 20260909 --trials 100
```

今回v0.1カーネル・既存28テスト・既存baselineの内容は変更していません。新しい推論基盤の結果をTransformerに対する優位性や一般的な発想力の実証とは扱いません。
