# FOLD-R 作業指針

この指針は`fold/`以下だけに適用する。

- 入口はREADME。上位設計は`docs/architecture-v0.3.md`、記憶の数値意味論はv0.2と`theory.md`。GitHub反映済み範囲は`docs/distribution-status.md`を読む。ローカルZIPの存在をリポジトリ内の実装と混同しない。
- 今回の推論系は独立した研究試作。v0.2のP系列とv0.3のR系列を分け、段階の合格を捏造しない。スコープ外の大規模学習・課金API・外部データ大量取得・CI追加はしない。
- 既存v0.1カーネルはfloat64、定数項・境界順序を保持する。数理的事実、設計仮説、コード、学習済み機能、実測を分ける。Schur補完・低ランク更新・LSH・beam search・batchingを新発明と呼ばない。
- 関係の応答だけを保存する記憶と、転用可能な仕組みを保存する構造記憶は別。新しい概念を既存Q/Uへ無言で押し込まない。`OUT_OF_SCOPE`を不存在や0として扱わない。
- 仮説はscope別にし、共有baseと兄弟枝を変更しない。推論結果を無検証で確定事実へ昇格しない。追加観測と撤回・置換を区別する。
- 検索のscan上限、候補数、frontier幅、深さ、検証候補数、cache容量を明示する。検証予算はbatch数でなく候補数。cacheのreplay・再検証も含める。予算切れを不可能証明にしない。
- 近似検索は見逃しを持つ。exact fallbackを無言で使わず、索引構築・全件走査・候補評価の費用を計上する。意味の遠さだけを高評価にしない。
- 成功プログラムの再利用は、適用条件と現目標を毎回再検証する。scope、revision、入力・ポート、演算子・索引の版を区別する。未登録の任意コードを実行しない。
- Router/署名が手製なら手製と記載する。操作列cacheをニューラル蒸留や推論プログラムの自動抽象化と呼ばない。latent/batch/GPUという名称だけで高速化を主張しない。
- 数値カーネルはsolveを使用する。無言のjitter、保証外の近似、非有限値の黙殺をしない。数値計算の正しさと自然言語・因果・事実の正しさを分ける。
- データ、出力、重み、索引、cacheは`.gitignore`で除外する。元グラフ、Q/U、index/provenance、padding、候補、学習中間状態も総コストに含める。小さいnumeric payloadだけで省メモリとしない。
- 部品変更は`python -m unittest discover -s tests_reasoning -p test_components.py -v`と`python -m fold_reasoning.components_demo`で検証する。ローカルZIPを含む環境では`tests_reasoning`全体と`tests_lm`も実行する。
- v0.1変更時は`python -m unittest discover -s tests -v`と`python demo.py --seed 20260909 --trials 100`も実行する。未実行の検証は明記する。
- 未来のquery・正解操作・正解グラフは教師信号に限る。正解を検索対象やモデル入力に漏らさない。評価では候補数・計算予算・データ分割をそろえる。
- 学習・生成・外部通信をimport時に開始しない。既存のデータ・成果物を一括削除しない。ツールが拒否した書き込みは反映済みと扱わない。
