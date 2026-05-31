namespace vba_brain.Application.Interfaces;

using vba_brain.Application.DTOs.Requests.F_ProductDetail;
using vba_brain.Application.DTOs.Responses.F_ProductDetail;

/// <summary>
/// Application service for F_ProductDetail.
/// </summary>
public interface IProductDetailService
{
    /// <summary>F000 On Open — 画面の初期表示の処理</summary>
    Task<F000Response> OnF000Async(F000Request request);

}
