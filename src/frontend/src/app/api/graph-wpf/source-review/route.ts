import fs from 'fs';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';
import { parseActualSourceGraph } from './sourceGraphParser';

function workflowRoot() {
  return path.resolve(process.cwd(), '..');
}

function normalizeKind(id: string) {
  if (id.startsWith('view:')) return 'view';
  if (id.startsWith('viewmodel:')) return 'viewmodel';
  if (id.startsWith('handler:macro:')) return 'macro-handler';
  if (id.startsWith('handler:')) return 'handler';
  if (id.startsWith('service:navigation')) return 'navigation';
  if (id.startsWith('service:')) return 'service';
  if (id.startsWith('repository:')) return 'repository';
  return id.split(':')[0];
}

function nodeSummary(node: any) {
  return {
    id: node?.data?.id ?? '',
    label: node?.data?.label ?? '',
    type: node?.data?.type ?? normalizeKind(node?.data?.id ?? ''),
    badge: node?.data?.badge,
    vbaLabel: node?.data?.vbaLabel,
  };
}

function edgeShape(edge: any, nodes: Map<string, any>) {
  const s = edge?.data?.source ?? '';
  const t = edge?.data?.target ?? '';
  const sourceType = nodes.get(s)?.data?.type ?? normalizeKind(s);
  const targetType = nodes.get(t)?.data?.type ?? normalizeKind(t);
  return `${sourceType}->${targetType}`;
}

function edgeSummary(edge: any, nodes: Map<string, any>) {
  const source = nodes.get(edge?.data?.source);
  const target = nodes.get(edge?.data?.target);
  return {
    source: nodeSummary(source ?? { data: { id: edge?.data?.source } }),
    target: nodeSummary(target ?? { data: { id: edge?.data?.target } }),
    label: edge?.data?.label ?? '',
    shape: edgeShape(edge, nodes),
  };
}

function compatibleActualEdges(expectedEdge: any, expectedNodes: Map<string, any>, actualEdges: any[], actualNodes: Map<string, any>) {
  const expected = edgeSummary(expectedEdge, expectedNodes);
  return actualEdges.filter((edge) => {
    const actual = edgeSummary(edge, actualNodes);
    if (actual.shape !== expected.shape) return false;

    // Phase 1 allows renamed commands/classes, but keeps anchored layers strict where possible.
    if (expected.source.type === 'view' || expected.source.type === 'viewmodel') {
      return actual.source.id === expected.source.id && actual.target.type === expected.target.type;
    }
    if (expected.target.type === 'repository') {
      return actual.target.id === expected.target.id || actual.target.label === expected.target.label;
    }
    if (expected.target.type === 'navigation') {
      return actual.target.id === 'service:navigation';
    }
    return true;
  });
}

function diffGraphs(expected: any, actual: any) {
  const expectedNodes = expected?.elements?.nodes ?? [];
  const expectedEdges = expected?.elements?.edges ?? [];
  const actualNodes = actual?.nodes ?? [];
  const actualEdges = actual?.edges ?? [];
  const expectedNodeMap = new Map<string, any>(expectedNodes.map((node: any) => [node.data.id, node]));
  const actualNodeMap = new Map<string, any>(actualNodes.map((node: any) => [node.data.id, node]));
  const actualKinds = new Set(actualNodes.map((node: any) => normalizeKind(node.data.id)));
  const expectedKinds = new Set(expectedNodes.map((node: any) => normalizeKind(node.data.id)));

  const errors: any[] = [];
  const warnings: any[] = [];

  for (const kind of expectedKinds) {
    if (!actualKinds.has(kind)) {
      const expectedOfKind = expectedNodes
        .filter((node: any) => normalizeKind(node.data.id) === kind)
        .map(nodeSummary);
      errors.push({
        rule: 'missing-node-kind',
        message: `Actual source graph is missing ${kind} node(s) required by expected flow`,
        kind,
        expectedNodes: expectedOfKind,
      });
    }
  }
  for (const kind of actualKinds) {
    if (!expectedKinds.has(kind)) warnings.push({ rule: 'extra-node-kind', message: `Actual graph has extra node kind ${kind}`, kind });
  }
  for (const edge of expectedEdges) {
    const expected = edgeSummary(edge, expectedNodeMap);
    const matches = compatibleActualEdges(edge, expectedNodeMap, actualEdges, actualNodeMap);
    if (!matches.length) {
      errors.push({
        rule: 'missing-flow',
        message: `Missing expected flow: ${expected.source.label || expected.source.id} -> ${expected.target.label || expected.target.id}`,
        expected,
        candidates: actualEdges
          .map((actualEdge: any) => edgeSummary(actualEdge, actualNodeMap))
          .filter((actualEdge: any) => actualEdge.shape === expected.shape)
          .slice(0, 5),
      });
    }
  }

  for (const edge of actualEdges) {
    const sourceType = actualNodeMap.get(edge.data.source)?.data?.type;
    const targetType = actualNodeMap.get(edge.data.target)?.data?.type;
    if ((sourceType === 'handler' || sourceType === 'viewmodel') && targetType === 'repository') {
      errors.push({ rule: 'direct-repository-call', message: 'ViewModel/Handler must not call Repository directly', edge: edge.data });
    }
    if (sourceType === 'navigation' && targetType === 'view') {
      errors.push({ rule: 'navigation-target-detail', message: 'Navigation details must not show target View', edge: edge.data });
    }
  }

  return {
    success: errors.length === 0,
    summary: {
      errors: errors.length,
      warnings: warnings.length,
      expectedNodes: expectedNodes.length,
      expectedEdges: expectedEdges.length,
      actualNodes: actualNodes.length,
      actualEdges: actualEdges.length,
    },
    errors,
    warnings,
  };
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const name = searchParams.get('name') || 'F_Login';
  const sourceRoot = path.resolve(workflowRoot(), 'source');
  const expectedPath = path.resolve(process.cwd(), 'reports', 'wpf-graph', `${name}.expected.json`);

  if (!fs.existsSync(expectedPath)) {
    return NextResponse.json({
      success: false,
      error: `Expected graph JSON not found: ${expectedPath}`,
      expectedPath,
    });
  }

  try {
    const expected = JSON.parse(fs.readFileSync(expectedPath, 'utf-8'));
    const actual = parseActualSourceGraph(sourceRoot, name);
    const report = diffGraphs(expected, actual);
    return NextResponse.json({
      success: true,
      expectedPath,
      sourceRoot,
      actual: { elements: { nodes: actual.nodes, edges: actual.edges }, stats: actual.stats },
      report,
    });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message });
  }
}
