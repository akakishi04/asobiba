# v0.3 検証記録

実行日: 2026-09-09。Linuxコンテナ、Python 3.13.5、PyTorch 2.10.0+cpu、NumPy 2.3.5。CUDAなし。GitHub Actions上の実行ではない。

## 配布範囲ごとの結果

| 検証 | 件数・結果 | 実行対象 |
|---|---|---|
| 候補検索・応答capsuleの部品テスト | 13件通過 | GitHubに反映するファイルだけの別ディレクトリで実行 |
| 予算・仮説分離・cache再検証など | 27件通過 | ローカルZIPの探索本体 |
| 小型LM・データ処理・勾配・学習再開など | 22件通過 | 前回ZIPから統合したローカル学習実装 |
| 全体 | 62件通過 | 13+27+22。元のv0.1の28テストは含めない |
| import/構文検査 | compileall通過 | ローカル実装 |
| データ・重み・索引・cacheのGit除外 | 5パス確認 | GitHub配布用の別ディレクトリ |

v0.1カーネル、既存28テスト、既存baselineは変更していない。今回はその28テストを再実行していない。新しいテストの成功で旧検証を実施済みと置き換えない。

## コマンド

GitHubに含む部品のみ:

```bash
python -m unittest discover -s tests_reasoning -p test_components.py -v
python -m fold_reasoning.components_demo
```

ローカルZIPを含む環境:

```bash
python -m unittest discover -s tests_reasoning -v
python -m unittest discover -s tests_lm -v
python -m fold_reasoning demo
python -m fold_reasoning demo --budget fast
python -m fold_reasoning benchmark --trials 30 --output runs/reasoning-benchmark/report.json
python -m compileall -q fold_lm fold_reasoning tests_reasoning
```

## 人工デモの結果

与えた署名から構造候補を検索し、加法的な六変数の数値目標を操作列で達成する。署名・作用は手製で、一般的な類推能力を測っていない。

| 指標 | 初回探索 | 成功列の再実行 |
|---|---:|---:|
| 結果 | SOLVED | SOLVED |
| 展開・再実行した操作数 | 12 | 2 |
| 検証した候補数（基底を含む） | 9 | 2 |
| batch呼び出し数 | 3 | 2 |
| 検索実行 | あり | なし |

目標を変えるとcacheの結果をそのまま返さず、再検証に失敗した列を棄却する。scope・revisionが異なる問題間での誤再利用、非有限値や非正定値の枝が他の枝を巻き込むこと、候補数予算の超過をテストした。

## CPU microbenchmark

同一の16枝、float64、1 CPU thread、30反復、warmup後にserial/batchの順序を交互にした。保存したJSONは`reasoning-smoke.json`。

- batchとserialの読み出しの最大絶対差: 0.0
- batchの中央値: 約0.1834 ms
- serialの中央値: 約1.4939 ms

この値は小さな検証カーネルの実時間で、LLM全体の速度比較ではない。GPU実測ではない。時計値は機器と負荷で変わる。索引・capsule構築はmicrobenchmarkの時刻から除外し、demoにはsetupを含む別の総時間を記録した。

numeric payloadの表示は、共有capsule96 bytes、16枝の差分768 bytes、索引配列960 bytes。これらには元のJ/eta/Q/U、validation用分解、Pythonの辞書・文字列、bucket、候補中間配列、allocator、学習状態等を含まない。プロセス全体の省メモリの証明ではない。

## 未検証・未実装

自然言語の構造抽出、学習する類推・Router、未知分野への転用、推論プログラムの一般化や蒸留、LLMとのend-to-end統合、大規模ANN recall、GPU最適化、MTP、Windows/CUDA実機。今回GitHubへの一部コード書き込みは拒否されたため、配布境界は`docs/distribution-status.md`を参照。
