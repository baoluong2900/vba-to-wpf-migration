using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

    /// <summary>
    /// Access配信日
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<Access配信日Entity>> GetCommentAsync();
}
