namespace vba_brain.Application.Interfaces;

using vba_brain.Application.DTOs.Requests.F_ProductList;
using vba_brain.Application.DTOs.Responses.F_ProductList;

/// <summary>
/// Application service for F_ProductList.
/// </summary>
public interface IProductListService
{
    /// <summary>F000 On Open — 画面の初期表示の処理</summary>
    Task<F000Response> OnF000Async(F000Request request);

}
