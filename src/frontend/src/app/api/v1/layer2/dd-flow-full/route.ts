import { NextRequest, NextResponse } from 'next/server';
import { layer2Client, promisifyGrpcCall } from '../../../grpcClient';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const screenName = body.screenName || body.screen_name;
    const model = body.model || body.target_model;
    const force = body.force !== undefined ? body.force : !(body.use_cache ?? true);

    if (!screenName) {
      return NextResponse.json({ success: false, error: "Missing screenName" }, { status: 400 });
    }

    const response = await promisifyGrpcCall<any, any>(
      layer2Client.RunDdFlowFull.bind(layer2Client),
      {
        screen_name: screenName,
        model: model || "",
        force: !!force,
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const result = JSON.parse(response.result_json || "{}");
    const paths = JSON.parse(response.paths_json || "{}");
    const tokenStats = JSON.parse(response.token_stats_json || "{}");
    const logFiles = JSON.parse(response.log_files_json || "[]");

    return NextResponse.json({
      success: true,
      result: JSON.stringify(result, null, 2),
      paths,
      token_stats: tokenStats,
      log_files: logFiles,
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
