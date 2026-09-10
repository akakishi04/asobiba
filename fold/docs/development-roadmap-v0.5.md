# FOLD v0.5 開発ロードマップ — 理論から実用品質まで

更新日: 2026-09-10。関連: [最終構想](architecture-v0.5.md)、[理論仕様](theory-v0.5.md)、[不足情報取得](information-acquisition.md)。

**目的: 今後の実装を、複数の新機構を一括投入する開発ではなく、原因を切り分けられる段階的な検証へする。各段階の数値閾値はbaseline取得後、最終比較前に固定する。**

## 1. 開発原則

1. 最初から既存LLMの内部互換性を守らない。ただし既存モデルはbaseline、教材、teacher、初期化材料として利用できる。
2. 新構造の学習可能性、圧縮、反復、routing、情報取得、記憶、可変長入出力、Visionを一度に追加しない。
3. 各段階に参照実装を置き、高精度・単純・遅い実装と最適化版の結果を比較できるようにする。
4. 保存量、推論量、学習量、外部記憶量を別会計にする。
5. 一つの小さな合成課題の成功を一般LLM性能と呼ばない。
6. 低性能でも仮説の局所検証になる試作は許すが、次段へ進むには明示したgateを通す。
7. code、data、weight、experiment result、design hypothesisを混同しない。

## 2. 推奨コード境界

以下は将来のnamespace候補。既存`fold_lm`を即座に破壊的変更する指示ではない。

```text
fold_lm/
  v05/
    state.py            # evidence / working state / budget / provenance
    core.py             # shared state-update core
    modules.py          # high-precision processing modules
    compression.py      # codebook, codes, decode/direct kernels
    controller.py       # routing / stop / acquire action head
    runtime.py          # internal step and external evidence boundary
    io_bytes.py         # byte-local encoder/decoder, later variable grouping
    memory_bridge.py    # FOLD-R / hot memory / raw evidence bridge
    accounting.py       # bytes, active compute, peak memory, wall-clock
    manifests.py        # architecture/data/training/eval manifest
  v05_training/
    continuous.py
    code_assignment.py
    controller.py
    distillation.py
  v05_benchmarks/
    state_update.py
    compression.py
    recurrence.py
    acquisition.py
    memory.py
    language.py
```

名称は実装時に変更可能。ただし**state/runtime/accountingの境界は早期に固定し、各研究機構が独自の隠れた状態や無料コストを持たないようにする。**

## 3. V5-A — 参照計算と会計

### 作るもの

- `EvidenceState / WorkingState / BudgetState / Provenance` の最小型。
- 高精度の単純な状態更新式。
- 小さなcodebook式の重み復号とmaterialized reference。
- 保存byte、active module、反復数、wall-clockを記録するaccounting。
- 合成された小行列でのfloat64検証。

### 必須テスト

- direct decodeとmaterialized weightのforward一致。
- 固定codeでのautograd vs finite difference。
- serialized bytesの実測と会計値が一致。
- internal stepでevidence revisionが変わらない。
- hypothesis provenanceとobserved provenanceを混同しない。

### Gate A

数式・会計・因果性の参照実装が再現可能であること。**ここでは言語性能を要求しない。** 数値差やbyte会計が説明不能なら次へ進まない。

## 4. V5-B — 高精度の新コア

### 作るもの

- 圧縮なしの`shared core + working slots + small module set`。
- 最初はroutingを固定または教師指定し、学習可能性を確認。
- byte/BPEのどちらか一つの単純な入力を固定し、入出力研究を混ぜない。

### 課題

- copy / exact string。
- 条件保持と更新。
- 比較、簡単な算術、2〜数段階の合成課題。
- 短い日本語・英語のnext-unit prediction / instruction response。

### 比較

- 同程度のactive computeを持つ単純Dense baseline。
- 同程度の独立学習値を持つ単純共有/再帰baseline。

### Gate B

新コアが**圧縮なしなら学習できる**こと。学習自体に失敗している段階でcompressionを追加して原因を隠さない。少なくとも複数seedでloss低下、held-out改善、基本課題の再現性を確認する。

## 5. V5-C — 圧縮部品と反復安定性

### 作るもの

- 共有`W_base`。
- 複数codebook + discrete codeによる部品差分。
- bounded correction `E`。
- materializeせずに計算するreference path。GPU kernel最適化は小規模でも同時に試す。
- 1/2/4/8反復でのperturbation/quality測定。

### 学習

1. 高精度Bモデルからcodebookを初期化する方式。
2. code固定で連続値を調整。
3. block単位のcode再割当。
4. 複数反復後のtask lossで再評価。

ゼロから圧縮表現を学ぶ方式も比較可能だが必須にしない。

### Gate C

次のどちらかを満たす候補を残す。

- 同品質でserialized/resident bytesが明確に減る。
- 同容量で高精度/単純量子化baselineより課題品質が上がる。

さらに、反復で誤差が説明不能に爆発せず、補正`E`が無制限に肥大しないこと。小さい保存量でも復号overheadで実時間が悪化するなら未達として記録する。

## 6. V5-D — 適応計算とrouting

### 作るもの

- `ANSWER / COMPUTE(module, steps)` を最初の行動空間にする。
- 小さな課題では全候補経路を試し、oracle/near-oracle routing datasetを生成。
- 固定反復baselineと動的反復を比較。

### 学習

- 初期はsupervised routing。
- 次にon-policyで、自分の誤routing後から回復する例を含める。
- 課題品質が同程度なら少ないstepを優先するcompute penaltyを加える。

### Gate D

- 難しい課題では追加stepが有意に使われる。
- 簡単な課題で最大step固定より平均計算量が下がる。
- 品質を落として早期終了するだけのrouterになっていない。
- routing headの圧縮有無で行動flip率を測り、必要なら高精度を維持する。

## 7. V5-E — 「分からない」と情報取得

### 行動空間を追加

```text
PARTIAL_ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

### データ

- 同じ可視入力で、隠れた条件だけが異なり答えが変わるpair。
- 一つの観測で区別できる課題。
- 欠落情報が結論に影響しないnegative pair。
- 証拠が矛盾、古い、取得不能、noiseを含むケース。
- 情報は十分だが推論が難しいケース。

### Gate E

- 必要情報がある場合、内部反復だけで架空の事実を生成する率が下がる。
- 取得後の最終品質が取得前より改善する。
- 既知情報の聞き直しと不要質問が対照より増えない。
- 全てを「分かりません」にしてcoverageを捨てる解へ崩壊しない。
- model proposalとruntime permissionが分離される。

## 8. V5-F — FOLD-R / 記憶統合

### 作るもの

- Writer / Reader / Port Selector / Coverage classifier。
- recent raw evidence / hot mutable memory / FOLD-R capsule の明示的な分岐。
- revision、scope、factor ID、provenanceをruntime stateへ統合。

### データ

```text
ASSERT -> QUERY
REPLACE -> QUERY
RETRACT -> QUERY
ASSUME(scope) -> QUERY -> END_SCOPE
OUT_OF_SCOPE query
conflicting evidence -> acquire/clarify -> update
```

### Gate F

- 訂正・撤回後の回答が古いcacheに戻らない。
- `OUT_OF_SCOPE`と不存在を区別する。
- FOLD-R数値kernelの参照一致と、Writerの意味精度を別々に測れる。
- 原文/index/provenanceを含む総記憶費用で、単純な全文履歴保持baselineと比較する。

## 9. V5-G — 入出力を可変長へ

### 作るもの

- UTF-8 byte local encoder/decoder。
- causalなvariable grouping/patching。
- exact-copy用のrecent raw byte path。

### 比較

- byte固定。
- BPE/Unigram固定。
- variable grouping。

### Gate G

- future byteを境界決定に使うリークがない。
- 日本語/英語/数字/識別子/コード/混在文字列で破綻しない。
- tokens/sではなく同一文章のwall-clock、byte当たりloss、peak state/KVで比較する。

## 10. V5-H — Vision

Visionはコアの能力と情報取得が安定してから統合する。

- Encoder / Projectorから位置付きの視覚表現を渡す。
- 「見えない/読めない領域」を情報取得状態へ接続する。
- crop/zoom/別画像要求などを`OBSERVE/ASK_USER`と統合できるようにする。

Gate Hでは、接続できたことではなく、実画像で必要情報を認識し、読めない場合に正しく追加観測を要求できることを評価する。

## 11. V5-I — 規模拡張と実用比較

ここで初めて部品数、state width、working slots、codebook容量、teacher dataを大きくする。

### 必須baseline

- 同容量の既存量子化モデル。
- 通常Dense。
- 単純なparameter sharing/recurrent model。
- 圧縮なしの独立module model。
- 共有のみ。
- 圧縮のみ。
- 共有＋圧縮＋routingの本命。

### 最終比較軸

- 品質 / coverage / hallucination。
- serialized bytes / resident bytes / peak VRAM。
- TTFT / latency distribution / task completion wall-clock。
- active compute / routing / decode overhead。
- training peak RAM/VRAM / wall-clock / resume。
- memory bytes / retrieval latency / correction cost。
- acquisition count / user turns / cost / improvement。

## 12. 初期試作の推奨探索範囲

原因を追える小さな範囲から始める。以下は探索開始点であり固定仕様ではない。

| 項目 | 初期候補 |
|---|---|
| state width | 256 / 384 / 512 |
| working slots | 8 / 16 |
| processing modules | 8 / 16 |
| active modules/step | 1 / 2 |
| internal steps | 1 / 2 / 4 / 8 |
| codebook count | 1 / 2 / 4 |
| code width / block width | 小規模sweep。容量計上込みで選ぶ |
| correction budget | 0%, 小規模、bounded |

一度に全軸をgrid searchしない。各段階で感度の大きい軸だけをsweepする。

## 13. Experiment manifestの必須項目

各実験は最低限以下を保存する。

```text
experiment_id
commit_sha
architecture_version
data_manifest + split hashes
teacher/source provenance
seed
precision
parameter accounting
serialized model bytes
resident bytes
peak RAM/VRAM
active modules + internal steps
training wall-clock
inference wall-clock + TTFT
quality metrics + coverage
acquisition metrics (when enabled)
known deviations / failed checks
```

raw dataset、weight、run output自体は既存`.gitignore`方針に従う。結果の要約に、実データや個人情報を混ぜない。

## 14. Codexが実装判断するときのルール

1. 作業対象がどのV5段階かを最初に明示する。
2. その段階より後の機構を「ついでに」追加しない。
3. 高精度reference pathを、最適化版が一致するまで消さない。
4. metricを取らずに「高速化」「省メモリ」「高精度」と記載しない。
5. 異なるTokenizer/入力単位でtokens/sだけを比較しない。
6. modelが生成した仮説を外部観測と同じstateへcommitしない。
7. codebookのdecoded要素数を独立parameter数と呼ばない。
8. Gate未達は未達として残す。閾値やbaselineを後から有利に動かさない。
9. 並行開発の既存ファイルを無関係に削除・上書きしない。
10. 学習・大量download・課金・外部通信を設計文書だけから暗黙開始しない。

## 15. 次に着手すべき段階

このロードマップを採用した時点で、最終構想を一括実装するのではなく、**V5-A: 参照計算と会計**から開始する。

最初の成果物は賢いLLMではない。状態境界、codebook復号、byte会計、gradient検証、因果性を小さな決定論的テストで固定すること。その土台が正しくなければ、後の性能差を構造の効果として解釈できない。
