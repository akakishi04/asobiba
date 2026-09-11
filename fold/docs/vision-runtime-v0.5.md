# FOLD v0.5 Vision / Visual Evidence 設計

更新日: 2026-09-11。

**状態: v0.5最終構想のVision方針。現在のFOLD-R Gate 1へVisionを追加する指示ではない。VisionはV5-H以降で統合する。**

関連: `architecture-v0.5.md`、`theory-v0.5.md`、`information-acquisition.md`、`long-context-runtime-v0.5.md`、`development-roadmap-v0.5.md`。

## 1. 中心方針

画像を一度テキスト化してから扱うのではなく、画像専用Encoderで視覚特徴へ変換し、FOLD Working Stateへ直接接続する。

```text
Image
  -> Vision Encoder
  -> patch / region features
  -> Visual Resampler
  -> bounded Visual Slots
  -> Projector
  -> FOLD Working State
```

元画像はVisual Slotsとは別にRaw Visual Evidenceとして保持する。Visual Slotsは意味理解用の圧縮表現であり、元画像の全細部を保持しているとは仮定しない。

## 2. Vision Encoderの導入

最初は学習済みVision Encoderをfrozenで使用する。初期学習対象はProjector、Visual Resampler、Working Stateへのread pathとする。

これにより、Encoder、FOLD Core、Projector、学習データの問題を同時に変えず、原因を切り分ける。

FOLDへの接続が成立した後に、Encoderの蒸留、低bit化、軽量化、自作構造を比較する。既存Encoderを最終形へ固定するものではない。

## 3. Visual Resampler

大量のpatch tokenをそのまま重いCoreへ渡さない。

```text
P patch features -> Resampler -> K Visual Slots
```

`K`には上限を持たせる。初期比較候補は8 / 16 / 32 slots。品質、速度、VRAMで選ぶ。

Resamplerはregion / position情報を保持し、小さい文字や微小物体を全体summaryだけで「確認済み」と扱わない。

## 4. Visual Evidence

画像由来の状態には最低限、次を結び付ける。

```text
image_id
content_hash
revision
region
resolution_level
encoder_version
projector_version
representation_ref
raw_evidence_ref
provenance
```

cropしたregionを画像全体の観測と混同せず、別revisionや別Encoder版のcacheを無言で再利用しない。

## 5. Working Stateとの接続

第一候補はWorking State側からVisual Slotsを読むcross-attention / selective readとする。

```text
H_next = H
       + TextRead(H, text)
       + VisionRead(H, visual_slots)
       + MemoryRead(H, memory)
```

Text / Vision / Memoryは内部次元を合わせてもsource type、region、revision、provenanceを失わない。

## 6. Multi-resolution再観測

大画像を常に最高解像度で全面処理しない。

1. full imageを標準解像度で観測。
2. 不足しているregionを推定。
3. 必要ならそのregionだけ高解像度で再観測。
4. 新しいvisual evidenceとしてWorking Stateを更新。

概念action:

```text
OBSERVE(image_id, region, requested_resolution, purpose)
```

`OBSERVE`は内部思考stepではなく、新しい証拠を取得するactionとしてevidence timeを進める。

観測回数、総処理pixel、最大解像度、1観測のVisual Slots数にはbudgetを設ける。

## 7. 画像中の文字

PC画面、ゲームUI、ログでは文字列精度が重要なので、semantic Visionだけへ依存しない。

```text
Image
  +-- Semantic Vision Path -> UI / object / layout / state
  +-- Text-in-Image Path   -> strings / text regions
```

Text-in-Image Pathは専用OCR、Vision側reader、region reader等を比較できる。外部OCRを必須とはしない。

曖昧な文字列を無理に確定せず、必要ならregion再観測へ回す。

## 8. FOLD-Rとの分担

| 情報 | 保存・処理先 |
|---|---|
| 元画像 / crop | Raw Visual Evidence |
| Visual Slots | session visual cache / Working State |
| 読み取った文字列 | exact evidence / recent context |
| 検証済み関係 | FOLD-R MemoryOp候補 |
| 未確定の解釈 | Working State / hypothesis |

生画像や大量のvisual featureを、そのままFOLD-Rへ保存しない。Vision側の誤認識とFOLD-R kernelの数値正しさを分離して評価する。

## 9. Persistent Visual Cache

同じ画像を次turnでも参照する場合、毎回Vision Encoderを再実行しない。

cache keyは少なくとも、画像content hash、region、resolution / preprocess、Encoder版、Projector版、Resampler版を含む。

同じ画像の別regionだけ細かく見る場合は、full imageのcacheを再利用し、必要regionだけ追加encodeする。

cache容量、lookup、serialization / restoreも総コストへ含める。

## 10. Information Acquisitionとの統合

Visionでは次を区別する。

- 必要regionが画像にない -> `MISSING_EVIDENCE`
- regionはあるが細かすぎる -> `OBSERVE`
- 画素は十分だが判別できない -> Vision能力不足または`REASONING_UNRESOLVED`
- 複数画像が矛盾 -> `CONFLICTING_EVIDENCE`

Controllerは`ANSWER / PARTIAL_ANSWER / COMPUTE / OBSERVE / ASK_USER / STOP_UNRESOLVED`を比較する。

評価は「見えないと言えたか」ではなく、追加観測後に最終品質が改善したかを見る。

## 11. V5-H内部の開発順

### Vision-0: Interface
`VisualEvidence / ImageRegion / VisualSlots / cache / provenance`の境界を決める。

### Vision-1: Frozen Encoder + Projector
Frozen Encoderで簡単な画像分類、VQA、位置関係を学習し、接続を確認する。

### Vision-2: Resampler
8 / 16 / 32 Visual Slotsを比較し、patch数とCore負荷を分離する。

### Vision-3: Selective Re-observation
crop / zoomをruntime action化し、regionだけ追加encodeできるようにする。

### Vision-4: Information Acquisition
`ANSWER vs OBSERVE vs ASK_USER`を学習・評価する。

### Vision-5: Encoder Optimization
蒸留、量子化、軽量Encoder、自作Encoderを比較する。

## 12. 評価

少なくとも、object presence、spatial relation、UI state、exact text / identifier、小物体・小文字、region再観測、読めない/写っていないnegative例を分ける。

Vision実験では、Encoder/Projector/Resampler版、入力解像度、patch数、Visual Slots数、visual cache bytes、encode/resample/read時間、peak VRAM増分、cache hit率、OBSERVE回数、総処理pixel、課題品質を記録する。

Gate Hでは、画像を接続できただけでは合格にしない。Visual inputが必要なheld-out課題で改善し、bounded Visual Slotsが費用対効果を持ち、cache reuseとregion再観測が機能し、再観測後に品質が改善することを確認する。

## 13. 現在のGate 1との境界

現在のGate 1はFOLD-R memory capabilityの検証である。Vision Encoder選定、Visionデータ取得、OCR導入、Vision GPU最適化はGate 1完了条件に追加しない。

Gate 1では、将来のVisual Evidenceを接続できるよう、scope / revision / provenance / raw evidence参照の意味論を壊さないことだけを要求する。

Visionは最終的に、**必要なときに必要な視覚証拠へ戻って確認できる、boundedかつ再観測可能な知覚系**として構成する。
