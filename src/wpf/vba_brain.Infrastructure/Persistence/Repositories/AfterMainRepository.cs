using System;
using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;
using Dapper;
using vba_brain.Domain.Common;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Infrastructure.Persistence.Repositories;

public class AfterMainRepository : IAfterMainRepository
{
    private readonly IDbConnectionFactory _connectionFactory;

    public AfterMainRepository(IDbConnectionFactory connectionFactory)
    {
        _connectionFactory = connectionFactory;
    }

    private string PrepareSql(string sql)
    {
        if (_connectionFactory.DbType == DatabaseType.Oracle)
        {
            // Simple replace of parameter prefix from @ to : for Oracle
            return sql.Replace("@", ":");
        }
        return sql;
    }

    public async Task<AfterMainEntity?> GetBySeqNoAsync(long seqNo)
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql("SELECT * FROM T001_AFTER_MAIN WHERE SEQ_NO = @SeqNo");
        return await conn.QueryFirstOrDefaultAsync<AfterMainEntity>(sql, new { SeqNo = seqNo });
    }

    public async Task<IEnumerable<AfterMainEntity>> GetAllAsync()
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql("SELECT * FROM T001_AFTER_MAIN ORDER BY RECEIVE_DT DESC");
        return await conn.QueryAsync<AfterMainEntity>(sql);
    }

    public async Task<IEnumerable<AfterMainEntity>> GetByDistrictAsync(string districtCd)
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql("SELECT * FROM T001_AFTER_MAIN WHERE DISTRICT_CD = @DistrictCd ORDER BY RECEIVE_DT DESC");
        return await conn.QueryAsync<AfterMainEntity>(sql, new { DistrictCd = districtCd });
    }

    public async Task<long> InsertAsync(AfterMainEntity entity)
    {
        using var conn = _connectionFactory.CreateConnection();
        string sql;
        if (_connectionFactory.DbType == DatabaseType.PostgreSQL)
        {
            sql = "INSERT INTO T001_AFTER_MAIN (AFTER_CD, CUSTOMER_NM, SERVICE_TYPE, PAYMENT_AMT, PAYMENT_FLG, DISTRICT_CD, RECEIVE_DT, CREATED_AT, CREATED_BY) " +
                  "VALUES (@AfterCd, @CustomerNm, @ServiceType, @PaymentAmt, @PaymentFlg, @DistrictCd, @ReceiveDt, @CreatedAt, @CreatedBy) RETURNING SEQ_NO";
            return await conn.ExecuteScalarAsync<long>(sql, entity);
        }
        else if (_connectionFactory.DbType == DatabaseType.Oracle)
        {
            // Oracle uses sequence or RETURNING INTO
            sql = "INSERT INTO T001_AFTER_MAIN (AFTER_CD, CUSTOMER_NM, SERVICE_TYPE, PAYMENT_AMT, PAYMENT_FLG, DISTRICT_CD, RECEIVE_DT, CREATED_AT, CREATED_BY) " +
                  "VALUES (:AfterCd, :CustomerNm, :ServiceType, :PaymentAmt, :PaymentFlg, :DistrictCd, :ReceiveDt, :CreatedAt, :CreatedBy) RETURNING SEQ_NO INTO :SeqNo";
            
            var parameters = new DynamicParameters(entity);
            parameters.Add("SeqNo", dbType: DbType.Int64, direction: ParameterDirection.Output);
            await conn.ExecuteAsync(sql, parameters);
            return parameters.Get<long>("SeqNo");
        }
        else // SQL Server
        {
            sql = "INSERT INTO T001_AFTER_MAIN (AFTER_CD, CUSTOMER_NM, SERVICE_TYPE, PAYMENT_AMT, PAYMENT_FLG, DISTRICT_CD, RECEIVE_DT, CREATED_AT, CREATED_BY) " +
                  "VALUES (@AfterCd, @CustomerNm, @ServiceType, @PaymentAmt, @PaymentFlg, @DistrictCd, @ReceiveDt, @CreatedAt, @CreatedBy); SELECT SCOPE_IDENTITY();";
            return await conn.ExecuteScalarAsync<long>(sql, entity);
        }
    }

    public async Task<bool> UpdateAsync(AfterMainEntity entity)
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql(
            "UPDATE T001_AFTER_MAIN SET AFTER_CD = @AfterCd, CUSTOMER_NM = @CustomerNm, SERVICE_TYPE = @ServiceType, " +
            "PAYMENT_AMT = @PaymentAmt, PAYMENT_FLG = @PaymentFlg, DISTRICT_CD = @DistrictCd, RECEIVE_DT = @ReceiveDt, " +
            "UPDATED_AT = @UpdatedAt, UPDATED_BY = @UpdatedBy WHERE SEQ_NO = @SeqNo"
        );
        entity.UpdatedAt = DateTime.UtcNow;
        entity.UpdatedBy = "System";
        var rows = await conn.ExecuteAsync(sql, entity);
        return rows > 0;
    }

    public async Task<bool> DeleteAsync(long seqNo)
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql("DELETE FROM T001_AFTER_MAIN WHERE SEQ_NO = @SeqNo");
        var rows = await conn.ExecuteAsync(sql, new { SeqNo = seqNo });
        return rows > 0;
    }
}
