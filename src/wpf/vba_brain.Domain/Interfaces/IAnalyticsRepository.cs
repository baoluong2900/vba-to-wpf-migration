using System.Collections.Generic;
using System.Threading.Tasks;
using vba_brain.Domain.Entities;

namespace vba_brain.Domain.Interfaces;

public interface IAnalyticsRepository
{
    Task<IEnumerable<AnalyticsEntity>> GetAggregatedDataAsync(string startPeriod, string endPeriod);
}
