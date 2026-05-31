using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

/// <summary>
/// T101_ID_PASS
/// </summary>
public interface IAuthRepository
{

    /// <summary>
    /// Q000_T_ID_PASS
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<AuthEntity>> QIdPassAsync();


    /// <summary>
    /// T_ID_Pass
    /// </summary>
    /// <returns></returns>
    Task<IEnumerable<AuthEntity>> IdPassAsync();
}
