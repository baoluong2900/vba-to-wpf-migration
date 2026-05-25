import { NextResponse } from "next/server";
import { layer3Client, promisifyGrpcCall } from "../../grpcClient";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { screenName, type } = body;

    if (!screenName) {
      return NextResponse.json({ success: false, error: "Missing screenName" }, { status: 400 });
    }

    const response = await promisifyGrpcCall<any, any>(
      layer3Client.GenDd.bind(layer3Client),
      {
        screen_name: screenName,
        type: type || "auto",
      }
    );

    if (!response.success) {
      return NextResponse.json(
        { success: false, error: response.error },
        { status: 500 }
      );
    }

    const result = JSON.parse(response.result_json);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
