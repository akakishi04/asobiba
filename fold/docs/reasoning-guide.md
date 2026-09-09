# 構造推論の参照実装を動かす

状態: 小さな**構造化数値課題**を処理する独立モジュール。文章を入力して自由に類推する完成済みLLMではありません。外部データ、APIキーは不要です。

## GitHubだけで実行できる範囲

依存を導入後、候補検索と応答capsuleの部品デモ・13テストを実行できます。

```powershell
python -m fold_reasoning.components_demo
python -m unittest discover -s tests_reasoning -p test_components.py -v
```

以下の全体探索デモには、会話で配布する **fold_v0.3_local_tools.zip** の追加ファイルが必要です。GitHubの現コミットには`core.py`や学習runnerはありません。連携ツールの書き込み拒否により未反映です。ZIPはローカル実行用であり、GitHub反映完了の意味ではありません。

## ローカルZIPを含む環境でのWindows PowerShell

`asobiba/fold` で実行します。既存の仮想環境を利用できます。

```powershell
py -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
& $python -m pip install -r requirements-reasoning.txt
& $python -m fold_reasoning demo
& $python -m fold_reasoning benchmark --trials 30 --output runs/reasoning/report.json
& $python -m unittest discover -s tests_reasoning -v
```

Linuxでは`.venv/bin/python`を使用します。依存の取得以外に通信しません。CPU float64で検証。WindowsとCUDAは実機未検証。適切なCUDA版PyTorchを導入した環境では `--device cuda` を指定でき、使えない場合に黙ってCPUへ切り替えません。

## 何が起きるか

六つの変数が加法的な連鎖を作る人工課題です。構造と話題の署名、適用可能な操作はコードが与えます。rhythmとfactoryという名前は、分野の遠さを区別する**手製のテスト用ラベル**であり、音楽から工場へ自力で類推した実験ではありません。

`demo`は、同じ課題を二度解き、さらに基底状態だけで解ける課題を試します。

| 出力 | 意味 |
|---|---|
| cold / search | 索引で候補を絞り、固定予算で操作列を探索 |
| warm / validated_program | 成功した操作列を再実行し、現在の目標で再検証 |
| direct | 基底状態がすでに数値目標を満たし、検索不要 |

`--budget fast / normal / deep`で予算を切り替えます。fastで解けない場合の `BUDGET_EXHAUSTED` は想定内です。失敗を0や「不可能」として返しません。

`benchmark`は、同じ16枝をserial/batchで評価した値の一致とCPU/GPU時間を測ります。順序を交互にし、warmup、CUDA同期、環境・試行数を記録します。microbenchmarkであり、LLM全体の高速化率ではありません。

## Pythonから使う

```python
from fold_reasoning.demo import example
from fold_reasoning.core import Reasoner, Budget

task, index, operations = example(shift=2)
reasoner = Reasoner(index, operations, budget=Budget.preset("normal"))
result = reasoner.solve(task)
assert result["status"] == "SOLVED"
print(result["program"], result["value"])
```

自分の課題では`CapsuleTask`へJ/eta/Q/U、達成したい数値目標、構造署名、意味署名、scope、revisionを渡します。参照版の上限は256変数・32read/update port。`Operation`は登録済みportへのeta/precision差分です。

Jは正定値、Uは列独立である必要があります。既存の任意の関係を自動抽出する機能、範囲外の新概念を復元する機能はありません。

## データと出力

`data/`, `datasets/`, `runs/`, `indices/`, `program_cache/`, `.cache/`, 重みファイルはGit管理対象外です。Gitは空ディレクトリを保持しないため、`--output`実行時に必要なディレクトリを作ります。既存の出力ファイルは上書きしません。

```powershell
git check-ignore -v data/raw/private.jsonl runs/reasoning/report.json indices/local.bin program_cache/local.json
```

索引は現在メモリ上で構築、プログラムcacheもprocess-localです。cache永続化・ANN大規模評価・学習する抽象化・LMへの統合は未実装。目標設計は [architecture-v0.3.md](architecture-v0.3.md) を参照してください。
