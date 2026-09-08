# FOLD-R 作業指針

この指針は `fold/` 以下だけに適用する。

- 入口は `README.md`。**現在の正規アーキテクチャは `docs/architecture-v0.2.md`**。`docs/theory.md` はFOLD v0.1数学背景として扱い、v0.2設計と矛盾する場合は正規設計を優先する。ただし数学的保証の変更は明示する。
- 実装順序は `docs/research-plan.md` のphaseを基準にする。現在地を飛ばして大規模言語モデル、GPU最適化、MoE、MTPへ進まない。独立した検証コードは別実験として置ける。
- 数学的事実、研究仮説、実装済み機能、実測結果を区別する。Schur補完、低ランク行列更新、local attention、MoE、MTPをFOLD-Rの新発明と表現しない。言語モデル未学習の状態を「Transformerを超えた」と記述しない。
- FOLD-R固有の中心は、因果的に学習するread/update capability、訂正列への応答保存、Capability Contract、総コストを含む記憶管理である。同等の先行研究がないことは調査なしに断定しない。
- v0.1参照カーネルはfloat64、定数項を含む二次形式、境界順序の保存を基準とする。疎化・低精度化・正則化・内部変数の再展開は意味を変える可能性があるため、別の明示的変更として扱う。
- v0.2の数値カーネルでは明示的な逆行列形成を正規経路にしない。solve/Choleskyを基準とし、正定値性・条件数・失敗statusを隠さない。原因を隠すために許容誤差を広げたり、無言でjitterを加えたりしない。
- `ASSERT`、`RETRACT`、`REPLACE`、`ASSUME`、scope、factor IDの意味を混同しない。同じentityへ新しい値が来ただけで暗黙に旧値を削除しない。
- Capability Contract外のquery/updateを黙って近似しない。`OUT_OF_SCOPE`、`HOT_REQUIRED`、`NUMERIC_UNSAFE`を0、不存在、成功として扱わない。
- H0/H1/H2、index/provenance、padding、routing、archive、学習中間状態をコスト集計から隠さない。capsuleの数値payloadだけで「定数メモリ」「省メモリ」と結論しない。
- GPU最適化では理論FLOPsだけで判断せず、batch size、kernel launch、GPU utilization、HBM traffic、padding waste、wall-clock、p95 latencyを測る。dynamic graphの不規則性を無視しない。
- Dense FFN、conditional compute、MTPはFOLD-Rの中心仮説とは別アブレーション。複数を同時導入した結果だけで効果を帰属しない。
- 未来のquery/updateをWriter/Port Selectorの入力へ漏らさない。未来操作は教師信号としてのみ利用可能。全文を見て過去token用のmemoryを作る評価は禁止。
- v0.1カーネル変更時は `python -m unittest discover -s tests -v` と `python demo.py --seed 20260909 --trials 100` を `fold/` から実行する。v0.2実装ではphaseごとに独立した再現テストを追加する。
- 実験結果にはseed・環境・precision・設定・commitを残す。実行不能な項目は未検証と記録し、独立した作業は続けてよい。
- 大規模学習、課金API、外部データの大量取得、CI追加はユーザーの依頼範囲を確認してから行う。既存の生成物・データを一括削除しない。
