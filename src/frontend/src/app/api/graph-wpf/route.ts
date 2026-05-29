import { NextRequest, NextResponse } from 'next/server';
import { getDb, buildAccessGraph } from '../graph/graphBuilder';
import { buildWpfLayerGraph } from './wpfGraphTransform';

/**
 * Dependency graph rewritten into suggested WPF layers (View, ViewModel,
 * Handler, Repository, Service, Workflow) using Layer5 graphview JSON exports.
 */
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

    const wpf = buildWpfLayerGraph(
      [...result.elements.nodes],
      [...result.elements.edges],
      type as 'form' | 'report' | 'module' | 'macro',
      name
    );

    return NextResponse.json({
      success: true,
      graphKind: 'wpf',
      rootId: wpf.rootId,
      elements: { nodes: wpf.nodes, edges: wpf.edges },
      stats: wpf.stats,
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message });
  }
}
