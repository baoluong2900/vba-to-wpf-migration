using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;

namespace vba_brain.Application.Services;

public class AnalyticsService : IAnalyticsService
{
    private readonly IAnalyticsRepository _repository;

    public AnalyticsService(IAnalyticsRepository repository)
    {
        _repository = repository;
    }

    public async Task<IEnumerable<AnalyticsEntity>> GetAggregatedDataAsync(string startPeriod, string endPeriod)
    {
        return await _repository.GetAggregatedDataAsync(startPeriod, endPeriod);
    }
}
