import { NextRequest, NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../../grpcClient';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { table_name, target_db } = body;

    if (!table_name || !target_db) {
      return NextResponse.json({ success: false, error: "Missing table_name or target_db" }, { status: 400 });
    }

    const response = await promisifyGrpcCall<any, any>(
      layer3Client.ConvertTableSchema.bind(layer3Client),
      { table_name, target_db }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, ddl: response.ddl });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
