# FOLD — 低容量モデルと訂正可能な記憶の研究

**最終構想の第一候補はv0.5です。設計仮説、既存の参照コード、学習済み能力、実測結果を分けて扱います。今回の文書更新は完成モデルや性能の実証を意味しません。**

目標は、実用的な言語理解・推論を少ない保存容量と実用的な速度で成立させ、自宅環境で構築・学習・更新できるモデルです。既存モデルは教材・材料・比較対象に使えますが、その内部構造を完成形の制約にはしません。

現在の本命は、**共有状態更新コア＋圧縮した処理部品群＋制御器＋訂正可能な記憶**です。処理の多様性は低ビットの部品、深さは再利用で確保し、会話で増える情報は重みとは別に扱います。

制御器は部品や反復を選ぶだけでなく、「答える・追加計算する・調べる・観測する・質問する」を選ぶ設計です。分かる範囲を答え、不明点と有用な追加情報を具体化し、不要な聞き返しを抑える能力を目指します。

## 設計を読む

| 文書 | 役割 |
|---|---|
| [architecture-v0.5.md](docs/architecture-v0.5.md) | 最終構想。状態更新コア、圧縮部品、可変長入出力、記憶、柔軟な学習方法、総費用での評価 |
| [theory-v0.5.md](docs/theory-v0.5.md) | v0.5を実装へ落とす理論仕様。二重時間軸、状態更新式、圧縮表現、反復誤差、行動価値、学習対象 |
| [development-roadmap-v0.5.md](docs/development-roadmap-v0.5.md) | V5-A〜Iの実装順序、各Gate、比較対象、manifest、Codex作業規約 |
| [information-acquisition.md](docs/information-acquisition.md) | 不確実性、不足情報、部分回答、検索・観測・質問、権限境界、学習と評価 |
| [architecture-v0.4.md](docs/architecture-v0.4.md) | Gate 1の層別共有比較候補。最終形そのものではない |
| [architecture-v0.3.md](docs/architecture-v0.3.md) | 構造推論、検索、仮説、予算、再利用の詳細 |
| [architecture-v0.2.md](docs/architecture-v0.2.md) | FOLD-R記憶、H0/H1/H2、Capability Contract |
| [theory.md](docs/theory.md) | v0.1のSchur補完の数学背景 |
| [distribution-status.md](docs/distribution-status.md) | ファイルの所在と過去の配布記録。所在確認と実行検証は別 |
| [local-training.md](docs/local-training.md) | 既存の小型LM学習手順。v0.5の学習実装ではない |
| [reasoning-guide.md](docs/reasoning-guide.md) | 既存の部品/全体デモの手順 |
| [reasoning-plan.md](docs/reasoning-plan.md) / [research-plan.md](docs/research-plan.md) | 推論系R系列と記憶系P系列。最終構想の一括完了を示さない |
| [reasoning-validation.md](results/reasoning-validation.md) | 過去の検証範囲。今回の再実行結果ではない |

最終方針はv0.5を優先します。v0.5を実装する場合は、`theory-v0.5.md`で数理境界を確認し、`development-roadmap-v0.5.md`で対象段階とGateを決めてから作業します。v0.4の比較条件を、全方式をゼロから共同学習する義務や、最終構造を固定する規則として再適用しません。FOLD-Rの数値保証・scope・訂正の意味論は維持します。

## 設計とコードの区別

更新前のコミット`2db60499bce1ee65834c5d798543e76d6f4f6f9d`のGit treeを確認すると、以前「ローカルZIPのみ」と記載していたLM・探索系のファイルもリポジトリ内にあります。古い配布表を現在状態として扱わないでください。

| 対象 | 所在と今回の確認範囲 |
|---|---|
| v0.1参照カーネル | `fold_memory.py`, `demo.py`, `tests/`。コード変更なし |
| 応答capsule | `fold_lm/capsule.py`。既存ファイル |
| 既存LM関連 | `fold_lm/model.py`, `data.py`, `runner.py`, `cli.py`。所在確認のみ |
| 既存構造推論関連 | `fold_reasoning/index.py`, `core.py`, `demo.py`。所在確認のみ |
| v0.4の共有比較 | 設計文書。今回の更新で比較実装は追加していない |
| v0.5 / 理論 / ロードマップ / 不足情報取得 | 設計文書。モデル本体の実装・学習・性能検証とは別 |

ファイルがあることだけで、完成・正常動作・学習済みとは扱いません。設計文書の更新だけではコード・データ・重み・過去の実験結果は変更されません。

## 既存の部品を実行する例

Windows PowerShell、`asobiba/fold`から。以下は既存手順であり、今回の文書更新時の実行ログではありません。

```powershell
py -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
& $python -m pip install -r requirements-reasoning.txt
& $python -m fold_reasoning.components_demo
& $python -m unittest discover -s tests_reasoning -p test_components.py -v
```

CPU用の例です。既に同じ仮想環境がある場合は再作成不要です。CUDA環境へ適用する際は、既存環境と[学習手順](docs/local-training.md)を確認してください。過去の環境・検証記録を、現在の実機で再検証済みとは読み替えません。

## データはGit管理しない

`data/`, `datasets/`, `runs/`, `indices/`, `program_cache/`, `checkpoints/`, `outputs/`, `.cache/`, モデル重みを除外します。空ディレクトリはGitが保持しないため、必要なコマンドが作成します。

```powershell
git check-ignore -v data/raw/private.jsonl runs/reasoning/report.json indices/local.bin program_cache/local.json
```

`.gitignore`は既に追跡済みのファイルを追跡解除するものではありません。設計文書の更新へユーザーコーパスや学習重みは追加しません。

## v0.1カーネル

既存の実行方法を維持します。

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python demo.py --seed 20260909 --trials 100
```

既存テストとbaselineは変更していません。数値カーネルや限定課題の結果を、一般的な言語・推論・自己認識能力や既存LLMへの優位性の証明とは扱いません。
