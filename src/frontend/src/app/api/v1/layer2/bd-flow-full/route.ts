import { NextRequest, NextResponse } from 'next/server';
import { layer2Client, promisifyGrpcCall } from '../../../grpcClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await promisifyGrpcCall<any, any>(
      layer2Client.RunBdFlowFull.bind(layer2Client),
      {
        screen_name: body.screen_name,
        target_model: body.target_model,
        fast_mode: body.fast_mode || false,
        use_cache: body.use_cache || true,
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      result_json: response.result_json,
      token_stats: response.token_stats,
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
