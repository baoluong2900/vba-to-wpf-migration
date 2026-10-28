import { NextRequest, NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';

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

    return NextResponse.json({ success: true, result: JSON.parse(response.query_json || '{}') });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
