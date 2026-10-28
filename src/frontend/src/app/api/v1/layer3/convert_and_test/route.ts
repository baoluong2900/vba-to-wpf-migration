import { NextRequest, NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';
import { staticSqlCheck } from '../staticSqlCheck';

// Convert with the LLM, then run the static check on the result. There is no automatic
// LLM fix loop yet, so test_history always holds a single attempt and fix_notes stays empty.
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await promisifyGrpcCall<any, any>(
      layer3Client.ConvertQuery.bind(layer3Client),
      // An empty model lets the gateway use llm_settings.layer3_migration_model.
      { name: body.name, model: body.model || '' }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const result = JSON.parse(response.query_json || '{}');
    const lastTest = staticSqlCheck(result.target_sql || '');

    return NextResponse.json({
      success: true,
      result,
      last_test: lastTest,
      test_history: [{ attempt: 1, success: lastTest.success, error_message: lastTest.error_message || '' }],
      fix_notes: [],
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
