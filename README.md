# サーバ演習50本ノック

**001〜050の全50問が必修です。** ローカルの端末からbbserverに接続し、ジョブの投入、状態確認、結果確認、ログを使ったエラー修正と再投入を行います。

| 範囲 | 内容 |
|---|---|
| 001〜012 | SSH接続、CPUジョブの実行、失敗原因の特定と修正 |
| 013〜025 | 入力の送信、自分のデータでの実行、アーカイブの作成・展開、結果の取得、差分同期 |
| 026〜036 | conda環境、NumPyを使うジョブ、環境の再作成 |
| 037〜043 | PBSのキューと役割分担、CPU・メモリ・実行時間・GPUの指定、起動前エラー調査 |
| 044〜050 | 対話型ジョブ、ログ検索、自分のジョブの照会と取消、ディスク使用量の確認 |

公開鍵とアカウントは準備済みとします。サーバにログイン後、`git clone` でホームディレクトリに教材を取得して始めます（2回目以降のログインでは `git clone` は不要です）。

```bash
ssh bbserver
git clone https://github.com/physicshinzui/server-50-knocks-student.git
cd ~/server-50-knocks-student
source ./setup.sh
less EXERCISES.md
```

[問題集](EXERCISES.md)を順に進め、コマンドを調べるときは[コマンド集](COMMANDS.md)を参照してください。`server-check 問題番号` と `server-check --progress` はログインノードで実行します。判定ではサーバ上の成果物や質問への回答を確認し、一部の問題では `qstat` でPBSに照会します。ファイル転送の操作はローカルの別端末で行います。

演習用スクリプト `tools/run_lesson.sh` は入力データ（TSV/CSV）の `value` 列の件数・合計・平均を集計し、ログ（`run.log`）と結果（`result.json`）を `work/runs/ジョブID/` に出力します（詳細は [COMMANDS.md](COMMANDS.md) を参照）。提出方法は教員の指示に従ってください。

今回の改訂で問題番号と手順が変わりました。進捗は `progress/completed-2026.50-r3.json` に記録します。改訂前の教材を使っていた場合は、新しい作業用コピーで始めてください。
