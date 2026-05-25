using System;
using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;
using Dapper;
using vba_brain.Domain.Common;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Infrastructure.Persistence.Repositories;

public class PrintRepository : IPrintRepository
{
    private readonly IDbConnectionFactory _connectionFactory;

    public PrintRepository(IDbConnectionFactory connectionFactory)
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

    public async Task<IEnumerable<PrintDocumentEntity>> GetHistoryBySeqNoAsync(long seqNo)
    {
        using var conn = _connectionFactory.CreateConnection();
        var sql = PrepareSql("SELECT * FROM T003_PRINT_HISTORY WHERE SEQ_NO = @SeqNo ORDER BY PRINTED_AT DESC");
        return await conn.QueryAsync<PrintDocumentEntity>(sql, new { SeqNo = seqNo });
    }

    public async Task<long> InsertLogAsync(PrintDocumentEntity entity)
    {
        using var conn = _connectionFactory.CreateConnection();
        string sql;
        if (_connectionFactory.DbType == DatabaseType.PostgreSQL)
        {
            sql = "INSERT INTO T003_PRINT_HISTORY (SEQ_NO, DOC_TYPE, PRINTED_AT, OPERATOR_NAME, CREATED_AT, CREATED_BY) " +
                  "VALUES (@SeqNo, @DocType, @PrintedAt, @OperatorName, @CreatedAt, @CreatedBy) RETURNING PRINT_ID";
            return await conn.ExecuteScalarAsync<long>(sql, entity);
        }
        else if (_connectionFactory.DbType == DatabaseType.Oracle)
        {
            sql = "INSERT INTO T003_PRINT_HISTORY (SEQ_NO, DOC_TYPE, PRINTED_AT, OPERATOR_NAME, CREATED_AT, CREATED_BY) " +
                  "VALUES (:SeqNo, :DocType, :PrintedAt, :OperatorName, :CreatedAt, :CreatedBy) RETURNING PRINT_ID INTO :PrintId";
            
            var parameters = new DynamicParameters(entity);
            parameters.Add("PrintId", dbType: DbType.Int64, direction: ParameterDirection.Output);
            await conn.ExecuteAsync(sql, parameters);
            return parameters.Get<long>("PrintId");
        }
        else // SQL Server
        {
            sql = "INSERT INTO T003_PRINT_HISTORY (SEQ_NO, DOC_TYPE, PRINTED_AT, OPERATOR_NAME, CREATED_AT, CREATED_BY) " +
                  "VALUES (@SeqNo, @DocType, @PrintedAt, @OperatorName, @CreatedAt, @CreatedBy); SELECT SCOPE_IDENTITY();";
            return await conn.ExecuteScalarAsync<long>(sql, entity);
        }
    }
}
