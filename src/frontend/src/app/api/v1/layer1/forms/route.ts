import { NextResponse } from 'next/server';
import { layer1Client, promisifyGrpcCall } from '../../../grpcClient';

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer1Client.ListForms.bind(layer1Client),
      {}
    );

    if (!response.success) {
      return NextResponse.json(
        { success: false, error: response.error },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, result: response.result });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: `gRPC Gateway Exception: ${error.message}` },
      { status: 500 }
    );
  }
}
