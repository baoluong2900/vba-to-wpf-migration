import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const sql = body.target_sql || '';
    
    // Basic mock validation rules
    if (!sql.trim()) {
      return NextResponse.json({
        success: false,
        error_code: 'ORA-00900',
        error_message: 'Invalid SQL statement'
      });
    }

    // Unclosed quote check
    if ((sql.match(/'/g) || []).length % 2 !== 0) {
      return NextResponse.json({
        success: false,
        error_code: 'ORA-01756',
        error_message: 'Quoted string not properly terminated'
      });
    }

    // Access functions validation
    const upperSql = sql.toUpperCase();
    if (upperSql.includes('DLOOKUP') || upperSql.includes('IIF') || upperSql.includes('NZ(')) {
      return NextResponse.json({
        success: false,
        error_code: 'ORA-00904',
        error_message: 'Access dialect function (DLookup/IIf/Nz) is invalid in target SQL. Please translate to PostgreSQL equivalents (e.g. COALESCE, CASE WHEN).'
      });
    }

    // Extract columns using regex
    let columns = ['ID', 'NAME', 'UPDATED_AT'];
    const selectMatch = sql.match(/SELECT\s+(.+?)\s+FROM/i);
    if (selectMatch) {
      const colsStr = selectMatch[1];
      const parsedCols = colsStr.split(',').map(c => {
        const aliasMatch = c.match(/as\s+(\w+)/i) || c.match(/\.(\w+)/) || [null, c.trim()];
        return (aliasMatch[1] || c.trim()).toUpperCase().replace(/['"`]/g, '');
      }).filter(c => c && !c.includes('*'));
      if (parsedCols.length > 0) {
        columns = parsedCols;
      }
    }

    // Generate sample rows
    const rows = [
      columns.map((c, i) => i === 0 ? 101 : c === 'NAME' ? 'Sample Data A' : '2026-05-26'),
      columns.map((c, i) => i === 0 ? 102 : c === 'NAME' ? 'Sample Data B' : '2026-05-26')
    ];

    return NextResponse.json({
      success: true,
      message: 'Query executed successfully (Mock database check passed).',
      columns,
      rows,
      rowcount: rows.length
    });
  } catch (error: any) {
    return NextResponse.json({
      success: false,
      error_code: 'ORA-00600',
      error_message: error.message
    });
  }
}
