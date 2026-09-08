# FOLD — 関係保存型折り畳みネットワーク

**状態: アーキテクチャの研究案 + 二次形式メモリの検証用実装。学習済みモデルではありません。**

過去の文章をそのまま保持する代わりに、潜在変数間の関係を記憶し、将来参照する「境界」への応答を保ちながら内部を折り畳む、Transformer代替候補の研究です。

> 「何を覚えるか」だけでなく、「どの問い合わせに答えられる状態を残すか」を学習する。

Schur補完などの基本演算は既知です。FOLD全体の新規性、言語能力、Transformerに対する優位性は未検証です。

## 内容

| ファイル | 内容 |
|---|---|
| [docs/theory.md](docs/theory.md) | 設計原理、数式、保証条件、学習構成案、限界、先行研究 |
| [docs/research-plan.md](docs/research-plan.md) | 実験段階、比較対象、合否基準、未実装部分 |
| [fold_memory.py](fold_memory.py) | float64・密行列の参照実装。関係追加、求解、境界圧縮 |
| [demo.py](demo.py) | 3変数の例、ランダム検証、内部更新とfill-inの反例 |
| [tests/test_fold_memory.py](tests/test_fold_memory.py) | 数学的性質・入力検証・失敗条件の28テスト |
| [results/baseline.json](results/baseline.json) | seedを固定した実行結果 |
| [results/validation.md](results/validation.md) | 実行環境、コマンド、結果、検証対象外 |
| [AGENTS.md](AGENTS.md) | このフォルダを扱う開発エージェント向けの指針 |

## 実行

Python 3.11以上を想定。保存した結果は **Python 3.13.5 / NumPy 2.3.5 / Linux** で検証しました。Windows実機での動作は未検証です。依存はNumPyのみで、学習データ、APIキー、GPUは不要です。

### Windows PowerShell（リポジトリのルートから）

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

JSONを保存する場合はデモに `--output results/local-run.json` を付けます。失敗したチェックがある場合、デモは終了コード1を返します。基準結果を更新する場合は実行環境と差分を記録してください。

## 何が動くか

```text
B - A = 2, C - B = 3
          ↓ Bを消去
       C - A = 5

A = 1 を与える → 圧縮前後とも C = 6
A = 4 に差し替える → 圧縮前後とも C = 9
```

実装は等式を厳密な拘束条件としてではなく、重み付き二乗誤差として扱います。圧縮時には関係の重みと定数項も保持します。

`add_factor` は証拠の**追加**です。同じ変数への古い観測を自動的に置換しません。上の差し替え例は、共通の関係メモリに別々のアンカーを与えて比較しています。

## 何がまだないか

文章を潜在関係に変換するニューラルネットワーク、学習する参照先選択、境界選択、トークン生成、疎行列/GPU実装、履歴の再展開は未実装です。現段階は**提案の数学的な中核を検証する研究用の土台**であり、Transformer代替の完成品ではありません。

密行列の参照実装なので、高速化・定数メモリ・線形時間を主張しません。GitHub Actionsや外部サービスを自動実行する設定は含めていません。
