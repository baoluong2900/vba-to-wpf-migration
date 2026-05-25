import type { CyEdge, CyNode } from '../graph/graphBuilder';

type GraphPayload = {
  success?: boolean;
  error?: string;
  rootId?: string;
  elements?: { nodes?: CyNode[]; edges?: CyEdge[] };
  stats?: Record<string, number>;
};

type ValidationIssue = {
  rule: string;
  message: string;
  detail?: Record<string, unknown>;
};

export type WpfGraphValidationReport = {
  success: boolean;
  summary: {
    errors: number;
    warnings: number;
    nodes: number;
    edges: number;
  };
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
};

function nodeId(node: CyNode) {
  return node?.data?.id ?? '';
}

function nodeType(node: CyNode) {
  return node?.data?.type ?? '';
}

function edgeSource(edge: CyEdge) {
  return edge?.data?.source ?? '';
}

function edgeTarget(edge: CyEdge) {
  return edge?.data?.target ?? '';
}

function edgeLabel(edge: CyEdge) {
  return edge?.data?.label ?? '';
}

export function validateWpfGraph(input: GraphPayload): WpfGraphValidationReport {
  const errors: ValidationIssue[] = [];
  const warnings: ValidationIssue[] = [];
  const nodes = Array.isArray(input.elements?.nodes) ? input.elements.nodes : [];
  const edges = Array.isArray(input.elements?.edges) ? input.elements.edges : [];
  const stats = input.stats ?? {};
  const nodeById = new Map(nodes.map((node) => [nodeId(node), node]));
  const typeById = new Map(nodes.map((node) => [nodeId(node), nodeType(node)]));

  const fail = (rule: string, message: string, detail?: Record<string, unknown>) => {
    errors.push({ rule, message, detail });
  };

  if (input.success === false) fail('response.success', 'Graph response is not successful', { error: input.error });
  if (!nodes.length) fail('graph.nodes', 'Graph must contain nodes');

  for (const node of nodes) {
    const id = nodeId(node);
    const type = nodeType(node);
    if (!id) fail('node.id', 'Node must have data.id');
    if (!type) fail('node.type', 'Node must have data.type', { id });
    if (!node.data.mappingStatus) fail('node.mappingStatus', 'Every node must have mappingStatus', { id });
    // if (node.data.mappingStatus === 'fallback') {
    //   fail('node.mappingStatus.fallback', 'Fallback mapping is not allowed for strict WPF graph tests', { id });
    // }
    if (type === 'warning' || node.data.status === 'warning') fail('node.warning', 'Warning nodes are not allowed', { id });
    if (id.startsWith('workflow:') || type === 'workflow') {
      fail('macro.workflow', 'Macro must be represented as handler:macro:*, not workflow', { id, type });
    }
  }

  for (const edge of edges) {
    const source = edgeSource(edge);
    const target = edgeTarget(edge);
    if (!nodeById.has(source)) fail('edge.source', 'Edge source node is missing', { edge: edge.data });
    if (!nodeById.has(target)) fail('edge.target', 'Edge target node is missing', { edge: edge.data });
    if (edge.data.status === 'warning') fail('edge.warning', 'Warning edges are not allowed', { edge: edge.data });
  }

  const hasEdge = (source: string, target: string) =>
    edges.some((edge) => edgeSource(edge) === source && edgeTarget(edge) === target);
  const outgoing = (source: string) => edges.filter((edge) => edgeSource(edge) === source);
  const incoming = (target: string) => edges.filter((edge) => edgeTarget(edge) === target);
  const targetsOfType = (source: string, type: string) =>
    outgoing(source).filter((edge) => typeById.get(edgeTarget(edge)) === type);

  for (const view of nodes.filter((node) => nodeType(node) === 'view')) {
    const id = nodeId(view);
    const expectedVm = id.replace(/^view:/, 'viewmodel:');
    if (!nodeById.has(expectedVm)) fail('view.viewmodel.node', 'View must have matching ViewModel node', { view: id, expectedVm });
    else if (!hasEdge(id, expectedVm)) fail('view.viewmodel.edge', 'View -> ViewModel edge must exist', { view: id, viewmodel: expectedVm });
  }

  for (const vm of nodes.filter((node) => nodeType(node) === 'viewmodel')) {
    const id = nodeId(vm);
    if (!targetsOfType(id, 'handler').length) fail('viewmodel.handler', 'ViewModel -> Handler edge must exist', { viewmodel: id });
    for (const edge of outgoing(id)) {
      if (typeById.get(edgeTarget(edge)) === 'repository') {
        fail('viewmodel.repository.direct', 'ViewModel must not call Repository directly', { edge: edge.data });
      }
    }
  }

  for (const handler of nodes.filter((node) => nodeType(node) === 'handler')) {
    const id = nodeId(handler);
    for (const edge of outgoing(id)) {
      if (typeById.get(edgeTarget(edge)) === 'repository') {
        fail('handler.repository.direct', 'Handler must not call Repository directly', { edge: edge.data });
      }
    }
  }

  for (const repo of nodes.filter((node) => nodeType(node) === 'repository')) {
    const id = nodeId(repo);
    if (!incoming(id).some((edge) => typeById.get(edgeSource(edge)) === 'service')) {
      fail('repository.service', 'Repository must be called by a Service', { repository: id });
    }
  }

  for (const service of nodes.filter((node) => nodeType(node) === 'service')) {
    const id = nodeId(service);
    if (id === 'service:navigation') continue;
    const callsRepository = targetsOfType(id, 'repository').length > 0;
    const hasCaller = incoming(id).some((edge) => ['handler', 'viewmodel'].includes(typeById.get(edgeSource(edge)) ?? ''));
    if (callsRepository && !hasCaller) fail('service.caller', 'Query Service must be called by Handler/ViewModel', { service: id });
  }

  for (const edge of edges) {
    const sourceType = typeById.get(edgeSource(edge));
    const targetType = typeById.get(edgeTarget(edge));
    const label = edgeLabel(edge).toLowerCase();
    if (targetType === 'navigation' && sourceType !== 'handler') {
      fail('navigation.source', 'NavigationService must be called by Handler only', { edge: edge.data });
    }
    if (sourceType === 'navigation' && targetType === 'view') {
      fail('navigation.target-detail', 'Navigation details must not show target View', { edge: edge.data });
    }
    if (label.includes('open') || label.includes('close')) {
      fail('navigation.docmd-detail', 'Open/close form/report details must be hidden behind NavigationService', { edge: edge.data });
    }
  }

  const expectedStats: Record<string, number> = {
    nodes: nodes.length,
    edges: edges.length,
    views: nodes.filter((node) => nodeType(node) === 'view').length,
    viewmodels: nodes.filter((node) => nodeType(node) === 'viewmodel').length,
    handlers: nodes.filter((node) => nodeType(node) === 'handler').length,
    repositories: nodes.filter((node) => nodeType(node) === 'repository').length,
    services: nodes.filter((node) => nodeType(node) === 'service').length,
    navigation: nodes.filter((node) => nodeType(node) === 'navigation').length,
    warnings: nodes.filter((node) => nodeType(node) === 'warning').length,
  };

  for (const [key, expected] of Object.entries(expectedStats)) {
    if (typeof stats[key] === 'number' && stats[key] !== expected) {
      fail('stats.mismatch', 'Stats must match graph nodes/edges', { key, expected, actual: stats[key] });
    }
  }

  return {
    success: errors.length === 0,
    summary: { errors: errors.length, warnings: warnings.length, nodes: nodes.length, edges: edges.length },
    errors,
    warnings,
  };
}
