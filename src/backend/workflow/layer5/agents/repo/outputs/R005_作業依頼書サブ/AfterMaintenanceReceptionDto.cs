using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace vba_brain.Domain.DTOs.BuildingAfterCollection;

public class AfterMaintenanceReceptionDto
{
    [Required]
    [MaxLength(16)]
    [Column("登録番号")]
    public string RegistrationNumber { get; set; } = string.Empty;  // 登録番号
    [MaxLength(100)]
    [Column("QuickNo")]
    public string QuickNo { get; set; } = string.Empty;  // 予備５
    [Column("受付日")]
    public DateTime? ReceptionDate { get; set; }  // 受付日
    [MaxLength(100)]
    [Column("担当者氏名")]
    public string PersonInChargeName { get; set; } = string.Empty;  // 担当者氏名
    [MaxLength(26)]
    [Column("受付ＩＤ")]
    public string ReceptionId { get; set; } = string.Empty;  // 受付ＩＤ
    [Column("ＡＭ依頼先施工管理")]
    public string AmRequesterConstructionManagement { get; set; } = string.Empty;  // ＡＭ依頼先施工管理
    [Column("ＡＭ受付時刻")]
    public string AmReceptionTime { get; set; } = string.Empty;  // ＡＭ受付時刻
    [Column("ＡＭ受付所属課")]
    public string AmReceptionDepartment { get; set; } = string.Empty;  // ＡＭ受付所属課
    [Column("ＡＭ訪問先携帯電話")]
    public string AmVisitDestinationMobilePhone { get; set; } = string.Empty;  // ＡＭ訪問先携帯電話
    [Column("ＡＭ訪問先メール")]
    public string AmVisitDestinationEmail { get; set; } = string.Empty;  // ＡＭ訪問先メール
    [Column("ＡＭ訪問先自宅電話番号")]
    public string AmVisitDestinationHomePhone { get; set; } = string.Empty;  // ＡＭ訪問先自宅電話番号
    [Column("ＡＭ訪問先勤務先電話番号")]
    public string AmVisitDestinationWorkPhone { get; set; } = string.Empty;  // ＡＭ訪問先勤務先電話番号
    [MaxLength(100)]
    [Column("工事名称")]
    public string ConstructionName { get; set; } = string.Empty;  // 工事名称
    [MaxLength(100)]
    [Column("工事先建物名")]
    public string ConstructionSiteBuildingName { get; set; } = string.Empty;  // 予備１３
    [MaxLength(100)]
    [Column("訪問先お客様名")]
    public string VisitDestinationCustomerName { get; set; } = string.Empty;  // 予備１４
    [MaxLength(100)]
    [Column("訪問先郵便番号")]
    public string VisitDestinationPostalCode { get; set; } = string.Empty;  // 予備１５
    [MaxLength(100)]
    [Column("訪問先都道府県")]
    public string VisitDestinationPrefecture { get; set; } = string.Empty;  // 予備１６
    [MaxLength(100)]
    [Column("訪問先市町村")]
    public string VisitDestinationCity { get; set; } = string.Empty;  // 予備１７
    [MaxLength(100)]
    [Column("訪問先町名番地")]
    public string VisitDestinationAddress { get; set; } = string.Empty;  // 予備１８
    [MaxLength(100)]
    [Column("訪問先建物名")]
    public string VisitDestinationBuildingName { get; set; } = string.Empty;  // 予備１９
    [MaxLength(100)]
    [Column("訪問先部屋番号")]
    public string VisitDestinationRoomNumber { get; set; } = string.Empty;  // 予備２０
    [Column("店所用管理番号")]
    public string StoreManagementNumber { get; set; } = string.Empty;  // ＡＭ訪問先建物名
    [Column("ＡＭ依頼者１会社名")]
    public string AmRequester1CompanyName { get; set; } = string.Empty;  // ＡＭ依頼者１会社名
    [Column("ＡＭ依頼者１お客様名")]
    public string AmRequester1CustomerName { get; set; } = string.Empty;  // ＡＭ依頼者１お客様名
    [Column("ＡＭ依頼者１電話番号")]
    public string AmRequester1PhoneNumber { get; set; } = string.Empty;  // ＡＭ依頼者１電話番号
    [Column("ＡＭ依頼者１ＦＡＸ")]
    public string AmRequester1Fax { get; set; } = string.Empty;  // ＡＭ依頼者１ＦＡＸ
    [Column("ＡＭ依頼者１メール")]
    public string AmRequester1Email { get; set; } = string.Empty;  // ＡＭ依頼者１メール
    [Column("ＡＭ依頼者２会社名")]
    public string AmRequester2CompanyName { get; set; } = string.Empty;  // ＡＭ依頼者２会社名
    [Column("ＡＭ依頼者２お客様名")]
    public string AmRequester2CustomerName { get; set; } = string.Empty;  // ＡＭ依頼者２お客様名
    [Column("ＡＭ依頼者２電話番号")]
    public string AmRequester2PhoneNumber { get; set; } = string.Empty;  // ＡＭ依頼者２電話番号
    [Column("ＡＭ依頼者２ＦＡＸ")]
    public string AmRequester2Fax { get; set; } = string.Empty;  // ＡＭ依頼者２ＦＡＸ
    [Column("ＡＭ依頼者２メール")]
    public string AmRequester2Email { get; set; } = string.Empty;  // ＡＭ依頼者２メール
    [Column("ＡＭご依頼内容")]
    public string AmRequestDetails { get; set; } = string.Empty;  // ＡＭご依頼内容
    [Column("ＡＭ竣工ＯＲ入居")]
    public string AmCompletionOrOccupancy { get; set; } = string.Empty;  // ＡＭ竣工ＯＲ入居
    [Column("ＡＭ竣工日ＯＲ入居日")]
    public string AmCompletionOrOccupancyDate { get; set; } = string.Empty;  // ＡＭ竣工日ＯＲ入居日
    [MaxLength(1)]
    [Column("責任区分")]
    public string ResponsibilityCategory { get; set; } = string.Empty;  // 責任区分
    [Column("ＡＭ製品メーカー")]
    public string AmProductManufacturer { get; set; } = string.Empty;  // ＡＭ製品メーカー
    [Column("ＡＭ製品メーカーその他")]
    public string AmProductManufacturerOther { get; set; } = string.Empty;  // ＡＭ製品メーカーその他
    [Column("ＡＭ製品タイプ＿その他")]
    public string AmProductTypeOther { get; set; } = string.Empty;  // ＡＭ製品タイプ＿その他
    [Column("ＡＭ状況作業内容他")]
    public string AmStatusWorkDetailsOther { get; set; } = string.Empty;  // ＡＭ状況作業内容他
    [Column("ＡＭ必要部品１部品名")]
    public string AmRequiredPart1PartName { get; set; } = string.Empty;  // ＡＭ必要部品１部品名
    [Column("ＡＭ必要部品１数量")]
    public string AmRequiredPart1Quantity { get; set; } = string.Empty;  // ＡＭ必要部品１数量
    [Column("ＡＭ必要部品１手配日")]
    public string AmRequiredPart1ArrangementDate { get; set; } = string.Empty;  // ＡＭ必要部品１手配日
    [Column("ＡＭ必要部品１納入")]
    public string AmRequiredPart1Delivery { get; set; } = string.Empty;  // ＡＭ必要部品１納入
    [Column("ＡＭ必要部品２部品名")]
    public string AmRequiredPart2PartName { get; set; } = string.Empty;  // ＡＭ必要部品２部品名
    [Column("ＡＭ必要部品２数量")]
    public string AmRequiredPart2Quantity { get; set; } = string.Empty;  // ＡＭ必要部品２数量
    [Column("ＡＭ必要部品２手配日")]
    public string AmRequiredPart2ArrangementDate { get; set; } = string.Empty;  // ＡＭ必要部品２手配日
    [Column("ＡＭ必要部品２納入")]
    public string AmRequiredPart2Delivery { get; set; } = string.Empty;  // ＡＭ必要部品２納入
    [Column("ＡＭ必要部品３部品名")]
    public string AmRequiredPart3PartName { get; set; } = string.Empty;  // ＡＭ必要部品３部品名
    [Column("ＡＭ必要部品３数量")]
    public string AmRequiredPart3Quantity { get; set; } = string.Empty;  // ＡＭ必要部品３数量
    [Column("ＡＭ必要部品３手配日")]
    public string AmRequiredPart3ArrangementDate { get; set; } = string.Empty;  // ＡＭ必要部品３手配日
    [Column("ＡＭ必要部品３納入")]
    public string AmRequiredPart3Delivery { get; set; } = string.Empty;  // ＡＭ必要部品３納入
    [Column("ＡＭ必要部品４部品名")]
    public string AmRequiredPart4PartName { get; set; } = string.Empty;  // ＡＭ必要部品４部品名
    [Column("ＡＭ必要部品４数量")]
    public string AmRequiredPart4Quantity { get; set; } = string.Empty;  // ＡＭ必要部品４数量
    [Column("ＡＭ必要部品４手配日")]
    public string AmRequiredPart4ArrangementDate { get; set; } = string.Empty;  // ＡＭ必要部品４手配日
    [Column("ＡＭ必要部品４納入")]
    public string AmRequiredPart4Delivery { get; set; } = string.Empty;  // ＡＭ必要部品４納入
    [Column("ＡＭ依頼業者名")]
    public string AmRequestingCompany { get; set; } = string.Empty;  // ＡＭ依頼業者名
    [Column("ＡＭ作業指示開始日")]
    public string AmWorkInstructionStartDate { get; set; } = string.Empty;  // ＡＭ作業指示開始日
    [Column("ＡＭ作業指示開始時間")]
    public string AmWorkInstructionStartTime { get; set; } = string.Empty;  // ＡＭ作業指示開始時間
    [Column("ＡＭ作業指示終了日")]
    public string AmWorkInstructionEndDate { get; set; } = string.Empty;  // ＡＭ作業指示終了日
    [Column("ＡＭ作業指示終了時間")]
    public string AmWorkInstructionEndTime { get; set; } = string.Empty;  // ＡＭ作業指示終了時間
    [MaxLength(100)]
    [Column("請求先電話番号")]
    public string ClientPhoneNumber { get; set; } = string.Empty;  // 請求先電話番号
    [MaxLength(100)]
    [Column("請求先住所２")]
    public string ClientAddress2 { get; set; } = string.Empty;  // 請求先住所２
    [MaxLength(100)]
    [Column("請求先住所３")]
    public string ClientAddress3 { get; set; } = string.Empty;  // 請求先住所３
    [MaxLength(100)]
    [Column("請求先住所４")]
    public string ClientAddress4 { get; set; } = string.Empty;  // 請求先住所４
    [MaxLength(100)]
    [Column("請求先")]
    public string Client { get; set; } = string.Empty;  // 請求先
    [MaxLength(1)]
    [Column("敬称区分")]
    public string TitleCategory { get; set; } = string.Empty;  // 敬称区分
    [MaxLength(50)]
    [Column("敬称名")]
    public string TitleName { get; set; } = string.Empty;  // 敬称区分 = '2' THEN '様' ELSE '殿' END
    [MaxLength(100)]
    [Column("請求先担当者")]
    public string ClientContactPerson { get; set; } = string.Empty;  // 請求先担当者
    [Column("AM数量_場所")]
    public string AmQuantityLocation { get; set; } = string.Empty;  // AM数量_場所
    [Column("AM数量_場所_その他")]
    public string AmQuantityLocationOther { get; set; } = string.Empty;  // AM数量_場所_その他
    [Column("立会者の有無")]
    public string PresenceOfAttendee { get; set; } = string.Empty;  // 立会者の有無
    [Column("立会者名前")]
    public string AttendeeName { get; set; } = string.Empty;  // 立会者名前
    [Column("立会者電話番号")]
    public string AttendeePhoneNumber { get; set; } = string.Empty;  // 立会者電話番号
    [Column("工事写真の有無")]
    public string PresenceOfConstructionPhoto { get; set; } = string.Empty;  // 工事写真の有無
    [Column("不具合時場所")]
    public string LocationDuringDefect { get; set; } = string.Empty;  // 不具合時場所
    [MaxLength(26)]
    [Column("報告ＩＤ")]
    public string ReportId { get; set; } = string.Empty;  // 報告ＩＤ
    [MaxLength(100)]
    [Column("予備２１")]
    public string Spare21 { get; set; } = string.Empty;  // 予備２１
    [MaxLength(100)]
    [Column("予備２２")]
    public string Spare22 { get; set; } = string.Empty;  // 予備２２
    [MaxLength(100)]
    [Column("予備２３")]
    public string Spare23 { get; set; } = string.Empty;  // 予備２３
    [MaxLength(100)]
    [Column("予備２４")]
    public string Spare24 { get; set; } = string.Empty;  // 予備２４
    [Column("予備２５")]
    public string Spare25 { get; set; } = string.Empty;  // 予備２５
    [Column("予備２６")]
    public string Spare26 { get; set; } = string.Empty;  // 予備２６
    [Column("予備２７")]
    public string Spare27 { get; set; } = string.Empty;  // 予備２７
    [MaxLength(100)]
    [Column("勤務先TEL_編集画面")]
    public string WorkplaceTelEditScreen { get; set; } = string.Empty;  // 構造（木造・非木造）
    [Column("作業責任者_所属")]
    public string WorkResponsiblePersonDepartment { get; set; } = string.Empty;  // 予備０１
    [Column("作業責任者_名前")]
    public string WorkResponsiblePersonName { get; set; } = string.Empty;  // 予備０２
}
