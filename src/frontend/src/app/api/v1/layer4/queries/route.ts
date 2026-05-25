import { NextResponse } from 'next/server';
import { layer4Client, promisifyGrpcCall } from '../../../grpcClient';

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer4Client.ListMigrationQueries.bind(layer4Client),
      {}
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, queries: JSON.parse(response.queries_json || '[]') });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
