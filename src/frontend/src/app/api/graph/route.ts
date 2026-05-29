import { NextRequest, NextResponse } from 'next/server';
import { getDb, buildAccessGraph } from './graphBuilder';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const name = searchParams.get('name') || '';
  const type = searchParams.get('type') || 'form';

  if (!name) {
    return NextResponse.json({ success: false, error: 'Missing name param' });
  }

  try {
    const db = await getDb();
    const result = await buildAccessGraph(db, name, type);
    if (result.success === false) {
      return NextResponse.json({ success: false, error: result.error });
    }
    return NextResponse.json({
      success: true,
      elements: result.elements,
      stats: result.stats,
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message });
  }
}
