import { NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer3Client.GetStats.bind(layer3Client),
      {}
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      stats: {
        total: response.total_queries,
        pending: response.pending,
        converted: response.converted,
        error: response.error_count
      }
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
