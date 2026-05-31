using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

    /// <summary>
    /// Q000_T_LoginUser
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<Q000TLoginUserEntity>> GetUserInfoAsync();
}
