------------Main Table------------
T_ID_PASS
WSTEM_TBLビルＡＭ受付
WSTEM_TBLビルＡＭ報告
WSTEM_TBLビルＡＭ報告処置
WSTEM_TBLビルＡＭ報告点検
WSTEM_TBLビルＡＭ報告不具合
WSTEM_TBLビルアフター回収
WSTEM_TBLビルサブ明細
 
--------Obj---------
C000_MAINⅡ 宛先テーブル
C000_MAINⅡ 差出人テーブル
T000_MAINⅡ ONOF-1選択抽出_テーブル作成
T000_MAINⅡ ONOF-1選択抽出_請求書提出日チェック
T000_MAINⅡ ONOF-1選択抽出_請求先チェック
T000_MAINⅡ 登録番号抽出 テーブル
T023_地区CD設定Ⅱ
 
------------Local------------------
T_ID_PASS_local
WSTEM_TBLビルアフター回収_localbak
 
------------Obj?---------------
T022_03地方 - update
T022_05地方 - update
T022_都道府県抽出用 - xuất file
T024_登録状況設定 - CRUD
T024_登録状況設定_元 - temp data
//T025_ログインユーザー設定_元 - store T_ID_PASS
T026_未登録表示設定 - store some field
T027_入金情報一括入力テーブル - store some field
T031_登録状況_表示設定 - store some field
T911_MAINⅡ_集計_額先月 - store some field (or use with)
T911_MAINⅡ_集計_額当月 - store some field (or use with)
Ｔ911_MAINⅡ_集計_額累計 - store some field (or use with)
T912_MAINⅡ_集計_額先月_担当者 - store some field (or use with)
T912_MAINⅡ_集計_額当月_担当者 - store some field (or use with)
Ｔ912_MAINⅡ_集計_額累計_担当者 - store some field (or use with)
T_LoginUser - user session
T_インストール日 - store some field
 
-------------Master/Config---------------------
JM_001_実績見出用
JM_002_MONOS年月M
JM_003_営業所⇒母店
M_回収管理リスト
M_請求
M_請求区分詳細
M_単位
M_担当者コード
M_提出元
M_店所
M_入金
M_流れ
S01_集計マスター
T_テスト
T_全集計
T011_期
T023_地区CD設定
TM_拠点
フォルダ名
 
M_明細区分N
T021_支店
T021_地方
 
------------Use With-------------------
C003_アフターMAINto編集Ⅱ 連番２テーブル
C003_アフターMAINto編集Ⅱ_複製抽出_テーブル
T000_MAINⅡ ONOF-1選択抽出 テーブル
T000_MAINⅡ_複製番号抽出_テーブル
T011_期設定
T011_期設定_前期