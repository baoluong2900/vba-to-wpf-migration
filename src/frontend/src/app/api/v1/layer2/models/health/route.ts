import { NextResponse } from 'next/server';
import { layer2Client, promisifyGrpcCall } from '../../../../grpcClient';

export async function GET() {
  try {
    const response = await promisifyGrpcCall<any, any>(
      layer2Client.GetModelsHealth.bind(layer2Client),
      {}
    );

        if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const results = JSON.parse(response.results_json);
    return NextResponse.json({ success: true, results });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
