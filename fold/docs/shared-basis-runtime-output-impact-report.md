# Shared Basis が運用時出力へ与える影響 — 研究仮説レポート

作成日: 2026-09-13  
状態: **研究仮説 / 評価設計。実運用上の効果を実証した文書ではない。**

## 1. 目的

FOLDで検討中の Shared Basis 構造について、モデルサイズや学習効率ではなく、**推論・生成時にユーザーが観測する出力へどのような影響が現れ得るか**を整理する。

本書では、Shared Basis を概念的に次のような構造として扱う。

```text
shared representation / basis
    + module- or layer-specific coefficients / deltas
    -> effective behavior for each module
```

現在の議論上の簡略表現は、例えば次の形である。

```text
W_module = W_base + A_module * B_shared
```

ただし、最終実装がこの厳密な式を採用することを本書は前提にしない。重要なのは、**複数の処理系が共通の低次元または共有表現空間を再利用する**という性質である。

---

## 2. 最も重要な仮説

Shared Basis が実運用で意味を持つ場合、その特徴は単なる圧縮率ではなく、**異なるタスクの出力が共通の内部方向を通ることによる相関**として現れる可能性が高い。

観測対象は次の2面に分ける。

- 良い相関: 一貫性、正の転移、再利用、安定した推論様式
- 悪い相関: 出力の均質化、負の転移、誤りの横断伝播、モジュール間リーク

したがって、通常の accuracy / loss だけでは評価不足になる。

---

## 3. 予想される正の影響

### 3.1 出力の一貫性

複数のタスクが共通 Basis を利用する場合、分野が違っても似た内部表現を再利用できる可能性がある。

実際の出力では、次のような形で観測され得る。

- 言い換えた質問に対する結論の安定化
- 同一会話内での自己矛盾の減少
- 分野をまたいだ問題分解手順の一貫性
- 説明と最終回答の整合性向上

これは単なる文章スタイルの固定化とは区別する必要がある。望ましいのは、**結論や内部関係の一貫性が上がりつつ、表現多様性は維持される状態**である。

### 3.2 Cross-domain positive transfer

ある分野の学習で改善された Shared Basis が、別分野でも有効な内部操作として再利用される可能性がある。

例:

```text
依存関係の追跡
条件の分解
比較
順序関係
状態遷移
```

これらが汎用 Basis として形成されれば、コード学習で得た改善が論理問題やゲームルール理解へ、あるいは逆方向へ波及する可能性がある。

重要なのは、**未学習または低学習量の分野にも改善が転移するか**である。

### 3.3 タスク切り替えの連続性

完全に独立した専門モデルを切り替えるのではなく、共通 Basis 上で module-specific な係数を切り替える構造であれば、

```text
一般会話 -> コード -> 数学 -> 一般会話
```

のような分野遷移でも内部表現の断絶が小さくなる可能性がある。

運用上は、

- 文脈維持
- タスク遷移時の回答品質
- 専門モードから通常会話へ戻った際の安定性

として評価できる。

### 3.4 Basis 凍結後の能力追加

特に重要な将来仮説は、十分に成熟した Shared Basis を固定し、module-specific 側だけを学習して新能力を追加できるかである。

成立すれば、

```text
Shared Basis = 共通知能部品
A_module     = 能力ごとの利用方法
```

という運用が可能になる。

この場合、追加能力の配布サイズ、学習量、既存能力への影響を大きく減らせる可能性がある。

---

## 4. 予想される負の影響

### 4.1 出力の均質化

共有が強すぎる場合、異なるタスクでも似た経路を通るため、回答が必要以上に似る可能性がある。

症状としては、

- 同じ文章構造を繰り返す
- 創造的タスクで発想が似る
- 分野固有の説明様式が失われる
- キャラクターやトーン切り替えの自由度が落ちる
- 簡単な質問にも同じ問題分解形式を適用する

などが考えられる。

したがって、Shared Basis の成功条件は「圧縮して accuracy を維持した」だけでは不十分であり、**output diversity の維持**も必要である。

### 4.2 Negative transfer / 共有干渉

Shared Basis の更新は、それを使う複数の機能へ同時に影響する。

```text
Task A の学習
    -> Shared Basis の変化
    -> Task B の内部表現も変化
```

このため、ある分野の改善と引き換えに別分野が悪化する可能性がある。

運用時には、

- 新しい能力追加後に既存回答が変わる
- 一部の専門学習後に一般会話の品質が落ちる
- fine-tuning の影響範囲が想定より広い

といった形で現れ得る。

### 4.3 Failure correlation

Shared Basis 内に誤った方向や不適切な表現が形成された場合、その誤りが複数タスクへ同時に伝播する可能性がある。

独立モジュール構造なら局所的だった失敗が、

```text
shared error
    -> math failure
    -> code failure
    -> language reasoning failure
```

のような横断的失敗になる可能性がある。

これは accuracy の平均値だけでは見えにくい。**同じ入力概念に対して複数分野が同時に誤る割合**を測る必要がある。

### 4.4 Module leakage

専門モジュール同士が同じ Basis を似た係数で利用する場合、本来分離したい出力特性が漏れる可能性がある。

例:

- 一般会話が過剰にコード的・形式的になる
- creative writing が説明調へ寄る
- 数学回答に不要な専門スタイルが混入する
- ある専門分野の強いパターンが無関係な問題でも発火する

これは能力共有とは異なる。**再利用できる汎用能力だけが共有され、分野固有の癖は必要以上に漏れないこと**が望ましい。

### 4.5 Over-reasoning 的挙動

Basis が比較・分類・分解など特定の処理に強く偏ると、本来単純に答えるべき入力にも同じ処理を適用する可能性がある。

出力上は、

- 不要な段階分解
- 過剰な条件整理
- 簡単な質問への長い説明
- 必要のない比較や分類

として見える可能性がある。

したがって、回答品質だけでなく、**task complexity に対する処理量と出力量の適合性**も確認する。

---

## 5. Rank / Basis capacity が出力へ与える可能性

Shared Basis の rank または有効次元は、単なる保存サイズではなく、モデルが同時に保持・区別できる内部方向の数として出力へ影響する可能性がある。

仮説としては、性能が rank に対して滑らかに上がるだけでなく、必要な独立方向が揃った地点で急に改善する **threshold-like transition** が起こり得る。

想定される現象:

```text
rank不足
  -> 曖昧な候補を分離できない
  -> 類似した回答へ潰れる

必要rank到達
  -> 重要な概念方向を分離できる
  -> 正答率・confidence・一貫性が急改善
```

現在までの探索的な会話・実験観察に threshold を疑う材料はあるが、**再現可能な benchmark artifact がリポジトリへ揃うまでは実証結果として扱わない**。

---

## 6. Logit / confidence への影響仮説

Shared Basis の表現自由度が出力層まで影響する場合、token logit の分布にも特徴が出る可能性がある。

良い場合:

- 正解候補を明確に分離する
- paraphrase 間で confidence が安定する
- 同じ概念を使う複数タスクで calibration が改善する

悪い場合:

- Basis に表現できない差異が複数候補へ潰れる
- 誤答に対して横断的に高 confidence を出す
- 分野ごとの calibration が連動して崩れる

そのため、top-1 accuracy だけでなく、NLL、entropy、margin、calibration も評価候補にする。

---

## 7. 運用評価で追加すべき指標

### 7.1 Paraphrase consistency

同一意味の複数表現に対し、

- 結論一致率
- 数値回答一致率
- confidence 分散

を測る。

Shared Basis の良い共通化なら改善が期待される。

### 7.2 Cross-domain transfer

Task A のみ追加学習した前後で、Task B/C の未学習評価セットを測る。

見るもの:

- 正の転移
- 無影響
- 負の転移

を分ける。

### 7.3 Output diversity

同一または近い prompt 群に対し、

- lexical diversity
- structural diversity
- semantic diversity
- repeated answer template rate

を測る。

accuracy を維持したまま diversity が落ちる場合は、共有過多の可能性がある。

### 7.4 Cross-domain failure correlation

同じ基礎概念を異なる形式で問う multi-domain set を作り、失敗の同時発生率を測る。

単純な個別 error rate ではなく、

```text
P(Task B fails | Task A fails)
```

のような条件付き失敗率を見る。

Shared Basis に由来する共通バグの検出に重要。

### 7.5 Module leakage

専門モジュール切り替え前後で、無関係タスクの

- 文体
- 語彙
- 推論形式
- 出力長
- error pattern

が不要に変化しないか確認する。

### 7.6 Rank sweep

rank / basis capacity を段階的に変え、

- accuracy
- NLL
- output diversity
- failure correlation
- module leakage
- parameter/storage cost

を同時に測る。

単一スコアではなく Pareto front で判断する。

---

## 8. 推奨する実験順序

実運用出力への影響を最小コストで確認するなら、次の順序を推奨する。

1. **Dense / independent baseline と Shared Basis を同条件で比較**
2. **paraphrase consistency** を測る
3. **output diversity** を測る
4. 1タスクのみ追加学習し **cross-domain transfer** を測る
5. **failure correlation** を測る
6. **module leakage** を測る
7. **rank sweep** で threshold の有無を確認する
8. Basis を freeze し、module-specific 側だけで新能力を追加できるか確認する

特に 4〜6 は、通常の accuracy benchmark では発見しにくい Shared Basis 固有の挙動を狙う。

---

## 9. Serving / 更新運用への示唆

Shared Basis を実運用する場合、性能評価だけでなく更新単位にも注意が必要である。

### Basis 更新

Shared Basis を変更する場合は、全モジュールへ影響する可能性があるため、局所更新として扱わない。

必要な比較:

- 全主要タスクの regression
- output diversity regression
- failure correlation の変化
- module-specific delta との互換性

### Module-specific 更新

Basis を freeze し module-specific 側だけを更新できれば、影響範囲を限定できる可能性がある。

この性質が成立するかは、FOLDの運用上かなり重要な評価ポイントになる。

### Version compatibility

将来 Shared Basis と module-specific delta を個別配布する場合、少なくとも概念上は、

```text
basis_version
module_delta_version
compatible_basis_range
```

のような対応関係を管理する必要がある。

古い delta を新しい Basis へ無検証で適用すると、同じ係数でも意味が変わる可能性がある。

---

## 10. 成功判定

Shared Basis を有効と判断する条件は、単にモデルサイズを小さくすることではない。

理想形は次の状態である。

- 共通知識・共通推論操作は Shared Basis に集約される
- 分野固有能力は module-specific 側で保持される
- 異分野間で正の転移が起こる
- 一貫性が上がる
- output diversity は維持される
- failure correlation が危険な水準まで増えない
- module leakage が抑えられる
- Basis freeze 後に小さい差分で新能力を追加できる
- Dense / independent baseline に対して品質・容量・計算量の Pareto 改善を示す

この状態まで確認できれば、Shared Basis は単なる重み圧縮ではなく、**複数能力が共通の内部表現・思考部品を再利用するアーキテクチャ上の特徴**として評価できる。

---

## 11. 現時点の結論

現段階で最も注目すべき運用上の現象は、**異なるタスク間の出力相関がどのように変化するか**である。

Shared Basis が成功すれば、一貫性・転移・能力追加効率が改善する可能性がある。一方で、共有過多なら出力均質化・負の転移・誤りの横断伝播が生じる。

したがって今後は、accuracy / NLL だけでなく、

- paraphrase consistency
- cross-domain transfer
- output diversity
- cross-domain failure correlation
- module leakage
- rank threshold behavior

を Shared Basis の主要評価軸として扱う。

本書に記載した効果は、明記したものを除きすべて研究仮説であり、実測結果と混同しない。
