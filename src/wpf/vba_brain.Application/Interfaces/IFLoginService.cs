using System.Threading.Tasks;
using vba_brain.Application.DTOs.Requests.F_Login;
using vba_brain.Application.DTOs.Responses.F_Login;
namespace vba_brain.Application.Interfaces;
public interface IFLoginService
{
    Task<F000Response> F000Async(F000Request request);
    Task<F001Response> F001Async(F001Request request);
    Task<F003Response> F003Async(F003Request request);
}
