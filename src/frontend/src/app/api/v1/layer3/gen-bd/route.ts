import { NextRequest, NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { screenName, type } = body;
    const sName = screenName || body.item_name || body.screen_name;

    if (!sName) {
      return NextResponse.json({ success: false, error: "Missing screenName" }, { status: 400 });
    }

    const response = await promisifyGrpcCall<any, any>(
      layer3Client.GenBd.bind(layer3Client),
      {
        screen_name: sName,
        type: type || "auto",
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const result = JSON.parse(response.result_json);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
