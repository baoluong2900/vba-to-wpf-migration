import { NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../grpcClient';

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer3Client.ListMigrationTables.bind(layer3Client),
      {}
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, tables: JSON.parse(response.tables_json || '[]') });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
