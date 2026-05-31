namespace vba_brain.Application.Interfaces;

using vba_brain.Application.DTOs.Requests.F_Login;
using vba_brain.Application.DTOs.Responses.F_Login;

/// <summary>
/// Application service for F_Login.
/// </summary>
public interface IFLoginService
{
    /// <summary>F000 On Open — Prepares the user interface for a clean and focused login experience.</summary>
    Task<F000Response> F000Async(F000Request request);

    /// <summary>F001 On Load — Checks if the current version is up-to-date and prompts for an update if necessary.</summary>
    Task<F001Response> F001Async(F001Request request);

    /// <summary>F003 After Update — Verifies user credentials and grants access to the system if valid.</summary>
    Task<F003Response> F003Async(F003Request request);

    /// <summary>F009 On Double Click — Closes multiple forms, sets up the user interface, and opens a specific query for viewing.</summary>
    Task<F009Response> F009Async(F009Request request);

}
