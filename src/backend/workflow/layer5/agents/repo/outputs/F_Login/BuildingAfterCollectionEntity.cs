using System.ComponentModel.DataAnnotations.Schema;
using vba_brain.Domain.Entities.Base;

namespace vba_brain.Domain.Entities;

/// <summary>
/// TBLビルアフター回収
/// </summary>
public class BuildingAfterCollectionEntity : BaseEntity
{
    [Column("登録番号")]
    public string RegistrationNumber { get; set; } = string.Empty;  // 登録番号
    [Column("店所コード")]
    public string BranchCode { get; set; } = string.Empty;  // 店所コード
    [Column("登録日")]
    public DateTime? RegistrationDate { get; set; }  // 登録日
    [Column("流れ")]
    public string Flow { get; set; } = string.Empty;  // 流れ
    [Column("見積フラグ")]
    public string QuoteFlag { get; set; } = string.Empty;  // 見積フラグ
    [Column("請求フラグ")]
    public string InvoiceFlag { get; set; } = string.Empty;  // 請求フラグ
    [Column("入金フラグ")]
    public string PaymentFlag { get; set; } = string.Empty;  // 入金フラグ
    [Column("登録者氏名")]
    public string RegisteredBy { get; set; } = string.Empty;  // 登録者氏名
    [Column("担当者コード")]
    public string HandlerCode { get; set; } = string.Empty;  // 担当者コード
    [Column("担当者氏名")]
    public string PersonInChargeName { get; set; } = string.Empty;  // 担当者氏名
    [Column("整理番号１＿店所")]
    public string RefNo1Branch { get; set; } = string.Empty;  // 整理番号１＿店所
    [Column("整理番号２＿期")]
    public string RefNo2Period { get; set; } = string.Empty;  // 整理番号２＿期
    [Column("整理番号３＿連番１")]
    public string RefNo3SeqNo1 { get; set; } = string.Empty;  // 整理番号３＿連番１
    [Column("整理番号４＿連番２")]
    public string RefNo4SeqNo2 { get; set; } = string.Empty;  // 整理番号４＿連番２
    [Column("受付日")]
    public DateTime? ReceptionDate { get; set; }  // 受付日
    [Column("工事名称")]
    public string ConstructionName { get; set; } = string.Empty;  // 工事名称
    [Column("作業予定日")]
    public DateTime? ScheduledWorkDate { get; set; }  // 作業予定日
    [Column("作業完了日")]
    public DateTime? WorkCompletionDate { get; set; }  // 作業完了日
    [Column("製品手配区分")]
    public string ProductArrangementCategory { get; set; } = string.Empty;  // 製品手配区分
    [Column("製品手配区分名")]
    public string ProductArrangementCategoryName { get; set; } = string.Empty;  // 製品手配区分名
    [Column("責任区分")]
    public string ResponsibilityCategory { get; set; } = string.Empty;  // 責任区分
    [Column("責任区分名")]
    public string ResponsibilityCategoryName { get; set; } = string.Empty;  // 責任区分名
    [Column("適正製品代金")]
    public string AppropriateProductPrice { get; set; } = string.Empty;  // 適正製品代金
    [Column("適正工賃")]
    public string AppropriateLaborCost { get; set; } = string.Empty;  // 適正工賃
    [Column("適正合計額")]
    public string AppropriateTotalAmount { get; set; } = string.Empty;  // 適正合計額
    [Column("請求先")]
    public string Client { get; set; } = string.Empty;  // 請求先
    [Column("敬称区分")]
    public string TitleCategory { get; set; } = string.Empty;  // 敬称区分
    [Column("敬称名")]
    public string TitleName { get; set; } = string.Empty;  // 敬称名
    [Column("請求区分")]
    public string BillingCategory { get; set; } = string.Empty;  // 請求区分
    [Column("請求区分名")]
    public string BillingCategoryName { get; set; } = string.Empty;  // 請求区分名
    [Column("請求書提出日")]
    public DateTime? InvoiceSubmissionDate { get; set; }  // 請求書提出日
    [Column("用途１")]
    public string Usage1 { get; set; } = string.Empty;  // 用途１
    [Column("明細区分１")]
    public string DetailCategory1 { get; set; } = string.Empty;  // 明細区分１
    [Column("数量１")]
    public string Quantity1 { get; set; } = string.Empty;  // 数量１
    [Column("単位１")]
    public string Unit1 { get; set; } = string.Empty;  // 単位１
    [Column("単価１")]
    public string UnitPrice1 { get; set; } = string.Empty;  // 単価１
    [Column("金額１")]
    public string Amount1 { get; set; } = string.Empty;  // 金額１
    [Column("用途２")]
    public string Usage2 { get; set; } = string.Empty;  // 用途２
    [Column("明細区分２")]
    public string DetailCategory2 { get; set; } = string.Empty;  // 明細区分２
    [Column("数量２")]
    public string Quantity2 { get; set; } = string.Empty;  // 数量２
    [Column("単位２")]
    public string Unit2 { get; set; } = string.Empty;  // 単位２
    [Column("単価２")]
    public string UnitPrice2 { get; set; } = string.Empty;  // 単価２
    [Column("金額２")]
    public string Amount2 { get; set; } = string.Empty;  // 金額２
    [Column("用途３")]
    public string Usage3 { get; set; } = string.Empty;  // 用途３
    [Column("明細区分３")]
    public string DetailCategory3 { get; set; } = string.Empty;  // 明細区分３
    [Column("数量３")]
    public string Quantity3 { get; set; } = string.Empty;  // 数量３
    [Column("単位３")]
    public string Unit3 { get; set; } = string.Empty;  // 単位３
    [Column("単価３")]
    public string UnitPrice3 { get; set; } = string.Empty;  // 単価３
    [Column("金額３")]
    public string Amount3 { get; set; } = string.Empty;  // 金額３
    [Column("用途４")]
    public string Usage4 { get; set; } = string.Empty;  // 用途４
    [Column("明細区分４")]
    public string DetailCategory4 { get; set; } = string.Empty;  // 明細区分４
    [Column("数量４")]
    public string Quantity4 { get; set; } = string.Empty;  // 数量４
    [Column("単位４")]
    public string Unit4 { get; set; } = string.Empty;  // 単位４
    [Column("単価４")]
    public string UnitPrice4 { get; set; } = string.Empty;  // 単価４
    [Column("金額４")]
    public string Amount4 { get; set; } = string.Empty;  // 金額４
    [Column("用途５")]
    public string Usage5 { get; set; } = string.Empty;  // 用途５
    [Column("明細区分５")]
    public string DetailCategory5 { get; set; } = string.Empty;  // 明細区分５
    [Column("数量５")]
    public string Quantity5 { get; set; } = string.Empty;  // 数量５
    [Column("単位５")]
    public string Unit5 { get; set; } = string.Empty;  // 単位５
    [Column("単価５")]
    public string UnitPrice5 { get; set; } = string.Empty;  // 単価５
    [Column("金額５")]
    public string Amount5 { get; set; } = string.Empty;  // 金額５
    [Column("用途６")]
    public string Usage6 { get; set; } = string.Empty;  // 用途６
    [Column("明細区分６")]
    public string DetailCategory6 { get; set; } = string.Empty;  // 明細区分６
    [Column("数量６")]
    public string Quantity6 { get; set; } = string.Empty;  // 数量６
    [Column("単位６")]
    public string Unit6 { get; set; } = string.Empty;  // 単位６
    [Column("単価６")]
    public string UnitPrice6 { get; set; } = string.Empty;  // 単価６
    [Column("金額６")]
    public string Amount6 { get; set; } = string.Empty;  // 金額６
    [Column("用途７")]
    public string Usage7 { get; set; } = string.Empty;  // 用途７
    [Column("明細区分７")]
    public string DetailCategory7 { get; set; } = string.Empty;  // 明細区分７
    [Column("数量７")]
    public string Quantity7 { get; set; } = string.Empty;  // 数量７
    [Column("単位７")]
    public string Unit7 { get; set; } = string.Empty;  // 単位７
    [Column("単価７")]
    public string UnitPrice7 { get; set; } = string.Empty;  // 単価７
    [Column("金額７")]
    public string Amount7 { get; set; } = string.Empty;  // 金額７
    [Column("用途８")]
    public string Usage8 { get; set; } = string.Empty;  // 用途８
    [Column("明細区分８")]
    public string DetailCategory8 { get; set; } = string.Empty;  // 明細区分８
    [Column("数量８")]
    public string Quantity8 { get; set; } = string.Empty;  // 数量８
    [Column("単位８")]
    public string Unit8 { get; set; } = string.Empty;  // 単位８
    [Column("単価８")]
    public string UnitPrice8 { get; set; } = string.Empty;  // 単価８
    [Column("金額８")]
    public string Amount8 { get; set; } = string.Empty;  // 金額８
    [Column("用途９")]
    public string Usage9 { get; set; } = string.Empty;  // 用途９
    [Column("明細区分９")]
    public string DetailCategory9 { get; set; } = string.Empty;  // 明細区分９
    [Column("数量９")]
    public string Quantity9 { get; set; } = string.Empty;  // 数量９
    [Column("単位９")]
    public string Unit9 { get; set; } = string.Empty;  // 単位９
    [Column("単価９")]
    public string UnitPrice9 { get; set; } = string.Empty;  // 単価９
    [Column("金額９")]
    public string Amount9 { get; set; } = string.Empty;  // 金額９
    [Column("用途１０")]
    public string Usage10 { get; set; } = string.Empty;  // 用途１０
    [Column("明細区分１０")]
    public string DetailCategory10 { get; set; } = string.Empty;  // 明細区分１０
    [Column("数量１０")]
    public string Quantity10 { get; set; } = string.Empty;  // 数量１０
    [Column("単位１０")]
    public string Unit10 { get; set; } = string.Empty;  // 単位１０
    [Column("単価１０")]
    public string UnitPrice10 { get; set; } = string.Empty;  // 単価１０
    [Column("金額１０")]
    public string Amount10 { get; set; } = string.Empty;  // 金額１０
    [Column("用途１１")]
    public string Usage11 { get; set; } = string.Empty;  // 用途１１
    [Column("明細区分１１")]
    public string DetailCategory11 { get; set; } = string.Empty;  // 明細区分１１
    [Column("数量１１")]
    public string Quantity11 { get; set; } = string.Empty;  // 数量１１
    [Column("単位１１")]
    public string Unit11 { get; set; } = string.Empty;  // 単位１１
    [Column("単価１１")]
    public string UnitPrice11 { get; set; } = string.Empty;  // 単価１１
    [Column("金額１１")]
    public string Amount11 { get; set; } = string.Empty;  // 金額１１
    [Column("用途１２")]
    public string Usage12 { get; set; } = string.Empty;  // 用途１２
    [Column("明細区分１２")]
    public string DetailCategory12 { get; set; } = string.Empty;  // 明細区分１２
    [Column("数量１２")]
    public string Quantity12 { get; set; } = string.Empty;  // 数量１２
    [Column("単位１２")]
    public string Unit12 { get; set; } = string.Empty;  // 単位１２
    [Column("単価１２")]
    public string UnitPrice12 { get; set; } = string.Empty;  // 単価１２
    [Column("金額１２")]
    public string Amount12 { get; set; } = string.Empty;  // 金額１２
    [Column("用途１３")]
    public string Usage13 { get; set; } = string.Empty;  // 用途１３
    [Column("明細区分１３")]
    public string DetailCategory13 { get; set; } = string.Empty;  // 明細区分１３
    [Column("数量１３")]
    public string Quantity13 { get; set; } = string.Empty;  // 数量１３
    [Column("単位１３")]
    public string Unit13 { get; set; } = string.Empty;  // 単位１３
    [Column("単価１３")]
    public string UnitPrice13 { get; set; } = string.Empty;  // 単価１３
    [Column("金額１３")]
    public string Amount13 { get; set; } = string.Empty;  // 金額１３
    [Column("用途１４")]
    public string Usage14 { get; set; } = string.Empty;  // 用途１４
    [Column("明細区分１４")]
    public string DetailCategory14 { get; set; } = string.Empty;  // 明細区分１４
    [Column("数量１４")]
    public string Quantity14 { get; set; } = string.Empty;  // 数量１４
    [Column("単位１４")]
    public string Unit14 { get; set; } = string.Empty;  // 単位１４
    [Column("単価１４")]
    public string UnitPrice14 { get; set; } = string.Empty;  // 単価１４
    [Column("金額１４")]
    public string Amount14 { get; set; } = string.Empty;  // 金額１４
    [Column("用途１５")]
    public string Usage15 { get; set; } = string.Empty;  // 用途１５
    [Column("明細区分１５")]
    public string DetailCategory15 { get; set; } = string.Empty;  // 明細区分１５
    [Column("数量１５")]
    public string Quantity15 { get; set; } = string.Empty;  // 数量１５
    [Column("単位１５")]
    public string Unit15 { get; set; } = string.Empty;  // 単位１５
    [Column("単価１５")]
    public string UnitPrice15 { get; set; } = string.Empty;  // 単価１５
    [Column("金額１５")]
    public string Amount15 { get; set; } = string.Empty;  // 金額１５
    [Column("用途１６")]
    public string Usage16 { get; set; } = string.Empty;  // 用途１６
    [Column("明細区分１６")]
    public string DetailCategory16 { get; set; } = string.Empty;  // 明細区分１６
    [Column("数量１６")]
    public string Quantity16 { get; set; } = string.Empty;  // 数量１６
    [Column("単位１６")]
    public string Unit16 { get; set; } = string.Empty;  // 単位１６
    [Column("単価１６")]
    public string UnitPrice16 { get; set; } = string.Empty;  // 単価１６
    [Column("金額１６")]
    public string Amount16 { get; set; } = string.Empty;  // 金額１６
    [Column("用途１７")]
    public string Usage17 { get; set; } = string.Empty;  // 用途１７
    [Column("明細区分１７")]
    public string DetailCategory17 { get; set; } = string.Empty;  // 明細区分１７
    [Column("数量１７")]
    public string Quantity17 { get; set; } = string.Empty;  // 数量１７
    [Column("単位１７")]
    public string Unit17 { get; set; } = string.Empty;  // 単位１７
    [Column("単価１７")]
    public string UnitPrice17 { get; set; } = string.Empty;  // 単価１７
    [Column("金額１７")]
    public string Amount17 { get; set; } = string.Empty;  // 金額１７
    [Column("用途１８")]
    public string Usage18 { get; set; } = string.Empty;  // 用途１８
    [Column("明細区分１８")]
    public string DetailCategory18 { get; set; } = string.Empty;  // 明細区分１８
    [Column("数量１８")]
    public string Quantity18 { get; set; } = string.Empty;  // 数量１８
    [Column("単位１８")]
    public string Unit18 { get; set; } = string.Empty;  // 単位１８
    [Column("単価１８")]
    public string UnitPrice18 { get; set; } = string.Empty;  // 単価１８
    [Column("金額１８")]
    public string Amount18 { get; set; } = string.Empty;  // 金額１８
    [Column("用途１９")]
    public string Usage19 { get; set; } = string.Empty;  // 用途１９
    [Column("明細区分１９")]
    public string DetailCategory19 { get; set; } = string.Empty;  // 明細区分１９
    [Column("数量１９")]
    public string Quantity19 { get; set; } = string.Empty;  // 数量１９
    [Column("単位１９")]
    public string Unit19 { get; set; } = string.Empty;  // 単位１９
    [Column("単価１９")]
    public string UnitPrice19 { get; set; } = string.Empty;  // 単価１９
    [Column("金額１９")]
    public string Amount19 { get; set; } = string.Empty;  // 金額１９
    [Column("用途２０")]
    public string Usage20 { get; set; } = string.Empty;  // 用途２０
    [Column("明細区分２０")]
    public string DetailCategory20 { get; set; } = string.Empty;  // 明細区分２０
    [Column("数量２０")]
    public string Quantity20 { get; set; } = string.Empty;  // 数量２０
    [Column("単位２０")]
    public string Unit20 { get; set; } = string.Empty;  // 単位２０
    [Column("単価２０")]
    public string UnitPrice20 { get; set; } = string.Empty;  // 単価２０
    [Column("金額２０")]
    public string Amount20 { get; set; } = string.Empty;  // 金額２０
    [Column("請求先住所１")]
    public string ClientAddress1 { get; set; } = string.Empty;  // 請求先住所１
    [Column("請求先住所２")]
    public string ClientAddress2 { get; set; } = string.Empty;  // 請求先住所２
    [Column("請求先電話番号")]
    public string ClientPhoneNumber { get; set; } = string.Empty;  // 請求先電話番号
    [Column("請求先担当者")]
    public string ClientContactPerson { get; set; } = string.Empty;  // 請求先担当者
    [Column("請求製品代金")]
    public string BilledProductPrice { get; set; } = string.Empty;  // 請求製品代金
    [Column("請求工賃")]
    public string BilledLaborCost { get; set; } = string.Empty;  // 請求工賃
    [Column("請求送料")]
    public string BilledShippingCost { get; set; } = string.Empty;  // 請求送料
    [Column("請求消費税額")]
    public string BilledConsumptionTax { get; set; } = string.Empty;  // 請求消費税額
    [Column("請求合計額")]
    public string TotalBillingAmount { get; set; } = string.Empty;  // 請求合計額
    [Column("入金完了日")]
    public DateTime? PaymentCompletionDate { get; set; }  // 入金完了日
    [Column("入金製品代金")]
    public string PaidProductPrice { get; set; } = string.Empty;  // 入金製品代金
    [Column("入金工賃")]
    public string PaidLaborCost { get; set; } = string.Empty;  // 入金工賃
    [Column("入金消費税額")]
    public string PaidConsumptionTax { get; set; } = string.Empty;  // 入金消費税額
    [Column("入金合計額")]
    public string PaidTotalAmount { get; set; } = string.Empty;  // 入金合計額
    [Column("回収不能日")]
    public DateTime? UnrecoverableDate { get; set; }  // 回収不能日
    [Column("回収不能製品代金")]
    public string UnrecoverableProductPrice { get; set; } = string.Empty;  // 回収不能製品代金
    [Column("回収不能工賃")]
    public string UnrecoverableLaborCost { get; set; } = string.Empty;  // 回収不能工賃
    [Column("回収不能消費税額")]
    public string UnrecoverableConsumptionTax { get; set; } = string.Empty;  // 回収不能消費税額
    [Column("回収不能合計額")]
    public string UnrecoverableTotalAmount { get; set; } = string.Empty;  // 回収不能合計額
    [Column("未入金合計額")]
    public string UnpaidTotalAmount { get; set; } = string.Empty;  // 未入金合計額
    [Column("予備１")]
    public string Spare1 { get; set; } = string.Empty;  // 予備１
    [Column("予備２")]
    public string Spare2 { get; set; } = string.Empty;  // 予備２
    [Column("予備３")]
    public string Spare3 { get; set; } = string.Empty;  // 予備３
    [Column("予備４")]
    public string Spare4 { get; set; } = string.Empty;  // 予備４
    [Column("予備５")]
    public string Spare5 { get; set; } = string.Empty;  // 予備５
    [Column("予備６")]
    public string Spare6 { get; set; } = string.Empty;  // 予備６
    [Column("予備７")]
    public string Spare7 { get; set; } = string.Empty;  // 予備７
    [Column("予備８")]
    public string Spare8 { get; set; } = string.Empty;  // 予備８
    [Column("予備９")]
    public string Spare9 { get; set; } = string.Empty;  // 予備９
    [Column("予備１０")]
    public string Spare10 { get; set; } = string.Empty;  // 予備１０
    [Column("見積先住所１")]
    public string QuotationAddress1 { get; set; } = string.Empty;  // 見積先住所１
    [Column("見積先住所２")]
    public string QuotationAddress2 { get; set; } = string.Empty;  // 見積先住所２
    [Column("見積有効期間")]
    public string QuotationValidityPeriod { get; set; } = string.Empty;  // 見積有効期間
    [Column("支払条件")]
    public string PaymentTerms { get; set; } = string.Empty;  // 支払条件
    [Column("納品書備考")]
    public string DeliveryNoteRemarks { get; set; } = string.Empty;  // 納品書備考
    [Column("更新日")]
    public DateTime? UpdateDate { get; set; }  // 更新日
    [Column("仕訳ナンバー１")]
    public string JournalNumber1 { get; set; } = string.Empty;  // 仕訳ナンバー１
    [Column("仕訳ナンバー２")]
    public string JournalNumber2 { get; set; } = string.Empty;  // 仕訳ナンバー２
    [Column("入金日")]
    public DateTime? PaymentDate { get; set; }  // 入金日
    [Column("適正送料")]
    public string AppropriateShippingCost { get; set; } = string.Empty;  // 適正送料
    [Column("適正諸経費")]
    public string AppropriateMiscExpenses { get; set; } = string.Empty;  // 適正諸経費
    [Column("適正消費税")]
    public string AppropriateConsumptionTax { get; set; } = string.Empty;  // 適正消費税
    [Column("請求諸経費")]
    public string BilledMiscExpenses { get; set; } = string.Empty;  // 請求諸経費
    [Column("入金完了日１")]
    public DateTime? PaymentCompletionDate1 { get; set; }  // 入金完了日１
    [Column("入金完了日２")]
    public DateTime? PaymentCompletionDate2 { get; set; }  // 入金完了日２
    [Column("入金完了日３")]
    public DateTime? PaymentCompletionDate3 { get; set; }  // 入金完了日３
    [Column("入金合計額１")]
    public string PaidTotalAmount1 { get; set; } = string.Empty;  // 入金合計額１
    [Column("入金合計額２")]
    public string PaidTotalAmount2 { get; set; } = string.Empty;  // 入金合計額２
    [Column("入金合計額３")]
    public string PaidTotalAmount3 { get; set; } = string.Empty;  // 入金合計額３
    [Column("仕訳ナンバー１Ａ")]
    public string JournalNumber1A { get; set; } = string.Empty;  // 仕訳ナンバー１Ａ
    [Column("仕訳ナンバー２Ａ")]
    public string JournalNumber2A { get; set; } = string.Empty;  // 仕訳ナンバー２Ａ
    [Column("仕訳ナンバー１Ｂ")]
    public string JournalNumber1B { get; set; } = string.Empty;  // 仕訳ナンバー１Ｂ
    [Column("仕訳ナンバー２Ｂ")]
    public string JournalNumber2B { get; set; } = string.Empty;  // 仕訳ナンバー２Ｂ
    [Column("仕訳ナンバー１Ｃ")]
    public string JournalNumber1C { get; set; } = string.Empty;  // 仕訳ナンバー１Ｃ
    [Column("仕訳ナンバー２Ｃ")]
    public string JournalNumber2C { get; set; } = string.Empty;  // 仕訳ナンバー２Ｃ
    [Column("連番")]
    public string SeqNo { get; set; } = string.Empty;  // 連番
    [Column("ＯＮＯＦＦ")]
    public string OnOff { get; set; } = string.Empty;  // ＯＮＯＦＦ
    [Column("コメント")]
    public string Comment1 { get; set; } = string.Empty;  // コメント
    [Column("特記事項")]
    public string SpecialNotes { get; set; } = string.Empty;  // 特記事項
    [Column("回収不能理由")]
    public string UnrecoverableReason { get; set; } = string.Empty;  // 回収不能理由
    [Column("請求先住所３")]
    public string ClientAddress3 { get; set; } = string.Empty;  // 請求先住所３
    [Column("請求先住所４")]
    public string ClientAddress4 { get; set; } = string.Empty;  // 請求先住所４
    [Column("請求先ＦＡＸ番号")]
    public string ClientFaxNumber { get; set; } = string.Empty;  // 請求先ＦＡＸ番号
    [Column("見積先住所３")]
    public string QuotationAddress3 { get; set; } = string.Empty;  // 見積先住所３
    [Column("見積先住所４")]
    public string QuotationAddress4 { get; set; } = string.Empty;  // 見積先住所４
    [Column("納品場所")]
    public string DeliveryLocation { get; set; } = string.Empty;  // 納品場所
    [Column("シリーズ")]
    public string Series { get; set; } = string.Empty;  // シリーズ
    [Column("対応業者")]
    public string Contractor { get; set; } = string.Empty;  // 対応業者
    [Column("構造（木造・非木造）")]
    public string ConstructionType { get; set; } = string.Empty;  // 構造（木造・非木造）
    [Column("竣工日")]
    public string CompletionDate { get; set; } = string.Empty;  // 竣工日
    [Column("お客様メールアドレス")]
    public string CustomerEmailAddress { get; set; } = string.Empty;  // お客様メールアドレス
    [Column("領収書希望")]
    public string ReceiptRequested { get; set; } = string.Empty;  // 領収書希望
    [Column("請求方法")]
    public string BillingMethod { get; set; } = string.Empty;  // 請求方法
    [Column("本工事番号")]
    public string MainConstructionNumber { get; set; } = string.Empty;  // 本工事番号
    [Column("請求書送付先")]
    public string InvoiceDestination { get; set; } = string.Empty;  // 請求書送付先
    [Column("初回連絡")]
    public string InitialContact { get; set; } = string.Empty;  // 初回連絡
    [Column("手配")]
    public string Arrangement { get; set; } = string.Empty;  // 手配
    [Column("予備１１")]
    public string Spare11 { get; set; } = string.Empty;  // 予備１１
    [Column("予備１２")]
    public string Spare12 { get; set; } = string.Empty;  // 予備１２
    [Column("予備１３")]
    public string Spare13 { get; set; } = string.Empty;  // 予備１３
    [Column("予備１４")]
    public string Spare14 { get; set; } = string.Empty;  // 予備１４
    [Column("予備１５")]
    public string Spare15 { get; set; } = string.Empty;  // 予備１５
    [Column("予備１６")]
    public string Spare16 { get; set; } = string.Empty;  // 予備１６
    [Column("予備１７")]
    public string Spare17 { get; set; } = string.Empty;  // 予備１７
    [Column("予備１８")]
    public string Spare18 { get; set; } = string.Empty;  // 予備１８
    [Column("予備１９")]
    public string Spare19 { get; set; } = string.Empty;  // 予備１９
    [Column("予備２０")]
    public string Spare20 { get; set; } = string.Empty;  // 予備２０
    [Column("予備２１")]
    public string Spare21 { get; set; } = string.Empty;  // 予備２１
    [Column("予備２２")]
    public string Spare22 { get; set; } = string.Empty;  // 予備２２
    [Column("予備２３")]
    public string Spare23 { get; set; } = string.Empty;  // 予備２３
    [Column("予備２４")]
    public string Spare24 { get; set; } = string.Empty;  // 予備２４
    [Column("予備２５")]
    public string Spare25 { get; set; } = string.Empty;  // 予備２５
    [Column("予備２６")]
    public string Spare26 { get; set; } = string.Empty;  // 予備２６
    [Column("予備２７")]
    public string Spare27 { get; set; } = string.Empty;  // 予備２７
    [Column("予備２８")]
    public string Spare28 { get; set; } = string.Empty;  // 予備２８
    [Column("予備２９")]
    public string Spare29 { get; set; } = string.Empty;  // 予備２９
    [Column("予備３０")]
    public string Spare30 { get; set; } = string.Empty;  // 予備３０
    [Column("受付ＩＤ")]
    public string ReceptionId { get; set; } = string.Empty;  // 受付ＩＤ
    [Column("報告ＩＤ")]
    public string ReportId { get; set; } = string.Empty;  // 報告ＩＤ
}
