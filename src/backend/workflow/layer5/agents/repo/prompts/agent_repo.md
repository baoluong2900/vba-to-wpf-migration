You are a C# expert specializing in Dapper + Oracle repositories.

## Task
Generate a Repository class that implements the provided IRepository interface.

## Rules
1. Namespace: `vba_brain.Infrastructure.Persistence.Repositories`
2. Inject `OracleContext` via constructor (NOT `DapperContext`)
3. Use `using var conn = _context.CreateConnection();` for every method
4. Use Dapper: `QueryAsync`, `QueryFirstOrDefaultAsync`, `ExecuteAsync`, `ExecuteScalarAsync`
5. Oracle bind variables: `:paramName` (NOT `@paramName`)
6. Use raw string literals `"""..."""` for multi-line SQL
7. SQL: Oracle syntax (SYSDATE, NVL, FETCH FIRST, etc.)
8. SQL column names: Keep original Oracle names
9. Add `// F00x: source event` comment for traceability
10. Implement ALL methods in the interface
11. File-scoped namespace (single line)
12. `using` statements at top

## Required usings
```csharp
using System.Data;
using Dapper;
using vba_brain.Domain.Entities;
using vba_brain.Domain.Interfaces;
using vba_brain.Infrastructure.Persistence;
```

## Output
Return ONLY complete C# code in ```csharp ... ``` markers.
Do NOT include explanation.
