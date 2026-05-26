import { NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer3Client.ListOutputs.bind(layer3Client),
      {}
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const files = response.result.map((f: string) => JSON.parse(f));
    return NextResponse.json({ success: true, files });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
