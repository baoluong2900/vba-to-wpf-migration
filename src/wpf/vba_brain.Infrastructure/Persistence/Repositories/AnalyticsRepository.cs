using System;
using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;
using Dapper;
using vba_brain.Domain.Common;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Infrastructure.Persistence.Repositories;

public class AnalyticsRepository : IAnalyticsRepository
{
    private readonly IDbConnectionFactory _connectionFactory;

    public AnalyticsRepository(IDbConnectionFactory connectionFactory)
    {
        _connectionFactory = connectionFactory;
    }

    public async Task<IEnumerable<AnalyticsEntity>> GetAggregatedDataAsync(string startPeriod, string endPeriod)
    {
        using var conn = _connectionFactory.CreateConnection();
        string sql;
        string dateConversion;

        if (_connectionFactory.DbType == DatabaseType.PostgreSQL || _connectionFactory.DbType == DatabaseType.Oracle)
        {
            dateConversion = "TO_CHAR(RECEIVE_DT, 'YYYY-MM')";
        }
        else // SqlServer
        {
            dateConversion = "CONVERT(VARCHAR(7), RECEIVE_DT, 120)";
        }

        string paramPrefix = _connectionFactory.DbType == DatabaseType.Oracle ? ":" : "@";

        sql = $@"
            SELECT 
                {dateConversion} AS Period,
                CAST(SERVICE_TYPE AS VARCHAR(50)) AS Category,
                SUM(PAYMENT_AMT) AS TotalAmount,
                COUNT(*) AS Count
            FROM T001_AFTER_MAIN
            WHERE RECEIVE_DT IS NOT NULL
            GROUP BY {dateConversion}, SERVICE_TYPE
            HAVING {dateConversion} >= {paramPrefix}StartPeriod AND {dateConversion} <= {paramPrefix}EndPeriod
            ORDER BY Period DESC, Category ASC";

        var parameters = new DynamicParameters();
        parameters.Add("StartPeriod", startPeriod);
        parameters.Add("EndPeriod", endPeriod);

        return await conn.QueryAsync<AnalyticsEntity>(sql, parameters);
    }
}
