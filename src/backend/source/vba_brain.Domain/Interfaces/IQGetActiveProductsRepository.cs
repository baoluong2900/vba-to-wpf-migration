using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

    /// <summary>
    /// Q_GetActiveProducts
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<QGetActiveProductsEntity>> GetActiveProductsAsync();
}
