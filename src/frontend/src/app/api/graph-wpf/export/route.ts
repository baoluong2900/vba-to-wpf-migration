import fs from 'fs';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';
import { getDb, buildAccessGraph } from '../../graph/graphBuilder';
import { buildWpfLayerGraph } from '../wpfGraphTransform';

export async function POST(req: NextRequest) {
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

    const graph = {
      success: true,
      graphKind: 'wpf',
      rootId: wpf.rootId,
      elements: { nodes: wpf.nodes, edges: wpf.edges },
      stats: wpf.stats,
    };

    const outDir = path.resolve(process.cwd(), 'reports', 'wpf-graph');
    const outPath = path.resolve(outDir, `${name}.expected.json`);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify(graph, null, 2), 'utf-8');

    return NextResponse.json({
      success: true,
      path: outPath,
      graph,
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message });
  }
}
