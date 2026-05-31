using System.Data;

namespace vba_brain.Infrastructure.Persistence;

/// <summary>
/// Thin wrapper around IDbConnectionFactory for Dapper-based repositories.
/// </summary>
public class DapperContext
{
    private readonly IDbConnectionFactory _factory;

    public DapperContext(IDbConnectionFactory factory)
    {
        _factory = factory;
    }

    public IDbConnection CreateConnection() => _factory.CreateConnection();
}
