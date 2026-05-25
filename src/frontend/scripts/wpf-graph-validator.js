const fs = require("fs");

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function nodeId(node) {
  return node && node.data && typeof node.data.id === "string" ? node.data.id : "";
}

function nodeType(node) {
  return node && node.data && typeof node.data.type === "string" ? node.data.type : "";
}

function edgeSource(edge) {
  return edge && edge.data && typeof edge.data.source === "string" ? edge.data.source : "";
}

function edgeTarget(edge) {
  return edge && edge.data && typeof edge.data.target === "string" ? edge.data.target : "";
}

function edgeLabel(edge) {
  return edge && edge.data && typeof edge.data.label === "string" ? edge.data.label : "";
}

function makeReport(input, options = {}) {
  const errors = [];
  const warnings = [];
  const graph = input && input.elements ? input.elements : input;
  const nodes = asArray(graph && graph.nodes);
  const edges = asArray(graph && graph.edges);
  const stats = input && input.stats ? input.stats : {};
  const nodeById = new Map(nodes.map((node) => [nodeId(node), node]));
  const typeById = new Map(nodes.map((node) => [nodeId(node), nodeType(node)]));

  const fail = (rule, message, detail = {}) => errors.push({ rule, message, detail });
  const warn = (rule, message, detail = {}) => warnings.push({ rule, message, detail });

  if (input && input.success === false) {
    fail("response.success", "Graph response is not successful", { error: input.error });
  }

  if (!nodes.length) fail("graph.nodes", "Graph must contain nodes");
  if (!edges.length) warn("graph.edges", "Graph contains no edges");

  for (const node of nodes) {
    const id = nodeId(node);
    const type = nodeType(node);
    if (!id) fail("node.id", "Node must have data.id", { node });
    if (!type) fail("node.type", "Node must have data.type", { id });
    if (!node.data || !node.data.mappingStatus) {
      fail("node.mappingStatus", "Every node must have mappingStatus", { id });
    }
    if (node.data && node.data.mappingStatus === "fallback") {
      fail("node.mappingStatus.fallback", "Fallback mapping is not allowed for strict WPF graph tests", { id });
    }
    if (type === "warning" || (node.data && node.data.status === "warning")) {
      fail("node.warning", "Warning nodes are not allowed", { id });
    }
    if (id.startsWith("workflow:") || type === "workflow") {
      fail("macro.workflow", "Macro must be represented as handler:macro:*, not workflow", { id, type });
    }
  }

  for (const edge of edges) {
    const source = edgeSource(edge);
    const target = edgeTarget(edge);
    if (!nodeById.has(source)) fail("edge.source", "Edge source node is missing", { edge: edge.data });
    if (!nodeById.has(target)) fail("edge.target", "Edge target node is missing", { edge: edge.data });
    if (edge.data && edge.data.status === "warning") {
      fail("edge.warning", "Warning edges are not allowed", { edge: edge.data });
    }
  }

  const hasEdge = (source, target) => edges.some((edge) => edgeSource(edge) === source && edgeTarget(edge) === target);
  const outgoing = (source) => edges.filter((edge) => edgeSource(edge) === source);
  const incoming = (target) => edges.filter((edge) => edgeTarget(edge) === target);
  const targetsOfType = (source, type) => outgoing(source).filter((edge) => typeById.get(edgeTarget(edge)) === type);

  for (const view of nodes.filter((node) => nodeType(node) === "view")) {
    const id = nodeId(view);
    const expectedVm = id.replace(/^view:/, "viewmodel:");
    if (!nodeById.has(expectedVm)) {
      fail("view.viewmodel.node", "View must have matching ViewModel node", { view: id, expectedVm });
    } else if (!hasEdge(id, expectedVm)) {
      fail("view.viewmodel.edge", "View -> ViewModel edge must exist", { view: id, viewmodel: expectedVm });
    }
  }

  for (const vm of nodes.filter((node) => nodeType(node) === "viewmodel")) {
    const id = nodeId(vm);
    const handlers = targetsOfType(id, "handler");
    if (!handlers.length && options.requireViewModelHandler !== false) {
      fail("viewmodel.handler", "ViewModel -> Handler edge must exist", { viewmodel: id });
    }
    for (const edge of outgoing(id)) {
      if (typeById.get(edgeTarget(edge)) === "repository") {
        fail("viewmodel.repository.direct", "ViewModel must not call Repository directly", { edge: edge.data });
      }
    }
  }

  for (const handler of nodes.filter((node) => nodeType(node) === "handler")) {
    const id = nodeId(handler);
    for (const edge of outgoing(id)) {
      if (typeById.get(edgeTarget(edge)) === "repository") {
        fail("handler.repository.direct", "Handler must not call Repository directly", { edge: edge.data });
      }
    }
  }

  for (const repo of nodes.filter((node) => nodeType(node) === "repository")) {
    const id = nodeId(repo);
    const serviceEdges = incoming(id).filter((edge) => typeById.get(edgeSource(edge)) === "service");
    if (!serviceEdges.length) {
      fail("repository.service", "Repository must be called by a Service", { repository: id });
    }
  }

  for (const service of nodes.filter((node) => nodeType(node) === "service")) {
    const id = nodeId(service);
    if (id === "service:navigation") continue;
    const repositoryEdges = targetsOfType(id, "repository");
    const serviceIncoming = incoming(id).filter((edge) => {
      const sourceType = typeById.get(edgeSource(edge));
      return sourceType === "handler" || sourceType === "viewmodel";
    });
    if (repositoryEdges.length && !serviceIncoming.length) {
      fail("service.caller", "Query Service must be called by Handler/ViewModel", { service: id });
    }
  }

  for (const edge of edges) {
    const sourceType = typeById.get(edgeSource(edge));
    const targetType = typeById.get(edgeTarget(edge));
    if (targetType === "navigation" && sourceType !== "handler") {
      fail("navigation.source", "NavigationService must be called by Handler only", { edge: edge.data });
    }
    if (sourceType === "navigation" && targetType === "view") {
      fail("navigation.target-detail", "Navigation details must not show target View", { edge: edge.data });
    }
    if ((edgeLabel(edge) || "").toLowerCase().includes("open") || (edgeLabel(edge) || "").toLowerCase().includes("close")) {
      fail("navigation.docmd-detail", "Open/close form/report details must be hidden behind NavigationService", { edge: edge.data });
    }
  }

  const navigationNodes = nodes.filter((node) => nodeType(node) === "navigation");
  const hasNavigationEdge = edges.some((edge) => typeById.get(edgeTarget(edge)) === "navigation");
  if (navigationNodes.length && !hasNavigationEdge) {
    fail("navigation.edge", "NavigationService exists but no Handler uses it");
  }

  const macroNodes = nodes.filter((node) => nodeId(node).startsWith("handler:macro:"));
  for (const macro of macroNodes) {
    const id = nodeId(macro);
    const callers = incoming(id).filter((edge) => typeById.get(edgeSource(edge)) === "handler");
    if (!callers.length && input.rootId !== id) {
      fail("macro.caller", "MacroCommand must be called by a Handler unless it is root", { macro: id });
    }
  }

  const expectedStats = {
    nodes: nodes.length,
    edges: edges.length,
    views: nodes.filter((node) => nodeType(node) === "view").length,
    viewmodels: nodes.filter((node) => nodeType(node) === "viewmodel").length,
    handlers: nodes.filter((node) => nodeType(node) === "handler").length,
    repositories: nodes.filter((node) => nodeType(node) === "repository").length,
    services: nodes.filter((node) => nodeType(node) === "service").length,
    navigation: nodes.filter((node) => nodeType(node) === "navigation").length,
    warnings: nodes.filter((node) => nodeType(node) === "warning").length,
  };

  for (const [key, value] of Object.entries(expectedStats)) {
    if (typeof stats[key] === "number" && stats[key] !== value) {
      fail("stats.mismatch", "Stats must match graph nodes/edges", { key, expected: value, actual: stats[key] });
    }
  }

  return {
    success: errors.length === 0,
    summary: {
      errors: errors.length,
      warnings: warnings.length,
      nodes: nodes.length,
      edges: edges.length,
    },
    errors,
    warnings,
  };
}

function validateFile(filePath, options) {
  const input = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  return makeReport(input, options);
}

module.exports = { makeReport, validateFile };
