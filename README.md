# ユタカ製作所 在庫管理アプリ

支給品・調達品の在庫管理Webアプリ（FastAPI）。設計は [設計書.md](設計書.md) 参照。

## 実装済み機能（フェーズ1〜6）
- 個人別ログイン認証（個人マスタ app_user）
- 品目マスタ：登録・編集・一覧・検索（固有番号/名称）、支給/調達 区分
- QRコード印刷：選択品目をA5・2×2面付けで出力（QR＋下に製品番号、左上→右上→左下→右下）
- 発注処理：調達発注／客先準備分。発注時に入荷予定を自動生成
- 注文依頼書PDF（A5横・1枚4明細）／加工依頼書PDF（A5縦・調達品のみ・図面欄）
- 入荷予定登録 → 受入消込（在庫+）／使用・仕損報告（在庫−）
- 履歴（依頼／入荷／使用）
- 図面登録（DB保存・品目ごと）
- 設定（注文依頼書フッターの自社情報を編集）

### メニュー構成
調達品（品目／発注=注文+加工依頼書／一覧）・支給品（品目／客先準備分発注=注文のみ／一覧）・共通（入荷受入／使用報告／在庫確認QR／履歴／設定）

## ローカル起動
```bash
cd yutaka-inventory
python -m pip install -r requirements.txt   # ローカルでpsycopgが不要ならスキップ可
python seed.py                              # admin/admin と サンプル品目を作成
python -m uvicorn app.main:app --reload --port 8123
```
ブラウザで http://127.0.0.1:8123/ → admin / admin でログイン。

## DB
- ローカル: SQLite（プロジェクト直下 `yutaka_inventory.db` を自動生成）
- 本番: 環境変数 `DATABASE_URL` に Neon の PostgreSQL接続文字列を設定すると自動で切替

## デプロイ（Render 無料 + Neon 無料 / フェーズ6で実施予定）
- Neonで無料Postgresを作成 → 接続文字列を取得
- Render の Web Service（無料）を作成
  - Build: `pip install -r requirements.txt`
  - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - 環境変数: `DATABASE_URL`（Neon）, `SECRET_KEY`（任意のランダム文字列）

## デプロイ手順（Render無料 + Neon無料）
1. Neon で無料 PostgreSQL を作成 → 接続文字列（postgresql://...）を取得
2. このフォルダを GitHub リポジトリに push
3. Render で「New Web Service」→ リポジトリを連携（render.yaml を自動認識）
   - 環境変数 `DATABASE_URL` に Neon の接続文字列を設定
   - `SECRET_KEY` は自動生成
4. 初回デプロイ後、本番DBに管理者を作成：Render Shell で `python seed.py` を実行
   （または admin 作成用の一時エンドポイントを用意）
※ Procfile / runtime.txt(python-3.12) / render.yaml 同梱済み

## 今後の拡張候補
- 発注ステータスの自動更新（受入完了で closed 等）
- 在庫マイナス時の警告、棚卸し機能
- 図面の外部ストレージ移行（DB肥大化対策）
