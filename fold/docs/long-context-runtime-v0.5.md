# FOLD v0.5 長文・セッション実行契約

更新日: 2026-09-11。

**状態: FOLD-R と v0.5 最終構想に共通する長文実行・セッション継続の正規設計。長い履歴を保持できることと、長い履歴を高速に利用できることを別問題として扱う。現時点で全項目が実装・実測済みという意味ではない。**

関連文書:

- [architecture-v0.2.md](architecture-v0.2.md): H0/H1/H2、固定local window、FOLD-Rの数値契約。
- [architecture-v0.5.md](architecture-v0.5.md): 最終構想。
- [theory-v0.5.md](theory-v0.5.md): 状態更新・圧縮・適応計算の理論仕様。
- [development-roadmap-v0.5.md](development-roadmap-v0.5.md): 段階的実装。
- [information-acquisition.md](information-acquisition.md): 不足情報の取得。

## 1. 解く問題

長いprompt/historyでは、少なくとも次の費用を分離する。

1. **cold ingestion**: 初めて与えられた入力を読む費用。
2. **continued-turn ingestion**: 既に処理済みの会話へ新しいturnを追加する費用。
3. **decode**: 1単位を生成するたびに参照する状態の費用。
4. **long-memory lookup**: H2/外部記憶が増えたときに必要項目を選ぶ費用。
5. **state maintenance**: H1 commit、索引更新、serialization、checkpoint、revision処理の費用。

目標は「入力長にかかわらず全処理が定数時間」ではない。新しい入力 `N` bytes/tokens は少なくとも読まなければならない。狙いは、**既に処理済みの履歴 `H` を毎turn・毎decodeで再走査しないこと、およびfull-history attentionの二次的な伸びを正規経路から外すこと**である。

## 2. 正規な複雑度目標

固定local window `W`、1 stepで許すmemory候補数 `R_max`、索引scan上限 `S_max` を定数として扱う条件で、正規経路の目標を次とする。

### 2.1 初回入力

新規入力長を `N` としたとき、local mixerの処理量は概念上、

```text
O(N * W)  -> W fixed なら N に対して線形
```

を目標とする。FOLD-Rへのwrite/commit、可変長grouping等の追加処理も実費へ含める。`O(N)`は実時間の定数係数が小さいことを保証しない。

### 2.2 継続turn

既にcommit済みの履歴長を `H`、新しく追加された入力を `DeltaN` とする。

正規stateful runtimeでは、

```text
cost(next turn) ~= cost(DeltaN) + bounded memory/index work
```

を目標とし、

```text
cost(next turn) ~= cost(H + DeltaN)
```

となるraw history replayを標準動作にしない。

### 2.3 decode

1生成stepの重い処理は概念上、

```text
O(W + working_state + active_modules + R_max)
```

の有界な状態に依存させる。総会話長 `H` に比例するglobal attention、全capsule scan、全原文scanを正規経路に含めない。

この目標はindex query自体が完全な定数時間であることを意味しない。backend固有の索引費用、cache miss、storage I/Oを別に測る。

## 3. Persistent Session State

一度処理したprefixを次turnでraw textとして再prefillしないため、sessionにauthoritativeな継続状態を持つ。

概念上、turn `t` のcommit後状態を、

```text
SessionState_t = {
  revision,
  h0_tail,
  h0_runtime_state,
  h1_hot_buffer,
  h2_foldr_bank,
  memory_index,
  raw_evidence_refs,
  provenance,
  controller/runtime metadata,
  accounting metadata
}
```

とする。

- `h0_tail`: 正確な語順・数字・引用・最近の照応に必要な直近範囲。
- `h0_runtime_state`: local mixerが継続に必要とする有界状態。attentionの場合は固定window内のKV等。
- `h1_hot_buffer`: まだcommitしていない最近の可変情報。
- `h2_foldr_bank`: 長期の応答capsule。
- `memory_index`: H2/原文参照をbounded retrievalする索引。
- `raw_evidence_refs`: 正確な再確認が必要な原文・出典への参照。全量をGPU常駐させない。
- `revision/provenance`: 履歴編集、scope、時点、取得元を検証するための情報。

SessionStateの保存量、serialize/deserialize時間、CPU RAM、GPU resident bytesを隠れた無料cacheとして扱わない。

## 4. Turn Transaction

通常turnは次の順序を正規候補とする。

```text
Committed SessionState_t
        +
new evidence DeltaX
        |
        v
1. validate revision / provenance
2. ingest DeltaX only through local path
3. stage H1 / working-state changes
4. bounded reads from H2/raw evidence when required
5. generate response
6. stage memory operations produced by this turn
7. commit session state atomically at the turn boundary
        |
        v
Committed SessionState_(t+1)
```

### 不変条件

- `SessionState_t`に既に反映されたraw historyを、毎turn暗黙に再tokenize・再prefillしない。
- internal reasoningだけでevidence revisionを進めない。
- generation途中の未確定仮説をauthoritative H2へ自動commitしない。
- turn失敗時に中途半端なH1/H2/index更新をauthoritative stateとして残さない。
- user/toolから新しい外部証拠が来た場合は、それを`DeltaX`として明示的に取り込む。

実装上のatomicityの粒度は後で固定するが、少なくともmemory/index/revisionが互いに別のturnを指す状態を正常終了として残さない。

## 5. Prefix Replay Policy

### 正規stateful mode

既知prefixのraw replayは禁止する。次turnはserializeされたSessionStateまたは同一process内のresident SessionStateから継続する。

### 許可する例外

- correctness/debug用のfull replay baseline。
- state format変更後のmigration/rebuild。
- state破損・checksum不一致からのrecovery。
- ユーザーが過去履歴を編集し、保存stateの因果系列が無効になった場合。
- 明示的なstateless互換モード。

例外を使ったrunはstateful性能として報告しない。

### stateless API互換

外部APIが毎回prompt全文しか渡せない場合でも、session ID + prefix fingerprint等で既知prefixを識別し、可能なら保存済みstateへ復帰して新規suffixだけ取り込む方式を候補とする。ただし誤ったprefix一致は状態汚染になるため、曖昧な一致をsilent reuseしない。

## 6. 履歴編集・revision・再構築

過去turnの編集・削除・分岐が起きた場合、編集前履歴から作ったstateをそのまま正しいと扱わない。

各commitへ少なくとも、

```text
session_id
revision
parent_revision
processed_prefix_fingerprint
state_schema_version
```

を結び付ける候補とする。

過去が変更された場合は、

1. 変更前のstateをそのまま継続しない。
2. 利用可能なら変更点より前の検証済みcheckpointへ戻る。
3. 変更されたsuffixだけを再処理する。
4. checkpointがなければfull rebuildする。

を正規のrecovery方針とする。

checkpointは速度最適化でありauthoritativeな証拠ではない。checkpoint自体の保存bytesと作成時間を計上する。

## 7. Bounded Memory Retrieval

H2 capsule数または原文参照数が増えても、毎decodeで全件を読む方式は禁止する。

memory readは概念上、

```text
query
  -> bounded index lookup
  -> <= R_max candidate memories
  -> capability/coverage check
  -> selected FOLD-R/raw reads
```

とする。

最低限、次を設定・計測する。

```text
R_max        # 1 queryで詳細評価するmemory上限
S_max        # indexがscan/probeする上限
Q_max        # 1 generation step/turnで発行可能なmemory query上限
read_bytes   # 実際に読んだpayload
```

`R_max`や`S_max`に達して候補を見逃す可能性は明示する。見つからない場合に全memoryへsilent fallbackしない。exact scanを使う場合は別baselineとして実時間と件数を報告する。

index構築・更新も全件に触れる可能性があるため、ingestion/commit費用へ含める。「decodeがbounded」であることと「memory maintenanceが無料」であることを混同しない。

## 8. H0 / H1 / H2 の速度上の役割

### H0 — fixed recent context

- local window `W`を固定する。
- decode時のKV/stateを`W`に対して有界にする。
- 語順、正確な文字列、局所照応を扱う。

### H1 — hot mutable state

- 1件ごとの不規則なgraph mutationを避け、chunk/pressure境界でまとめる。
- 容量・滞在量に上限を置く。
- commit latencyを測る。

### H2 — long response memory

- 遠い情報をfull token historyとしてGPUへ保持しない。
- FOLD-RのQ/U契約で、必要なread/update capabilityを保存する。
- capsule数が増えたらindexで候補を絞る。

つまり、履歴長の増大を主に**保存stateの総量**へ逃がし、**1 stepでactiveに読む量**はboundedにすることを狙う。

## 9. Cold Prompt と Session Continuation を分けて測る

長文速度benchmarkでは、次を混同しない。

### Cold prefill

新しい長文を一度だけ読む条件。

測定:

- input length。
- time to first output / TTFT。
- ingestion throughput（bytes/sまたはcharacters/sも併記）。
- peak RAM/VRAM。
- H0/H1/H2/index bytes。
- commit/compile/index更新時間。

### Warm continuation

既に同じ履歴をSessionStateへcommit済みで、新規turnだけ追加する条件。

測定:

- committed history length。
- DeltaX length。
- incremental TTFT。
- raw history bytes reread。
- H2 candidate count / scanned count / read bytes。
- state load time（residentとserialized復帰を分ける）。
- decode latency / throughput。

**warm continuationでraw history rereadが履歴長に比例して増える場合、正規stateful目標は未達。**

## 10. Prompt/History Length Sweep

最低限、履歴長を複数点で増やし、次をプロットする。

```text
history length -> cold TTFT
history length -> warm incremental TTFT
history length -> decode latency
history length -> peak VRAM
history length -> resident state bytes
history length -> H2/index bytes
history length -> candidates/scans per read
history length -> task quality
```

長さ候補は実験規模に合わせるが、2倍系列を基本とする。FOLD-Rの現在のexact-distance sweepと、runtime速度sweepは別物として記録する。

単一factを遠ざけるだけの記憶試験が成功しても、warm continuationの速度が履歴長に比例して悪化するなら長文runtimeの成功とはしない。

## 11. 比較条件

少なくとも次を分ける。

| 条件 | 意味 |
|---|---|
| Full replay / full attention baseline | 毎turn raw historyを再処理する基準 |
| Local-only recurrent/session baseline | FOLD-Rなしで有界状態だけを継続 |
| FOLD-R stateful | H0/H1/H2/indexを継続 |
| FOLD-R stateless replay | correctness/debug。stateful性能に数えない |
| Prefix/KV cache baseline | 利用可能なら既存方式の強い比較対象 |

同じ品質を維持できているかを必ず併記する。高速だが必要な遠距離情報を忘れている条件を成功にしない。

## 12. Gate 1との関係

現在進行中のFOLD-R Gate 1では、まずmemory capabilityを詰める。

現在のdistance系に続き、優先度は概念上、

```text
single distant fact
 -> multiple facts
 -> interference
 -> correction / replace / retract
 -> mixed queries
 -> more natural language
```

とする。

長文runtime速度は、Gate 1のmemory correctnessを置き換えない。ただしGate 1を「実用可能なFOLD-R記憶」として閉じる前に、少なくとも次を測定対象へ入れる。

- fixed local windowを維持したcold ingestion scaling。
- persistent SessionStateを使ったwarm continuation scaling。
- H2/indexが増えた条件でのbounded read budget。
- prompt/history長別のTTFT、decode latency、RAM/VRAM。

FOLD-Rが遠距離情報を保持できても、毎turn全履歴を再処理する必要があるなら、長文速度対策としては未完成である。

## 13. 合格判定の方針

具体的な数値marginはbenchmark実装・baseline取得後、最終比較前に固定する。最低限、次を要求する。

1. **Correctness:** 遠距離情報、訂正、scope等の対象能力を維持する。
2. **No mandatory full replay:** 正規stateful continuationで全history replayを要求しない。
3. **Bounded decode working set:** local stateと詳細memory read数に明示上限がある。
4. **Incremental scaling:** warm incremental TTFTが主に新規入力とbounded maintenanceに支配され、committed history全量の再処理に支配されない。
5. **Transparent accounting:** state/index/raw evidence/checkpoint/cacheのbytesと時間を全て計上する。
6. **No silent fallback:** full scan/full replayを使った場合は別条件として記録する。

この契約を満たさない場合、長期記憶の品質が高くても「prompt長による速度低下を解決した」とは報告しない。
