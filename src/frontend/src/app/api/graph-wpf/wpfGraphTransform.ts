import path from 'path';
import fs from 'fs';
import type { CyEdge, CyNode } from '../graph/graphBuilder';

type FormRow = { access_form_name: string; wpf_view_name: string; wpf_viewmodel_name: string };
type EventRow = { access_form_name: string; handler_hint: string; suggested_dotnet_handler_name: string };
type QueryRow = { access_query_name: string; suggested_dotnet_type_name: string };
type MacroRow = { access_macro_name: string; suggested_dotnet_type_name: string };
type MappingStatus = 'mapped' | 'fallback' | 'trace';

function readJson<T>(relFromWorkflow: string): T | null {
  const candidates = [
    path.resolve(process.cwd(), relFromWorkflow),
    path.resolve(process.cwd(), '03_agents/workflow/frontend', relFromWorkflow),
    path.resolve(process.cwd(), 'frontend', relFromWorkflow),
  ];
  try {
    const p = candidates.find((candidate) => fs.existsSync(candidate));
    if (!p) return null;
    return JSON.parse(fs.readFileSync(p, 'utf-8')) as T;
  } catch {
    return null;
  }
}

let cache: {
  forms: Map<string, { view: string; vm: string }>;
  events: Map<string, string>;
  queries: Map<string, string>;
  macros: Map<string, string>;
} | null = null;

export function loadWpfMaps() {
  if (cache) return cache;
  const forms = new Map<string, { view: string; vm: string }>();
  const events = new Map<string, string>();
  const queries = new Map<string, string>();
  const macros = new Map<string, string>();

  const f = readJson<{ items?: FormRow[] }>('../backend/layer5/agents/graphview/outputs/forms/listFormJpToEn.json');
  for (const row of f?.items || []) {
    if (row.access_form_name && row.wpf_view_name) {
      forms.set(row.access_form_name, { view: row.wpf_view_name, vm: row.wpf_viewmodel_name || '' });
      forms.set(normalizeLookupKey(row.access_form_name), { view: row.wpf_view_name, vm: row.wpf_viewmodel_name || '' });
    }
  }

  const e = readJson<{ items?: EventRow[] }>('../backend/layer5/agents/graphview/outputs/events/listEventJpToEn.json');
  for (const row of e?.items || []) {
    if (row.access_form_name && row.handler_hint && row.suggested_dotnet_handler_name) {
      events.set(`${row.access_form_name}::${row.handler_hint}`, row.suggested_dotnet_handler_name);
      events.set(`${normalizeLookupKey(row.access_form_name)}::${normalizeLookupKey(row.handler_hint)}`, row.suggested_dotnet_handler_name);
    }
  }

  const q = readJson<{ items?: QueryRow[] }>('../backend/layer5/agents/graphview/outputs/queries/listQueryJpToEn.json');
  for (const row of q?.items || []) {
    if (row.access_query_name && row.suggested_dotnet_type_name) {
      queries.set(row.access_query_name, row.suggested_dotnet_type_name);
      queries.set(normalizeLookupKey(row.access_query_name), row.suggested_dotnet_type_name);
    }
  }

  const m = readJson<{ items?: MacroRow[] }>('../backend/layer5/agents/graphview/outputs/macros/listMacroJpToEn.json');
  for (const row of m?.items || []) {
    if (row.access_macro_name && row.suggested_dotnet_type_name) {
      macros.set(row.access_macro_name, row.suggested_dotnet_type_name);
      macros.set(normalizeLookupKey(row.access_macro_name), row.suggested_dotnet_type_name);
    }
  }

  cache = { forms, events, queries, macros };
  return cache;
}

function parseEventId(id: string): { form: string; handler: string } | null {
  if (!id.startsWith('event:')) return null;
  const rest = id.slice('event:'.length);
  const i = rest.indexOf('::');
  if (i < 0) return null;
  return { form: rest.slice(0, i), handler: rest.slice(i + 2) };
}

function stripPrefix(id: string, prefix: string): string | null {
  if (!id.startsWith(prefix)) return null;
  return id.slice(prefix.length);
}

function normalizeLookupKey(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/(?<=[A-Za-z\u3040-\u30ff\u3400-\u9fff_])II(?=[_\s]|$)/g, 'Ⅱ')
    .trim();
}

function mapLookup<T>(map: Map<string, T>, key: string): T | undefined {
  return map.get(key) ?? map.get(normalizeLookupKey(key));
}

function pascalFallbackName(value: string, defaultName: string): string {
  const normalized = normalizeLookupKey(value)
    .replace(/Ⅱ/g, '2')
    .replace(/[①１]/g, '1')
    .replace(/[②２]/g, '2')
    .replace(/[③３]/g, '3')
    .replace(/[④４]/g, '4')
    .replace(/[⑤５]/g, '5');
  const parts = normalized
    .split(/[^0-9A-Za-z]+/g)
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) return defaultName;
  return parts
    .map((part) => (/^[0-9]+$/.test(part) ? part : part[0].toUpperCase() + part.slice(1)))
    .join('');
}

function repositoryLabel(queryName: string, maps: ReturnType<typeof loadWpfMaps>): string {
  const spec = mapLookup(maps.queries, queryName);
  if (spec) {
    if (/AccessQuery$/i.test(spec)) return spec.replace(/AccessQuery$/i, 'Repository');
    return `${spec}Repository`;
  }
  return `${pascalFallbackName(queryName, 'Query')}Repository`;
}

function handlerId(form: string, handler: string): string {
  return `handler:${form}|${handler}`;
}

export type WpfGraphPayload = {
  nodes: CyNode[];
  edges: CyEdge[];
  stats: Record<string, number>;
  rootId: string;
};

export type WpfMappingPayload = {
  form_name: string;
  source_api: string;
  phase: 1;
  node_mapping: Array<{
    vba_id: string;
    wpf_id: string;
    wpf_file: string;
    wpf_kind: string;
    mapping_status: MappingStatus;
  }>;
  edge_mapping: Array<{
    vba_source: string;
    vba_target: string;
    vba_label: string;
    vba_edge: string;
    wpf_source: string;
    wpf_target: string;
    wpf_label: string;
    wpf_edge: string;
    expected_flow?: string[];
  }>;
  name_mapping: Array<{
    jp: string;
    en: string;
    type: string;
  }>;
};

function formViewMapping(accessForm: string, maps: ReturnType<typeof loadWpfMaps>) {
  const mapped = mapLookup(maps.forms, accessForm);
  const view = mapped?.view ?? `${accessForm}View`;
  const vm = mapped?.vm ?? `${accessForm}ViewModel`;
  return { view, vm, status: mapped ? 'mapped' as const : 'fallback' as const };
}

function eventHandlerMapping(form: string, handler: string, maps: ReturnType<typeof loadWpfMaps>) {
  const mapped = mapLookup(maps.events, `${form}::${handler}`);
  return {
    id: handlerId(form, handler),
    label: mapped ?? handler,
    status: mapped ? 'mapped' as const : 'fallback' as const,
  };
}

function macroHandlerMapping(macroName: string, maps: ReturnType<typeof loadWpfMaps>) {
  const mapped = mapLookup(maps.macros, macroName);
  const label = mapped
    ? mapped.replace(/Workflow$/i, 'Command').replace(/Macro$/i, 'Command')
    : `${pascalFallbackName(macroName, 'Macro')}Command`;
  return {
    id: `handler:macro:${macroName}`,
    label,
    status: mapped ? 'mapped' as const : 'fallback' as const,
  };
}

function moduleServiceMapping(moduleName: string) {
  const label = `${pascalFallbackName(moduleName, 'Module')}ModuleService`;
  return {
    id: `service:module:${moduleName}`,
    label,
    status: 'fallback' as const,
  };
}

function queryRepositoryMapping(queryName: string, maps: ReturnType<typeof loadWpfMaps>) {
  const mapped = mapLookup(maps.queries, queryName);
  const label = repositoryLabel(queryName, maps);
  return {
    id: `repository:${queryName}`,
    label,
    status: mapped ? 'mapped' as const : 'fallback' as const,
  };
}

function nodeDisplayName(node: CyNode | undefined, id: string) {
  return node?.data.label || id.replace(/^[^:]+:/, '');
}

function readableEdge(sourceLabel: string, targetLabel: string, label: string) {
  return `${sourceLabel} -> ${targetLabel}${label ? ` (${label})` : ''}`;
}

export function buildWpfMappingFromVbaGraph(
  vbaNodes: CyNode[],
  vbaEdges: CyEdge[],
  graphType: 'form' | 'report' | 'module' | 'macro',
  rootName: string
): WpfMappingPayload {
  const maps = loadWpfMaps();
  const nodeById = new Map(vbaNodes.map((node) => [node.data.id, node]));
  const nodeMapping = new Map<string, WpfMappingPayload['node_mapping'][number]>();
  const edgeMapping: WpfMappingPayload['edge_mapping'] = [];
  const nameMapping = new Map<string, WpfMappingPayload['name_mapping'][number]>();
  const rootForm = graphType === 'form' || graphType === 'report' ? rootName : '';
  const rootFormMap = rootForm ? formViewMapping(rootForm, maps) : null;

  function addNodeMapping(
    vbaId: string,
    wpfId: string,
    wpfFile: string,
    wpfKind: string,
    mappingStatus: MappingStatus,
    jp: string,
    en: string,
    type: string
  ) {
    if (!nodeMapping.has(vbaId)) {
      nodeMapping.set(vbaId, {
        vba_id: vbaId,
        wpf_id: wpfId,
        wpf_file: wpfFile,
        wpf_kind: wpfKind,
        mapping_status: mappingStatus,
      });
    }
    const nameKey = `${type}:${jp}`;
    if (!nameMapping.has(nameKey)) nameMapping.set(nameKey, { jp, en, type });
  }

  function addForm(accessForm: string) {
    const mapped = formViewMapping(accessForm, maps);
    addNodeMapping(
      `form:${accessForm}`,
      `view:${accessForm}`,
      `Views/${mapped.view}.xaml`,
      'view',
      mapped.status,
      accessForm,
      mapped.view,
      'form'
    );
    addNodeMapping(
      `form:${accessForm}#viewmodel`,
      `viewmodel:${accessForm}`,
      `ViewModels/${mapped.vm}.cs`,
      'viewmodel',
      mapped.status,
      accessForm,
      mapped.vm,
      'viewmodel'
    );
  }

  function addEvent(form: string, handler: string) {
    const mapped = eventHandlerMapping(form, handler, maps);
    const vm = formViewMapping(form, maps).vm;
    addNodeMapping(
      `event:${form}::${handler}`,
      mapped.id,
      `ViewModels/${vm}.cs`,
      'handler',
      mapped.status,
      handler,
      mapped.label,
      'event'
    );
  }

  function addQuery(queryName: string) {
    const mapped = queryRepositoryMapping(queryName, maps);
    addNodeMapping(
      `query:${queryName}`,
      mapped.id,
      `Infrastructure/Repositories/${mapped.label}.cs`,
      'repository',
      mapped.status,
      queryName,
      mapped.label,
      'query'
    );
  }

  function addMacro(macroName: string) {
    const mapped = macroHandlerMapping(macroName, maps);
    const vm = rootFormMap?.vm ?? 'MacroViewModel';
    addNodeMapping(
      `macro:${macroName}`,
      mapped.id,
      `ViewModels/${vm}.cs`,
      'macro-handler',
      mapped.status,
      macroName,
      mapped.label,
      'macro'
    );
  }

  function addModule(moduleName: string) {
    const mapped = moduleServiceMapping(moduleName);
    addNodeMapping(
      `module:${moduleName}`,
      mapped.id,
      `Application/Services/${mapped.label}.cs`,
      'service',
      mapped.status,
      moduleName,
      mapped.label,
      'module'
    );
  }

  for (const node of vbaNodes) {
    const id = node.data.id;
    const event = parseEventId(id);
    const form = stripPrefix(id, 'form:');
    const report = stripPrefix(id, 'report:');
    const query = stripPrefix(id, 'query:');
    const macro = stripPrefix(id, 'macro:');
    const moduleVal = stripPrefix(id, 'module:');

    if (form) addForm(form);
    else if (report) addForm(report);
    else if (event) addEvent(event.form, event.handler);
    else if (query) addQuery(query);
    else if (macro) addMacro(macro);
    else if (moduleVal) addModule(moduleVal);
  }

  const addEdge = (
    edge: CyEdge,
    wpfSource: string,
    wpfTarget: string,
    wpfLabel: string,
    expectedFlow?: string[]
  ) => {
    const sourceLabel = nodeDisplayName(nodeById.get(edge.data.source), edge.data.source);
    const targetLabel = nodeDisplayName(nodeById.get(edge.data.target), edge.data.target);
    edgeMapping.push({
      vba_source: edge.data.source,
      vba_target: edge.data.target,
      vba_label: edge.data.label ?? '',
      vba_edge: readableEdge(sourceLabel, targetLabel, edge.data.label ?? ''),
      wpf_source: wpfSource,
      wpf_target: wpfTarget,
      wpf_label: wpfLabel,
      wpf_edge: readableEdge(wpfSource, wpfTarget, wpfLabel),
      expected_flow: expectedFlow,
    });
  };

  for (const edge of vbaEdges) {
    const s = edge.data.source;
    const t = edge.data.target;
    const sEvent = parseEventId(s);
    const tEvent = parseEventId(t);
    const sForm = stripPrefix(s, 'form:') ?? stripPrefix(s, 'report:');
    const sMacro = stripPrefix(s, 'macro:');
    const tForm = stripPrefix(t, 'form:') ?? stripPrefix(t, 'report:');
    const tQuery = stripPrefix(t, 'query:');
    const tMacro = stripPrefix(t, 'macro:');
    const tModule = stripPrefix(t, 'module:');

    if (sForm && tEvent) {
      addEdge(edge, `viewmodel:${sForm}`, handlerId(tEvent.form, tEvent.handler), 'event', [
        `view:${sForm}`,
        `viewmodel:${sForm}`,
        handlerId(tEvent.form, tEvent.handler),
      ]);
      continue;
    }

    if (sEvent && tQuery) {
      const service = `service:${sEvent.form}|${sEvent.handler}`;
      const repository = `repository:${tQuery}`;
      addNodeMapping(
        `${s}#service`,
        service,
        `Application/Services/${eventHandlerMapping(sEvent.form, sEvent.handler, maps).label.replace(/Command$/i, '')}Service.cs`,
        'service',
        eventHandlerMapping(sEvent.form, sEvent.handler, maps).status,
        `${sEvent.form}::${sEvent.handler}`,
        `${eventHandlerMapping(sEvent.form, sEvent.handler, maps).label.replace(/Command$/i, '')}Service`,
        'service'
      );
      addEdge(edge, handlerId(sEvent.form, sEvent.handler), repository, 'calls service -> uses repository', [
        handlerId(sEvent.form, sEvent.handler),
        service,
        repository,
      ]);
      continue;
    }

    if (sEvent && tMacro) {
      addEdge(edge, handlerId(sEvent.form, sEvent.handler), `handler:macro:${tMacro}`, 'invokes macro handler', [
        handlerId(sEvent.form, sEvent.handler),
        `handler:macro:${tMacro}`,
      ]);
      continue;
    }

    if (sEvent && tModule) {
      addEdge(edge, handlerId(sEvent.form, sEvent.handler), `service:module:${tModule}`, 'references service', [
        handlerId(sEvent.form, sEvent.handler),
        `service:module:${tModule}`,
      ]);
      continue;
    }

    if (sEvent && tForm) {
      addEdge(edge, handlerId(sEvent.form, sEvent.handler), 'service:navigation', 'uses navigation', [
        handlerId(sEvent.form, sEvent.handler),
        'service:navigation',
      ]);
      continue;
    }

    if (sMacro && tForm) {
      addEdge(edge, `handler:macro:${sMacro}`, 'service:navigation', 'uses navigation', [
        `handler:macro:${sMacro}`,
        'service:navigation',
      ]);
      continue;
    }

    if (sMacro && tQuery) {
      const service = `service:macro:${sMacro}`;
      const repository = `repository:${tQuery}`;
      addEdge(edge, `handler:macro:${sMacro}`, repository, 'calls service -> uses repository', [
        `handler:macro:${sMacro}`,
        service,
        repository,
      ]);
    }
  }

  if (edgeMapping.some((edge) => edge.wpf_target === 'service:navigation' || edge.expected_flow?.includes('service:navigation'))) {
    addNodeMapping(
      'navigation:DoCmd',
      'service:navigation',
      'Application/Navigation/NavigationService.cs',
      'navigation',
      'mapped',
      'DoCmd.OpenForm/Close/OpenReport',
      'NavigationService',
      'navigation'
    );
  }

  return {
    form_name: rootName,
    source_api: `/api/graph?name=${rootName}&type=${graphType}`,
    phase: 1,
    node_mapping: [...nodeMapping.values()],
    edge_mapping: edgeMapping,
    name_mapping: [...nameMapping.values()],
  };
}

export function buildWpfLayerGraph(
  vbaNodes: CyNode[],
  vbaEdges: CyEdge[],
  graphType: 'form' | 'report' | 'module' | 'macro',
  rootName: string
): WpfGraphPayload {
  const maps = loadWpfMaps();
  const nodeById = new Map<string, CyNode>();
  const edgeKey = new Set<string>();
  const outEdges: CyEdge[] = [];

  function addNode(
    id: string,
    label: string,
    nodeType: string,
    badge?: string,
    vbaLabel?: string,
    mappingStatus: MappingStatus = 'mapped',
    status?: 'warning'
  ) {
    if (nodeById.has(id)) return;
    nodeById.set(id, { data: { id, label, type: nodeType, badge, vbaLabel, mappingStatus, status } });
  }

  function pushEdge(source: string, target: string, label?: string, status?: 'warning', vbaLabel?: string) {
    if (source === target) return;
    const k = `${source}>>${target}>>${label ?? ''}`;
    if (edgeKey.has(k)) return;
    edgeKey.add(k);
    outEdges.push({ data: { id: `e:${source}__${target}__${outEdges.length}`, source, target, label, status, vbaLabel } });
  }

  const ensureFormStack = (accessForm: string) => {
    const m = mapLookup(maps.forms, accessForm);
    const viewLabel = m?.view ?? `${accessForm}View`;
    const vmLabel = m?.vm ?? `${accessForm}ViewModel`;
    const status: MappingStatus = m ? 'mapped' : 'fallback';
    addNode(`view:${accessForm}`, viewLabel, 'view', 'Views/*.xaml', accessForm, status);
    addNode(`viewmodel:${accessForm}`, vmLabel, 'viewmodel', 'ViewModels/*.cs', accessForm, status);
    pushEdge(`view:${accessForm}`, `viewmodel:${accessForm}`, 'DataContext');
  };

  const ensureReportStack = (accessReport: string) => {
    const m = mapLookup(maps.forms, accessReport);
    const viewLabel = m?.view ?? `${accessReport}View`;
    const vmLabel = m?.vm ?? `${accessReport}ViewModel`;
    const status: MappingStatus = m ? 'mapped' : 'fallback';
    addNode(`view:${accessReport}`, viewLabel, 'view', 'Views/*.xaml', accessReport, status);
    addNode(`viewmodel:${accessReport}`, vmLabel, 'viewmodel', 'ViewModels/*.cs', accessReport, status);
    pushEdge(`view:${accessReport}`, `viewmodel:${accessReport}`, 'DataContext');
  };

  const ensureHandler = (form: string, handler: string) => {
    const hid = handlerId(form, handler);
    const mapped = mapLookup(maps.events, `${form}::${handler}`);
    addNode(hid, mapped ?? handler, 'handler', 'ICommand', `${form}::${handler}`, mapped ? 'mapped' : 'fallback');
    return hid;
  };

  const ensureMacroCommand = (macroName: string) => {
    const hid = `handler:macro:${macroName}`;
    const mapped = mapLookup(maps.macros, macroName);
    const label = mapped
      ? mapped.replace(/Workflow$/i, 'Command').replace(/Macro$/i, 'Command')
      : `${pascalFallbackName(macroName, 'Macro')}Command`;
    addNode(hid, label, 'handler', 'ICommand (macro)', macroName, mapped ? 'mapped' : 'fallback');
    return hid;
  };

  const ensureRepository = (queryName: string) => {
    const rid = `repository:${queryName}`;
    const mapped = mapLookup(maps.queries, queryName);
    addNode(
      rid,
      repositoryLabel(queryName, maps),
      'repository',
      'Infrastructure/Repositories',
      queryName,
      mapped ? 'mapped' : 'fallback'
    );
    return rid;
  };

  const ensureUseCaseService = (accessName: string) => {
    const sid = `service:${accessName}`;
    const m = mapLookup(maps.forms, accessName);
    const base = m?.vm ? m.vm.replace(/ViewModel$/i, '') : pascalFallbackName(accessName, 'UseCase');
    addNode(sid, `${base}Service`, 'service', 'Application/Services', accessName, m ? 'mapped' : 'fallback');
    return sid;
  };

  const ensureHandlerService = (form: string, handler: string) => {
    const sid = `service:${form}|${handler}`;
    const mapped = mapLookup(maps.events, `${form}::${handler}`);
    const base = mapped
      ? mapped.replace(/Command$/i, '').replace(/^On/i, '')
      : pascalFallbackName(handler, 'Command');
    addNode(
      sid,
      `${base}Service`,
      'service',
      'Application/Services',
      `${form}::${handler}`,
      mapped ? 'mapped' : 'fallback'
    );
    return sid;
  };

  const ensureMacroService = (macroName: string) => {
    const sid = `service:macro:${macroName}`;
    const mapped = mapLookup(maps.macros, macroName);
    const base = (mapped ?? pascalFallbackName(macroName, 'Macro'))
      .replace(/Workflow$/i, '')
      .replace(/Macro$/i, '')
      .replace(/Command$/i, '');
    addNode(sid, `${base}Service`, 'service', 'Application/Services', macroName, mapped ? 'mapped' : 'fallback');
    return sid;
  };

  const ensureModuleService = (moduleName: string) => {
    const sid = `service:module:${moduleName}`;
    addNode(sid, `${pascalFallbackName(moduleName, 'Module')}ModuleService`, 'service', 'Application/Services', moduleName, 'fallback');
    return sid;
  };

  const ensureNavigationService = () => {
    const sid = 'service:navigation';
    addNode(sid, 'NavigationService', 'navigation', 'Application/Navigation', 'DoCmd.OpenForm/OpenReport');
    return sid;
  };

  const ensureTraceNode = (vbaId: string) => {
    const id = `trace:${vbaId}`;
    addNode(id, vbaId.replace(/^[^:]+:/, ''), 'warning', 'Unmapped VBA dependency', vbaId, 'trace', 'warning');
    return id;
  };

  const referencedForms = new Set<string>();
  const reportNames = new Set<string>();
  const scanId = (id: string) => {
    if (id.startsWith('form:')) referencedForms.add(id.slice('form:'.length));
    if (id.startsWith('report:')) {
      const r = id.slice('report:'.length);
      referencedForms.add(r);
      reportNames.add(r);
    }
  };
  if (graphType === 'form') referencedForms.add(rootName);
  if (graphType === 'report') {
    referencedForms.add(rootName);
    reportNames.add(rootName);
  }
  for (const e of vbaEdges) scanId(e.data.source);

  for (const f of referencedForms) {
    if (reportNames.has(f) || vbaNodes.some((n) => n.data.id === `report:${f}`)) ensureReportStack(f);
    else ensureFormStack(f);
  }

  let rootId: string;
  if (graphType === 'macro') {
    rootId = ensureMacroCommand(rootName);
  } else if (graphType === 'module') {
    rootId = ensureModuleService(rootName);
  } else if (graphType === 'report') {
    ensureReportStack(rootName);
    rootId = `view:${rootName}`;
  } else {
    ensureFormStack(rootName);
    rootId = `view:${rootName}`;
  }

  for (const n of vbaNodes) {
    const ev = parseEventId(n.data.id);
    if (ev) ensureHandler(ev.form, ev.handler);
    if (n.data.id.startsWith('query:')) ensureRepository(n.data.id.slice('query:'.length));
    if (n.data.id.startsWith('macro:')) ensureMacroCommand(n.data.id.slice('macro:'.length));
    if (n.data.id.startsWith('module:')) ensureModuleService(n.data.id.slice('module:'.length));
  }

  for (const e of vbaEdges) {
    const s = e.data.source;
    const t = e.data.target;
    const lbl = e.data.label;

    const sEvent = parseEventId(s);
    const tEvent = parseEventId(t);

    const sForm = stripPrefix(s, 'form:');
    const sReport = stripPrefix(s, 'report:');
    const sMacro = stripPrefix(s, 'macro:');
    const sModule = stripPrefix(s, 'module:');

    const tForm = stripPrefix(t, 'form:');
    const tReport = stripPrefix(t, 'report:');
    const tQuery = stripPrefix(t, 'query:');
    const tMacro = stripPrefix(t, 'macro:');
    const tModule = stripPrefix(t, 'module:');

    if ((sForm || sReport) && tEvent) {
      const form = sForm ?? sReport!;
      pushEdge(`viewmodel:${form}`, ensureHandler(tEvent.form, tEvent.handler), lbl ?? 'handles');
      continue;
    }

    if (sModule && tEvent) {
      pushEdge(`service:module:${sModule}`, ensureHandler(tEvent.form, tEvent.handler), lbl ?? 'handles');
      continue;
    }

    if (sMacro && tMacro) {
      pushEdge(ensureMacroCommand(sMacro), ensureMacroCommand(tMacro), lbl ?? 'calls command');
      continue;
    }

    if (sMacro && (tForm || tReport)) {
      const nav = ensureNavigationService();
      pushEdge(ensureMacroCommand(sMacro), nav, 'uses navigation');
      continue;
    }

    if (sMacro && tQuery) {
      const sid = ensureMacroService(sMacro);
      pushEdge(ensureMacroCommand(sMacro), sid, 'calls service');
      pushEdge(sid, ensureRepository(tQuery), 'uses repository');
      continue;
    }

    if (sEvent && tQuery) {
      const sid = ensureHandlerService(sEvent.form, sEvent.handler);
      pushEdge(handlerId(sEvent.form, sEvent.handler), sid, 'calls service');
      pushEdge(sid, ensureRepository(tQuery), 'uses repository');
      continue;
    }

    if (sEvent && (tForm || tReport)) {
      const nav = ensureNavigationService();
      pushEdge(handlerId(sEvent.form, sEvent.handler), nav, 'uses navigation');
      continue;
    }

    if (sEvent && tMacro) {
      pushEdge(handlerId(sEvent.form, sEvent.handler), ensureMacroCommand(tMacro), lbl ?? 'invokes command');
      continue;
    }

    if (sEvent && tModule) {
      pushEdge(handlerId(sEvent.form, sEvent.handler), ensureModuleService(tModule), lbl ?? 'uses');
      continue;
    }

    if ((sForm || sReport) && tQuery) {
      const form = sForm ?? sReport!;
      const sid = ensureUseCaseService(form);
      pushEdge(`viewmodel:${form}`, sid, 'loads via service');
      pushEdge(sid, ensureRepository(tQuery), 'uses repository');
      continue;
    }

    if (sModule && tQuery) {
      pushEdge(ensureModuleService(sModule), ensureRepository(tQuery), 'uses repository');
      continue;
    }

    const src = ensureTraceNode(s);
    const dst = ensureTraceNode(t);
    pushEdge(src, dst, lbl ?? 'unmapped dependency', 'warning', `${s} -> ${t}`);
  }

  const nodes = [...nodeById.values()];
  const countType = (t: string) => nodes.filter((n) => n.data.type === t).length;

  const stats: Record<string, number> = {
    nodes: nodes.length,
    edges: outEdges.length,
    views: countType('view'),
    viewmodels: countType('viewmodel'),
    handlers: countType('handler'),
    repositories: countType('repository'),
    services: countType('service'),
    navigation: countType('navigation'),
    warnings: countType('warning'),
    workflows: countType('workflow'),
    events: countType('handler'),
    macros: nodes.filter((n) => n.data.id.startsWith('handler:macro:')).length,
    modules: countType('service'),
    queries: countType('repository'),
    forms: countType('view'),
  };

  return { nodes, edges: outEdges, stats, rootId };
}
