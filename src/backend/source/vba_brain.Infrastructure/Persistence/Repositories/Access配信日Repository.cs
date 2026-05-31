using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// Access配信日
/// </summary>
public class Access配信日Repository : IAccess配信日Repository
{
    private readonly DapperContext _context;
    public Access配信日Repository(DapperContext context) => _context = context;

    /// <summary>
    /// Access配信日
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<Access配信日Entity>> GetCommentAsync()
    {
        return await Task.FromResult(Enumerable.Empty<Access配信日Entity>());
    }
}
