# Target-only SFT supervision

更新: 2026-09-10。長期QA実験で、全文NLLが低くても所有者検索精度がchance付近に留まることを確認したため、質問・回答系ではpromptを入力として保持しつつtargetだけをloss対象にできる形式を追加する。

## JSONL形式

従来の全文学習はそのまま使える。

```jsonl
{"text":"通常の言語モデル学習用文章"}
```

QA/SFTでは次を使う。

```jsonl
{"prompt":"Important fact: ... Question: ... Answer: ","target":"Alice."}
```

`prompt`はモデルへ入力されるがlossは掛からない。`target`のUTF-8 byteと、その後のEOSだけが教師ラベルになる。追加metadata keyは保持せず無視する。`text`と`prompt/target`を同時に指定する曖昧なレコード、片方だけのprompt/target、空targetは拒否する。

## prepared schema 2

`prepare`が新規生成するmanifestはschema 2。各index rowは`[offset, token_length, loss_start]`となり、別の巨大mask fileは持たない。`loss_start`以降のtokenだけを`Corpus.batch()`が教師ラベルとして返し、それ以前は`-100`にする。runnerは既存どおりPyTorch cross entropyの`ignore_index=-100`を使用する。

既存のschema 1 prepared dataは互換読み込みする。schema 1は全next-token labelを有効と解釈するため、既存TinyStories実験を再prepareしなくても評価できる。

## 現在の制約

学習runnerはsequence blockごとに作業状態を初期化する。このためtarget-only文書はprompt+target+特殊tokenが1 blockに収まる必要がある。`Corpus`はtargeted documentが`seq_len`を超える場合、黙ってprompt contextを捨てずエラーにする。長いSFT/TBPTTは別実装が必要。

重複判定は結合後の全文byteで行う。同一内容がtrain/validationを跨げばsupervision modeに関係なく拒否する。同じsplit内で同一全文に異なるloss開始位置を与える場合も、曖昧な教師信号として拒否する。
