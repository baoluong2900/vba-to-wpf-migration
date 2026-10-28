import { MongoClient, Db } from 'mongodb';
import fs from 'fs';
import { CONFIG_PATH } from '../../../lib/paths';

// ── Mongo connection ──────────────────────────────────────────────────────────
let _config: any = null;
function getConfig() {
  if (_config) return _config;
  try {
    _config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
  } catch (e) {
    throw new Error(`Failed to load config.json at ${CONFIG_PATH}: ${e}`);
  }
  return _config;
}

// The connect promise lives on globalThis so dev reloads reuse it; a failed connect is
// forgotten so the next request retries instead of reusing a closed client.
const mongoCache = globalThis as typeof globalThis & { __vbaBrainMongo?: Promise<MongoClient> };

export async function getDb(): Promise<Db> {
  const cfg = getConfig();
  if (!mongoCache.__vbaBrainMongo) {
    const client = new MongoClient(cfg.mongodb.uri);
    mongoCache.__vbaBrainMongo = client.connect().catch((err) => {
      mongoCache.__vbaBrainMongo = undefined;
      client.close().catch(() => {});
      throw err;
    });
  }
  const client = await mongoCache.__vbaBrainMongo;
  return client.db(cfg.mongodb.db);
}

// ── VBA preprocess ────────────────────────────────────────────────────────────
function stripVbaLineBareRem(line: string): string | null {
  const t = line.trimStart();
  if (/^Rem(\s|$)/i.test(t)) return '';
  return line;
}

function stripVbaLineQuoteComment(line: string): string {
  let i = 0;
  let inDouble = false;
  while (i < line.length) {
    const c = line[i];
    if (c === '"') {
      inDouble = !inDouble;
      i++;
      continue;
    }
    if (!inDouble && c === "'") {
      return line.slice(0, i);
    }
    i++;
  }
  return line;
}

function stripVbaComments(code: string): string {
  return code
    .split(/\r?\n/)
    .map((ln) => {
      const bare = stripVbaLineBareRem(ln);
      if (bare === '') return '';
      return stripVbaLineQuoteComment(bare);
    })
    .join('\n');
}

function extractOpenQuery(code: string): string[] {
  const matches = [
    ...code.matchAll(/DoCmd\.OpenQuery\s+"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.OpenQuery\s+'([^']+)'/gi),
  ];
  return [...new Set(matches.map((m) => m[1]))];
}

function extractOpenForm(code: string): string[] {
  const matches = [
    ...code.matchAll(/DoCmd\.OpenForm\s+"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.OpenForm\s+'([^']+)'/gi),
  ];
  return [...new Set(matches.map((m) => m[1]))];
}

function extractCloseForm(code: string): string[] {
  const matches = [
    ...code.matchAll(/DoCmd\.Close\s+acForm\s*,\s*"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.Close\s+acForm\s*,\s*'([^']+)'/gi),
  ];
  return [...new Set(matches.map((m) => m[1]))];
}

function extractOpenReport(code: string): string[] {
  const matches = [
    ...code.matchAll(/DoCmd\.OpenReport\s+"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.OpenReport\s+'([^']+)'/gi),
  ];
  return [...new Set(matches.map((m) => m[1]))];
}

function extractReportReferences(code: string): string[] {
  const matches = [
    ...code.matchAll(/DoCmd\.OutputTo\s+acOutputReport\s*,\s*"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.OutputTo\s+acOutputReport\s*,\s*'([^']+)'/gi),
    ...code.matchAll(/DoCmd\.SelectObject\s+acReport\s*,\s*"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.SelectObject\s+acReport\s*,\s*'([^']+)'/gi),
    ...code.matchAll(/DoCmd\.Close\s+acReport\s*,\s*"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.Close\s+acReport\s*,\s*'([^']+)'/gi),
  ];
  return [...new Set(matches.map((m) => m[1]))];
}

function extractRunMacro(code: string): string[] {
  const matches = [
    ...code.matchAll(/DoCmd\.RunMacro\s+"([^"]+)"/gi),
    ...code.matchAll(/DoCmd\.RunMacro\s+'([^']+)'/gi),
  ];
  return [...new Set(matches.map((m) => m[1]))];
}

// ── Graph types / builder ─────────────────────────────────────────────────────
export type CyNode = {
  data: {
    id: string;
    label: string;
    type: string;
    badge?: string;
    vbaLabel?: string;
    mappingStatus?: 'mapped' | 'fallback' | 'trace';
    status?: 'ok' | 'missing' | 'extra' | 'mismatch' | 'warning';
  };
};
export type CyEdge = {
  data: {
    id: string;
    source: string;
    target: string;
    label?: string;
    status?: 'ok' | 'missing' | 'extra' | 'mismatch' | 'warning';
    vbaLabel?: string;
  };
};

export type GraphBuildResult =
  | { success: true; elements: { nodes: CyNode[]; edges: CyEdge[] }; stats: Record<string, number> }
  | { success: false; error: string };

export async function buildAccessGraph(db: Db, name: string, type: string): Promise<GraphBuildResult> {
  const nodes: CyNode[] = [];
  const edges: CyEdge[] = [];
  const addedNodes = new Set<string>();
  const addedEdges = new Set<string>();

  function addNode(id: string, label: string, nodeType: string, badge?: string) {
    if (!addedNodes.has(id)) {
      addedNodes.add(id);
      nodes.push({ data: { id, label, type: nodeType, badge } });
    }
  }

  function addEdge(source: string, target: string, label?: string) {
    const edgeId = `${source}__${target}`;
    if (!addedEdges.has(edgeId)) {
      addedEdges.add(edgeId);
      edges.push({ data: { id: edgeId, source, target, label } });
    }
  }

  const allMacros: Record<string, any> = {};
  const macroDocs = await db.collection('macros').find({}, { projection: { macro_name: 1, steps: 1, references: 1 } }).toArray();
  for (const m of macroDocs) {
    allMacros[m.macro_name] = m;
  }

  const resolvedMacros = new Set<string>();
  function resolveMacro(macroName: string, parentId: string, depth: number = 0) {
    if (depth > 3 || resolvedMacros.has(macroName)) return;
    resolvedMacros.add(macroName);

    const macroId = `macro:${macroName}`;
    addNode(macroId, macroName, 'macro');
    addEdge(parentId, macroId, 'calls');

    const mac = allMacros[macroName];
    if (!mac) return;

    const refs = mac.references || {};
    for (const formRef of refs.forms || []) {
      const fId = `form:${formRef}`;
      addNode(fId, formRef, 'form');
      addEdge(macroId, fId, 'opens form');
    }
    for (const qRef of refs.queries || []) {
      const qId = `query:${qRef}`;
      addNode(qId, qRef, 'query');
      addEdge(macroId, qId, 'runs query');
    }

    for (const step of mac.steps || []) {
      if (step.action === 'RunMacro' && step.macro_name) {
        resolveMacro(step.macro_name, macroId, depth + 1);
      }
    }
  }

  const collectionName =
    type === 'macro' ? 'macros' : type === 'module' ? 'modules' : type === 'report' ? 'reports' : 'forms';
  const nameField = type === 'macro' ? 'macro_name' : type === 'module' ? 'module_name' : 'name';

  let doc = await db.collection(collectionName).findOne({ [nameField]: name });

  if (!doc && (type === 'form' || type === 'report')) {
    const fallbackColl = type === 'form' ? 'reports' : 'forms';
    doc = await db.collection(fallbackColl).findOne({ [nameField]: name });
  }

  if (!doc) {
    return { success: false, error: `Document '${name}' not found` };
  }

  const rootId = `${type}:${name}`;
  addNode(rootId, name, type);

  if (type === 'macro') {
    resolveMacro(name, rootId, 0);
  } else {
    const rs = doc.record_source || (doc.properties && doc.properties.data && doc.properties.data.recordsource);
    if (rs && typeof rs === 'string' && !rs.trim().toUpperCase().startsWith('SELECT')) {
      const qId = `query:${rs}`;
      addNode(qId, rs, 'query');
      addEdge(rootId, qId, 'record source');
    }

    const functions: any[] = doc.functions || doc.vba_procedures || [];
    const eventCount = functions.length;

    for (const fn of functions) {
      const handler = fn.handler || 'unknown';
      const codeRaw = fn.code || '';
      const code = stripVbaComments(codeRaw);
      const eventId = `event:${name}::${handler}`;
      addNode(eventId, handler, 'event');
      addEdge(rootId, eventId, 'event');

      const refsFn = fn.references || {};
      const macroNames = new Set<string>();
      for (const m of refsFn.macros || []) {
        if (typeof m === 'string' && m) macroNames.add(m);
      }
      for (const m of extractRunMacro(code)) {
        macroNames.add(m);
      }
      for (const macroCall of macroNames) {
        resolveMacro(macroCall, eventId, 0);
      }

      for (const modRef of refsFn.modules || []) {
        if (typeof modRef !== 'string' || !modRef) continue;
        const modId = `module:${modRef}`;
        addNode(modId, modRef, 'module');
        addEdge(eventId, modId, 'references');
      }

      const queryNames = new Set<string>();
      for (const qName of refsFn.queries || []) {
        if (typeof qName === 'string' && qName) queryNames.add(qName);
      }
      for (const qName of extractOpenQuery(code)) {
        queryNames.add(qName);
      }
      for (const qName of queryNames) {
        const qId = `query:${qName}`;
        addNode(qId, qName, 'query');
        addEdge(eventId, qId, 'opens query');
      }

      for (const fName of extractOpenForm(code)) {
        const fId = `form:${fName}`;
        addNode(fId, fName, 'form');
        addEdge(eventId, fId, 'opens form');
      }

      for (const fName of extractCloseForm(code)) {
        const fId = `form:${fName}`;
        addNode(fId, fName, 'form');
        addEdge(eventId, fId, 'closes form');
      }

      const reportNames = new Set<string>();
      for (const rName of refsFn.reports || []) {
        if (typeof rName === 'string' && rName) reportNames.add(rName);
      }
      for (const rName of extractOpenReport(code)) {
        reportNames.add(rName);
      }
      for (const rName of extractReportReferences(code)) {
        reportNames.add(rName);
      }
      for (const rName of reportNames) {
        const rId = `report:${rName}`;
        addNode(rId, rName, 'report');
        addEdge(eventId, rId, 'references report');
      }
    }

    const rootNode = nodes.find((n) => n.data.id === rootId);
    if (rootNode) rootNode.data.badge = `${eventCount} events`;
  }

  const stats = {
    nodes: nodes.length,
    edges: edges.length,
    events: nodes.filter((n) => n.data.type === 'event').length,
    macros: nodes.filter((n) => n.data.type === 'macro').length,
    modules: nodes.filter((n) => n.data.type === 'module').length,
    queries: nodes.filter((n) => n.data.type === 'query').length,
    reports: nodes.filter((n) => n.data.type === 'report' && n.data.id !== rootId).length,
    forms: nodes.filter((n) => n.data.type === 'form' && n.data.id !== rootId).length,
  };

  return { success: true, elements: { nodes, edges }, stats };
}
