namespace vba_brain.Application.Interfaces;

using vba_brain.Application.DTOs.Requests;
using vba_brain.Application.DTOs.Responses;

/// <summary>
/// Application service for R005_作業依頼書サブ.
/// </summary>
public interface IR005WorkRequestSubService
{
    /// <summary>R005_作業依頼書サブ 画面を開く時 — 画面の初期表示の処理</summary>
    Task<R005WorkRequestSubResponse> GetInitialDataAsync(R005WorkRequestSubRequest request);

}
