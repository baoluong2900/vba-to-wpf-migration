import { NextResponse } from 'next/server';
import { layer4Client, promisifyGrpcCall } from '../../../grpcClient';

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer4Client.ListItems.bind(layer4Client),
      {}
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const result = response.result.map((item: string) => JSON.parse(item));
    return NextResponse.json({ success: true, result, total: result.length });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
