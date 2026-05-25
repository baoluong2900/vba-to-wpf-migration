using System;
using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;
using Dapper;
using vba_brain.Domain.Common;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Infrastructure.Persistence.Repositories;

public class PaymentRepository : IPaymentRepository
{
    private readonly IDbConnectionFactory _connectionFactory;

    public PaymentRepository(IDbConnectionFactory connectionFactory)
    {
        _connectionFactory = connectionFactory;
    }

    private string PrepareSql(string sql)
    {
        if (_connectionFactory.DbType == DatabaseType.Oracle)
        {
            return sql.Replace("@", ":");
        }
        return sql;
    }

    public async Task<IEnumerable<PaymentEntity>> GetBySeqNoAsync(long seqNo)
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql("SELECT * FROM T002_PAYMENT WHERE SEQ_NO = @SeqNo ORDER BY PAYMENT_DT DESC");
        return await conn.QueryAsync<PaymentEntity>(sql, new { SeqNo = seqNo });
    }

    public async Task<long> InsertAsync(PaymentEntity entity)
    {
        using var conn = _connectionFactory.CreateConnection();
        string sql;
        if (_connectionFactory.DbType == DatabaseType.PostgreSQL)
        {
            sql = "INSERT INTO T002_PAYMENT (SEQ_NO, AMOUNT, PAYMENT_DT, NOTE, CREATED_AT, CREATED_BY) " +
                  "VALUES (@SeqNo, @Amount, @PaymentDt, @Note, @CreatedAt, @CreatedBy) RETURNING PAYMENT_ID";
            return await conn.ExecuteScalarAsync<long>(sql, entity);
        }
        else if (_connectionFactory.DbType == DatabaseType.Oracle)
        {
            sql = "INSERT INTO T002_PAYMENT (SEQ_NO, AMOUNT, PAYMENT_DT, NOTE, CREATED_AT, CREATED_BY) " +
                  "VALUES (:SeqNo, :Amount, :PaymentDt, :Note, :CreatedAt, :CreatedBy) RETURNING PAYMENT_ID INTO :PaymentId";
            
            var parameters = new DynamicParameters(entity);
            parameters.Add("PaymentId", dbType: DbType.Int64, direction: ParameterDirection.Output);
            await conn.ExecuteAsync(sql, parameters);
            return parameters.Get<long>("PaymentId");
        }
        else // SQL Server
        {
            sql = "INSERT INTO T002_PAYMENT (SEQ_NO, AMOUNT, PAYMENT_DT, NOTE, CREATED_AT, CREATED_BY) " +
                  "VALUES (@SeqNo, @Amount, @PaymentDt, @Note, @CreatedAt, @CreatedBy); SELECT SCOPE_IDENTITY();";
            return await conn.ExecuteScalarAsync<long>(sql, entity);
        }
    }
}
