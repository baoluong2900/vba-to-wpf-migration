import { NextRequest, NextResponse } from "next/server";
import { layer3Client, promisifyGrpcCall } from "../../../grpcClient";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { path: pathSegments } = await params;
    if (!pathSegments || pathSegments.length < 3) {
      return NextResponse.json(
        { success: false, error: "Expected path: /download/{doc_kind}/{doc_type}/{filename}" },
        { status: 400 }
      );
    }

    const doc_kind = pathSegments[0];
    const doc_type = pathSegments[1];
    const filename = pathSegments[2];

    const response = await promisifyGrpcCall<any, any>(
      layer3Client.DownloadExcel.bind(layer3Client),
      {
        doc_kind,
        doc_type,
        filename,
      }
    );

    if (!response.success) {
      return NextResponse.json(
        { success: false, error: response.error },
        { status: 500 }
      );
    }

    const buffer = Buffer.from(response.file_content);

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": response.content_type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename="${encodeURIComponent(filename)}"`,
        "Content-Length": String(buffer.byteLength),
      },
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
