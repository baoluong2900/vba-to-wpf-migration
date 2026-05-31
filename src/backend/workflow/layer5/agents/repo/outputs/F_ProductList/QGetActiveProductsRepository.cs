using System.Text;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

using vba_brain.Infrastructure.Persistence;
using Dapper;

namespace vba_brain.Infrastructure.Persistence.Repositories;

    /// <summary>
    /// Q_GetActiveProducts
    /// </summary>
    /// <returns></returns>
    public async Task<IEnumerable<QGetActiveProductsEntity>> GetActiveProductsAsync()
    {
        return await Task.FromResult(Enumerable.Empty<QGetActiveProductsEntity>());
    }
