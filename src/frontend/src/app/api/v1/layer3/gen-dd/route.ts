import { NextRequest, NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await promisifyGrpcCall<any, any>(
      layer3Client.GenDd.bind(layer3Client),
      {
        item_name: body.item_name,
        force: body.force || false,
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      file_info: response.file_info,
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
