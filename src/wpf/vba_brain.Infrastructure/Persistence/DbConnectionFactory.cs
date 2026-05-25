using System;
using System.Data;
using Microsoft.Data.SqlClient;
using Npgsql;
using Oracle.ManagedDataAccess.Client;
using vba_brain.Domain.Common;

namespace vba_brain.Infrastructure.Persistence;

public interface IDbConnectionFactory
{
    IDbConnection CreateConnection();
    DatabaseType DbType { get; }
}

public class DbConnectionFactory : IDbConnectionFactory
{
    private readonly string _connectionString;
    public DatabaseType DbType { get; }

    public DbConnectionFactory(string connectionString, DatabaseType dbType)
    {
        _connectionString = connectionString;
        DbType = dbType;
    }

    public IDbConnection CreateConnection()
    {
        return DbType switch
        {
            DatabaseType.PostgreSQL => new NpgsqlConnection(_connectionString),
            DatabaseType.Oracle => new OracleConnection(_connectionString),
            DatabaseType.SqlServer => new SqlConnection(_connectionString),
            _ => throw new NotSupportedException($"Database type {DbType} is not supported.")
        };
    }
}
