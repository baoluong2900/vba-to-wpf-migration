using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

    /// <summary>
    /// Q000_T_LoginUser
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<Q000TLoginUserEntity>> GetUserInfoAsync()
    {
        return await Task.FromResult(Enumerable.Empty<Q000TLoginUserEntity>());
    }
