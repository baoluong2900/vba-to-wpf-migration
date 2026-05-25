import fs from 'fs';
import path from 'path';
import type { CyEdge, CyNode } from '../../graph/graphBuilder';

type ActualGraph = {
  nodes: CyNode[];
  edges: CyEdge[];
  stats: Record<string, number>;
  files: string[];
};

function walkFiles(dir: string, exts: Set<string>, out: string[] = []) {
  if (!fs.existsSync(dir)) return out;
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, item.name);
    if (item.isDirectory()) walkFiles(p, exts, out);
    else if (exts.has(path.extname(item.name).toLowerCase())) out.push(p);
  }
  return out;
}

function readIfExists(filePath: string) {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf-8') : '';
}

function addNode(nodes: Map<string, CyNode>, id: string, label: string, type: string, badge?: string, vbaLabel?: string) {
  if (!nodes.has(id)) {
    nodes.set(id, { data: { id, label, type, badge, vbaLabel, mappingStatus: 'mapped' } });
  }
}

function addEdge(edges: CyEdge[], seen: Set<string>, source: string, target: string, label?: string) {
  if (source === target) return;
  const key = `${source}->${target}->${label ?? ''}`;
  if (seen.has(key)) return;
  seen.add(key);
  edges.push({ data: { id: `actual:${edges.length}`, source, target, label } });
}

function classNameFromFile(filePath: string) {
  return path.basename(filePath, path.extname(filePath));
}

function commandNames(code: string) {
  const names = new Set<string>();
  for (const m of code.matchAll(/\b(?:ICommand|RelayCommand|DelegateCommand|AsyncRelayCommand)\s+([A-Za-z_][A-Za-z0-9_]*)/g)) {
    names.add(m[1]);
  }
  for (const m of code.matchAll(/\b([A-Za-z_][A-Za-z0-9_]*Command)\b/g)) {
    names.add(m[1]);
  }
  return [...names];
}

function constructorParams(code: string, suffix: string) {
  const names = new Set<string>();
  const re = new RegExp(`\\bI?([A-Za-z_][A-Za-z0-9_]*${suffix})\\b`, 'g');
  for (const m of code.matchAll(re)) names.add(m[1]);
  return [...names];
}

function methodCallsToClasses(code: string, classNames: string[]) {
  const found = new Set<string>();
  for (const cls of classNames) {
    const base = cls.replace(/^I/, '');
    const varPattern = new RegExp(`\\b_?[a-zA-Z0-9]*${base.replace(/Service$|Repository$/, '')}[a-zA-Z0-9]*\\.`, 'i');
    if (varPattern.test(code) || new RegExp(`\\b${cls}\\b`).test(code)) found.add(cls);
  }
  return [...found];
}

export function parseActualSourceGraph(sourceRoot: string, screenName: string): ActualGraph {
  const files = walkFiles(sourceRoot, new Set(['.cs', '.xaml', '.csproj', '.sln', '.json']));
  const nodes = new Map<string, CyNode>();
  const edges: CyEdge[] = [];
  const edgeSeen = new Set<string>();

  const viewFile = files.find((f) => f.endsWith(path.join('Views', `${screenName}.xaml`)));
  const viewModelFile = files.find((f) => f.endsWith(path.join('ViewModels', `${screenName}.cs`)));
  const viewLabel = viewFile ? classNameFromFile(viewFile) : `${screenName}View`;
  const viewModelLabel = viewModelFile ? classNameFromFile(viewModelFile) : `${screenName}ViewModel`;

  if (viewFile) addNode(nodes, `view:${screenName}`, viewLabel, 'view', path.relative(sourceRoot, viewFile), screenName);
  if (viewModelFile) addNode(nodes, `viewmodel:${screenName}`, viewModelLabel, 'viewmodel', path.relative(sourceRoot, viewModelFile), screenName);
  if (viewFile && viewModelFile) addEdge(edges, edgeSeen, `view:${screenName}`, `viewmodel:${screenName}`, 'DataContext');

  const serviceFiles = files.filter((f) => /Services[\\/].+\.cs$/i.test(f));
  const repositoryFiles = files.filter((f) => /Repositories[\\/].+\.cs$/i.test(f));
  const serviceClasses = serviceFiles.map(classNameFromFile).filter((name) => !name.startsWith('I'));
  const repositoryClasses = repositoryFiles.map(classNameFromFile).filter((name) => !name.startsWith('I'));

  const vmCode = readIfExists(viewModelFile ?? '');
  const xamlCode = readIfExists(viewFile ?? '');
  const xamlCommands = [...xamlCode.matchAll(/Command\s*=\s*"\{Binding\s+([^,}\s]+)/g)].map((m) => m[1]);
  const vmCommands = [...new Set([...commandNames(vmCode), ...xamlCommands])];

  for (const command of vmCommands) {
    const handlerId = `handler:${screenName}|${command}`;
    addNode(nodes, handlerId, command, 'handler', 'ICommand', `${screenName}::${command}`);
    if (viewModelFile) addEdge(edges, edgeSeen, `viewmodel:${screenName}`, handlerId, 'binds command');
  }

  const servicesInVm = new Set([...constructorParams(vmCode, 'Service'), ...methodCallsToClasses(vmCode, serviceClasses)]);
  const repositoriesInVm = new Set([...constructorParams(vmCode, 'Repository'), ...methodCallsToClasses(vmCode, repositoryClasses)]);
  const usesNavigation = /NavigationService|INavigationService|\.Navigate|\.Show\(|new\s+[A-Za-z_][A-Za-z0-9_]*View\b/.test(vmCode);

  for (const service of servicesInVm) {
    const sid = service.toLowerCase().includes('navigation') ? 'service:navigation' : `service:${service}`;
    addNode(nodes, sid, service.toLowerCase().includes('navigation') ? 'NavigationService' : service, service.toLowerCase().includes('navigation') ? 'navigation' : 'service', 'Application/Services');
    for (const command of vmCommands.length ? vmCommands : ['ViewModel']) {
      addEdge(edges, edgeSeen, command === 'ViewModel' ? `viewmodel:${screenName}` : `handler:${screenName}|${command}`, sid, service.toLowerCase().includes('navigation') ? 'uses navigation' : 'calls service');
    }
  }
  if (usesNavigation && ![...servicesInVm].some((s) => s.toLowerCase().includes('navigation'))) {
    addNode(nodes, 'service:navigation', 'NavigationService', 'navigation', 'Application/Navigation');
    for (const command of vmCommands) addEdge(edges, edgeSeen, `handler:${screenName}|${command}`, 'service:navigation', 'uses navigation');
  }

  for (const repo of repositoriesInVm) {
    addNode(nodes, `repository:${repo}`, repo, 'repository', 'Infrastructure/Repositories');
    addEdge(edges, edgeSeen, `viewmodel:${screenName}`, `repository:${repo}`, 'direct repository');
  }

  for (const serviceFile of serviceFiles) {
    const service = classNameFromFile(serviceFile);
    if (service.startsWith('I')) continue;
    const code = readIfExists(serviceFile);
    const serviceId = service.toLowerCase().includes('navigation') ? 'service:navigation' : `service:${service}`;
    const serviceType = service.toLowerCase().includes('navigation') ? 'navigation' : 'service';
    addNode(nodes, serviceId, serviceType === 'navigation' ? 'NavigationService' : service, serviceType, path.relative(sourceRoot, serviceFile));

    for (const repo of new Set([...constructorParams(code, 'Repository'), ...methodCallsToClasses(code, repositoryClasses)])) {
      addNode(nodes, `repository:${repo}`, repo, 'repository', 'Infrastructure/Repositories');
      addEdge(edges, edgeSeen, serviceId, `repository:${repo}`, 'uses repository');
    }
  }

  for (const repoFile of repositoryFiles) {
    const repo = classNameFromFile(repoFile);
    if (repo.startsWith('I')) continue;
    addNode(nodes, `repository:${repo}`, repo, 'repository', path.relative(sourceRoot, repoFile));
  }

  const nodeList = [...nodes.values()];
  const countType = (type: string) => nodeList.filter((node) => node.data.type === type).length;
  return {
    nodes: nodeList,
    edges,
    files,
    stats: {
      nodes: nodeList.length,
      edges: edges.length,
      views: countType('view'),
      viewmodels: countType('viewmodel'),
      handlers: countType('handler'),
      services: countType('service'),
      repositories: countType('repository'),
      navigation: countType('navigation'),
    },
  };
}
