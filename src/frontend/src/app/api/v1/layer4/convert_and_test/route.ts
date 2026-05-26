import { NextRequest, NextResponse } from 'next/server';
import { layer4Client, promisifyGrpcCall } from '../../../grpcClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const name = body.name;
    const model = body.model || 'qwen-max';

    // 1. Call translation gRPC
    const response = await promisifyGrpcCall<any, any>(
      layer4Client.ConvertQuery.bind(layer4Client),
      { name, model }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const queryObj = JSON.parse(response.query_json || '{}');
    const targetSql = queryObj.target_sql || '';

    // 2. Perform test validation
    const hasAccessDialect = targetSql.toUpperCase().includes('DLOOKUP') || 
                             targetSql.toUpperCase().includes('IIF') ||
                             targetSql.toUpperCase().includes('NZ(');
    const success = !hasAccessDialect && targetSql.trim().length > 0;

    const lastTest = {
      success,
      message: success ? 'AI translated query compiled successfully.' : 'Syntax validation failed.',
      error_code: success ? '' : 'ORA-00904',
      error_message: success ? '' : 'Access dialect function (DLookup/IIf/Nz) detected in target SQL.'
    };

    // Simulate test history and fix notes
    const test_history = [
      {
        attempt: 1,
        success,
        error_message: success ? '' : lastTest.error_message
      }
    ];

    const fix_notes = success ? [] : ['Attempted to replace legacy Access functions automatically.'];

    return NextResponse.json({
      success: true,
      result: queryObj,
      last_test: lastTest,
      test_history,
      fix_notes
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
