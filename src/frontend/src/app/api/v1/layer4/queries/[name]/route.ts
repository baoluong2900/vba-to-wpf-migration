import { NextRequest, NextResponse } from 'next/server';
import { layer4Client, promisifyGrpcCall } from '../../../../grpcClient';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const resolvedParams = await params;
    const response = await promisifyGrpcCall<any, any>(
      layer4Client.GetMigrationQuery.bind(layer4Client),
      { name: resolvedParams.name }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, query: JSON.parse(response.query_json || '{}') });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const body = await request.json();
    const resolvedParams = await params;
    const response = await promisifyGrpcCall<any, any>(
      layer4Client.UpdateMigrationQuery.bind(layer4Client),
      {
        name: resolvedParams.name,
        target_sql: body.target_sql || "",
        target_query_json: body.target_query_json ? JSON.stringify(body.target_query_json) : "",
        notes: body.notes || "",
        status: body.status || "",
        reviewer: body.reviewer || "",
        description: body.description || "",
        model: body.model || ""
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, query: JSON.parse(response.query_json || '{}') });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
