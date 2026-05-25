import { NextRequest, NextResponse } from 'next/server';
import { layer3Client, promisifyGrpcCall } from '../../../../../../grpcClient';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ doc_kind: string, doc_type: string, filename: string }> }
) {
  try {
    const resolvedParams = await params;
    const response = await promisifyGrpcCall<any, any>(
      layer3Client.DownloadDoc.bind(layer3Client),
      {
        doc_kind: resolvedParams.doc_kind,
        doc_type: resolvedParams.doc_type,
        filename: resolvedParams.filename
      }
    );

    if (!response.success) {
      return NextResponse.json({ success: false, error: response.error }, { status: 500 });
    }

    const headers = new Headers();
    headers.set('Content-Type', response.content_type || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    headers.set('Content-Disposition', `attachment; filename="${resolvedParams.filename}"`);

    return new NextResponse(response.file_content, { status: 200, headers });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
