using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

/// <summary>
/// T101_ID_PASS
/// </summary>
public class AuthRepository : IAuthRepository
{
    private readonly DapperContext _context;
    public AuthRepository(DapperContext context) => _context = context;

    /// <summary>
    /// T_ID_Pass
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<AuthEntity>> IdPassAsync()
    {
        return await Task.FromResult(Enumerable.Empty<AuthEntity>());
    }

    /// <summary>
    /// Q000_T_ID_PASS
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<AuthEntity>> QIdPassAsync()
    {
        return await Task.FromResult(Enumerable.Empty<AuthEntity>());
    }
}
