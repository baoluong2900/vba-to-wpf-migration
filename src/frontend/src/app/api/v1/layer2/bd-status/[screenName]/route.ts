import { NextRequest, NextResponse } from 'next/server';
import { layer2Client, promisifyGrpcCall } from '../../../../grpcClient';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ screenName: string }> }
) {
  try {
    const resolvedParams = await params;
    const screenName = resolvedParams.screenName;
    const response = await promisifyGrpcCall<any, any>(
      layer2Client.GetBdStatus.bind(layer2Client),
      { screen_name: screenName }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      status: response.status,
      result_json: response.result_json,
      token_stats: response.token_stats,
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
