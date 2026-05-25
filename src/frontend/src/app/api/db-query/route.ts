import { NextResponse } from 'next/server';
import { layer1Client, promisifyGrpcCall } from '../grpcClient';

export async function POST(req: Request) {
  try {
    let body: any;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json({ success: false, error: 'Invalid JSON body' }, { status: 400 });
    }

    const { screenName, itemType, deep } = body;

    if (!screenName) {
      return NextResponse.json({ success: false, error: 'Missing screenName' }, { status: 400 });
    }

    const response = await promisifyGrpcCall<any, any>(
      layer1Client.GetDbQuery.bind(layer1Client),
      {
        screen_name: screenName,
        item_type: itemType || 'auto',
        deep: !!deep,
      }
    );

    if (!response.success) {
      return NextResponse.json(
        { success: false, error: response.error },
        { status: 500 }
      );
    }

    const result = JSON.parse(response.result_json);
    return NextResponse.json({ success: true, result });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: `gRPC Connection Exception: ${error.message}` },
      { status: 500 }
    );
  }
}
