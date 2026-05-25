import { NextRequest, NextResponse } from 'next/server';
import { layer4Client, promisifyGrpcCall } from '../../../grpcClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await promisifyGrpcCall<any, any>(
      layer4Client.ConvertQuery.bind(layer4Client),
      {
        name: body.name,
        model: body.model || "qwen-max",
        fast_mode: body.fast_mode || false,
        use_cache: body.use_cache || true
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, query: JSON.parse(response.query_json || '{}') });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
