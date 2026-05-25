using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;
using vba_brain.Domain.DTOs;
using vba_brain.Domain.DTOs.BuildingAfterCollection;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// TBLビルアフター回収
/// </summary>
public class BuildingAfterCollectionRepository : IBuildingAfterCollectionRepository
{
    private readonly DapperContext _context;
    public BuildingAfterCollectionRepository(DapperContext context) => _context = context;

    /// <summary>
    /// Q005_アフターメンテナンス受付
    /// 指定された登録番号に一致するAM受付とアフター回収データを結合して取得するクエリ
    /// </summary>
    /// <param name="registrationNumberBf"></param>
    /// <param name="registrationNumberB"></param>
    /// <returns></returns>
    public async Task<IEnumerable<AfterMaintenanceReceptionDto>> AfterMaintenanceReceptionAsync(string registrationNumberBf, string registrationNumberB)
    {
        var sql = new StringBuilder();
        sql.AppendLine(@"SELECT t1.""登録番号"" ");
        sql.AppendLine(@", t1.""予備５"" AS ""QuickNo"" ");
        sql.AppendLine(@", t1.""受付日"" ");
        sql.AppendLine(@", t1.""担当者氏名"" ");
        sql.AppendLine(@", t2.""受付ＩＤ"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼先施工管理"" ");
        sql.AppendLine(@", t2.""ＡＭ受付時刻"" ");
        sql.AppendLine(@", t2.""ＡＭ受付所属課"" ");
        sql.AppendLine(@", t2.""ＡＭ訪問先携帯電話"" ");
        sql.AppendLine(@", t2.""ＡＭ訪問先メール"" ");
        sql.AppendLine(@", t2.""ＡＭ訪問先自宅電話番号"" ");
        sql.AppendLine(@", t2.""ＡＭ訪問先勤務先電話番号"" ");
        sql.AppendLine(@", t1.""工事名称"" ");
        sql.AppendLine(@", t1.""予備１３"" AS ""工事先建物名"" ");
        sql.AppendLine(@", t1.""予備１４"" AS ""訪問先お客様名"" ");
        sql.AppendLine(@", t1.""予備１５"" AS ""訪問先郵便番号"" ");
        sql.AppendLine(@", t1.""予備１６"" AS ""訪問先都道府県"" ");
        sql.AppendLine(@", t1.""予備１７"" AS ""訪問先市町村"" ");
        sql.AppendLine(@", t1.""予備１８"" AS ""訪問先町名番地"" ");
        sql.AppendLine(@", t1.""予備１９"" AS ""訪問先建物名"" ");
        sql.AppendLine(@", t1.""予備２０"" AS ""訪問先部屋番号"" ");
        sql.AppendLine(@", t2.""ＡＭ訪問先建物名"" AS ""店所用管理番号"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者１会社名"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者１お客様名"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者１電話番号"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者１ＦＡＸ"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者１メール"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者２会社名"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者２お客様名"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者２電話番号"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者２ＦＡＸ"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼者２メール"" ");
        sql.AppendLine(@", t2.""ＡＭご依頼内容"" ");
        sql.AppendLine(@", t2.""ＡＭ竣工ＯＲ入居"" ");
        sql.AppendLine(@", t2.""ＡＭ竣工日ＯＲ入居日"" ");
        sql.AppendLine(@", t1.""責任区分"" ");
        sql.AppendLine(@", t2.""ＡＭ製品メーカー"" ");
        sql.AppendLine(@", t2.""ＡＭ製品メーカーその他"" ");
        sql.AppendLine(@", t2.""ＡＭ製品タイプ＿その他"" ");
        sql.AppendLine(@", t2.""ＡＭ状況作業内容他"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品１部品名"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品１数量"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品１手配日"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品１納入"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品２部品名"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品２数量"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品２手配日"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品２納入"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品３部品名"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品３数量"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品３手配日"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品３納入"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品４部品名"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品４数量"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品４手配日"" ");
        sql.AppendLine(@", t2.""ＡＭ必要部品４納入"" ");
        sql.AppendLine(@", t2.""ＡＭ依頼業者名"" ");
        sql.AppendLine(@", t2.""ＡＭ作業指示開始日"" ");
        sql.AppendLine(@", t2.""ＡＭ作業指示開始時間"" ");
        sql.AppendLine(@", t2.""ＡＭ作業指示終了日"" ");
        sql.AppendLine(@", t2.""ＡＭ作業指示終了時間"" ");
        sql.AppendLine(@", t1.""請求先電話番号"" ");
        sql.AppendLine(@", t1.""請求先住所２"" ");
        sql.AppendLine(@", t1.""請求先住所３"" ");
        sql.AppendLine(@", t1.""請求先住所４"" ");
        sql.AppendLine(@", t1.""請求先"" ");
        sql.AppendLine(@", t1.""敬称区分"" ");
        sql.AppendLine(@", CASE WHEN t1.""敬称区分"" = '1' THEN '御中' WHEN t1.""敬称区分"" = '2' THEN '様' ELSE '殿' END AS ""敬称名"" ");
        sql.AppendLine(@", t1.""請求先担当者"" ");
        sql.AppendLine(@", t2.""AM数量_場所"" ");
        sql.AppendLine(@", t2.""AM数量_場所_その他"" ");
        sql.AppendLine(@", t2.""立会者の有無"" ");
        sql.AppendLine(@", t2.""立会者名前"" ");
        sql.AppendLine(@", t2.""立会者電話番号"" ");
        sql.AppendLine(@", t2.""工事写真の有無"" ");
        sql.AppendLine(@", t2.""不具合時場所"" ");
        sql.AppendLine(@", t1.""報告ＩＤ"" ");
        sql.AppendLine(@", t1.""予備２１"" ");
        sql.AppendLine(@", t1.""予備２２"" ");
        sql.AppendLine(@", t1.""予備２３"" ");
        sql.AppendLine(@", t1.""予備２４"" ");
        sql.AppendLine(@", t1.""予備２５"" ");
        sql.AppendLine(@", t1.""予備２６"" ");
        sql.AppendLine(@", t1.""予備２７"" ");
        sql.AppendLine(@", t1.""構造（木造・非木造）"" AS ""勤務先TEL_編集画面"" ");
        sql.AppendLine(@", t2.""予備０１"" AS ""作業責任者_所属"" ");
        sql.AppendLine(@", t2.""予備０２"" AS ""作業責任者_名前""");
        sql.AppendLine(@"FROM TBLビルアフター回収 t1");
        sql.AppendLine(@"INNER JOIN TBLビルＡＭ受付 t2 ON t2.""受付ＩＤ"" = t1.""受付ＩＤ""");
        sql.AppendLine(@"WHERE t1.""登録番号"" =:登録番号Bｆ");
        using var conn = _context.CreateConnection();
        return await conn.QueryAsync<AfterMaintenanceReceptionDto>(sql.ToString(), new { 登録番号Bｆ = registrationNumberBf, 登録番号B = registrationNumberB });
    }
}
