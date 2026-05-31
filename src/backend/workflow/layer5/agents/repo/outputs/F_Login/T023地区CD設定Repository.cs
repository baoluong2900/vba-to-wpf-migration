using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// T023_地区CD設定
/// </summary>
public class T023地区CD設定Repository : IT023地区CD設定Repository
{
    private readonly DapperContext _context;
    public T023地区CD設定Repository(DapperContext context) => _context = context;

    /// <summary>
    /// T023_地区CD設定
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<T023地区CD設定Entity>> SetAreaCdAsync()
    {
        return await Task.FromResult(Enumerable.Empty<T023地区CD設定Entity>());
    }
}
