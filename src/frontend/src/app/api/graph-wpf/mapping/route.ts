import { NextRequest, NextResponse } from 'next/server';
import { getDb, buildAccessGraph } from '../../graph/graphBuilder';
import { buildWpfMappingFromVbaGraph } from '../wpfGraphTransform';

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

    const mapping = buildWpfMappingFromVbaGraph(
      [...result.elements.nodes],
      [...result.elements.edges],
      type as 'form' | 'report' | 'module' | 'macro',
      name
    );

    return NextResponse.json({
      success: true,
      graphKind: 'wpf-mapping',
      ...mapping,
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message });
  }
}
