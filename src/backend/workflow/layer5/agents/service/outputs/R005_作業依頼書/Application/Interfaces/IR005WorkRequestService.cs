namespace vba_brain.Application.Interfaces;

using vba_brain.Application.DTOs.Requests;
using vba_brain.Application.DTOs.Responses;

/// <summary>
/// Application service for R005_作業依頼書.
/// </summary>
public interface IR005WorkRequestService
{
    /// <summary>R005_作業依頼書 画面を開く時 — 画面の初期表示の処理</summary>
    Task<R005WorkRequestResponse> GetInitialDataAsync(R005WorkRequestRequest request);

}
