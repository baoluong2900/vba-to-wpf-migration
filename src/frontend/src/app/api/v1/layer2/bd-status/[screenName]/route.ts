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
      screen_name: response.screen_name,
      bd_done: response.bd_done,
      dd_done: response.dd_done,
      s4_path: response.s4_path || null,
      d4_path: response.d4_path || null,
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
