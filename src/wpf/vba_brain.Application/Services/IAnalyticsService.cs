using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Domain.Entities;

namespace vba_brain.Application.Services;

public interface IAnalyticsService
{
    Task<IEnumerable<AnalyticsEntity>> GetAggregatedDataAsync(string startPeriod, string endPeriod);
}
