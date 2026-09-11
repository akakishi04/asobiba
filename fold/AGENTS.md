# FOLD-R 作業指針

この指針は`fold/`以下だけに適用する。

- 入口はREADME。最終構想は`docs/architecture-v0.5.md`、v0.5の数理・学習境界は`docs/theory-v0.5.md`、長文session/prefix reuse/bounded memory readは`docs/long-context-runtime-v0.5.md`、実装順序と各Gateは`docs/development-roadmap-v0.5.md`、不足情報の判断・取得は`docs/information-acquisition.md`。v0.4はGate 1の層別共有比較候補、v0.3は構造推論の詳細、記憶の数値意味論はv0.2と`theory.md`。所在は`docs/distribution-status.md`と対象refの実ファイルで確認する。
- v0.5関連を実装するときは、開始時に対象の`V5-A`〜`V5-I`段階を明記し、その段階のGateと比較対象を確認する。後段の機構を「ついでに」混ぜず、高精度reference pathを最適化版との一致確認前に削除しない。
- 最終構想と直近ゲート、v0.2のP系列とv0.3のR系列を分け、段階の合格を捏造しない。現在のFOLD-R Gate 1ではmemory capabilityの正しさを優先して進め、v0.5本体を実装済みと扱わない。ゼロからの共同学習・既存重みとの内部互換性を最終形の必須条件にしない。蒸留・変換・部分学習も比較できるが、設計文書だけを根拠にスコープ外の大規模学習・課金API・外部データ大量取得・CI追加を開始しない。
- v0.5の内部反復ではevidence timeとinternal stepを分離する。内部仮説を新しい観測事実として`X`や長期記憶へcommitしない。外部取得結果には出典・対象・時点を保持し、検索0件・取得失敗・`OUT_OF_SCOPE`を不存在へ変換しない。
- 長文の正規stateful runtimeでは、commit済みraw historyを毎turn再tokenize・再prefillしない。`SessionState + new DeltaX`を処理し、full replayはdebug/rebuild/stateless baselineとして別計測する。過去turn編集時はrevision/fingerprintを検証し、古いstateをsilent reuseしない。
- H2/原文参照が増えても毎decodeの全件scanを許可しない。memory queryは`R_max / S_max / Q_max`等の明示予算を持たせ、上限到達時のmissを認める代わりにsilent exact fallbackを禁止する。index構築・更新・state serializationも総コストに含める。
- 長文性能を報告するときはcold prefillとwarm continuationを分離し、history長ごとの`cold TTFT / incremental TTFT / decode latency / raw reread bytes / candidate-scan count / H0-H1-H2-index bytes / peak RAM-VRAM / quality`を記録する。warm continuationのraw reread量がhistory長に比例する場合、stateful長文目標は未達とする。
- 圧縮部品では、共有重みの反復回数を独立パラメータ数へ加算しない。辞書・code・scale・補正・metadata・復号bufferを含めて容量を報告する。decoded要素数、独立continuous scalar、discrete code bits、serialized bytesを分離する。
- codebook/direct kernelを実装するときは、materialized referenceとのforward一致を先に固定し、固定code条件でautogradとfloat64 finite differenceを比較する。圧縮品質は1-stepだけでなく複数反復後のtask loss、routing/stop/acquisitionの行動flipも測る。
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
- 不足情報の判断も推定である。情報不足と推論未完了を混同せず、分かる部分は答える。既知情報の聞き直し・無限取得を避け、情報取得後の品質改善と不要質問率を測る。モデルの取得提案と実行基盤の権限・予算を分離する。
- 異なるTokenizer/入力単位でtokens/sだけを比較しない。同じ元文章・課題のwall-clock、byte当たりloss、state/KV量を併記する。
- v0.5実験は`experiment_id / commit_sha / data split hashes / seed / precision / serialized bytes / peak RAM-VRAM / active modules / internal steps / wall-clock / quality / coverage / acquisition metrics / known deviations`をmanifestに残す。Gate未達は未達として記録し、後からbaselineや閾値を有利に動かさない。
