export type LogicCodeStatus = 'DONE' | 'TODO' | 'SKIP' | 'ERROR';

export type LogicSummary = {
  done: number;
  todo: number;
  skip: number;
  error: number;
  compile_ok: boolean;
};

type MethodOutput = { status?: string; code?: unknown };

/** Status of one entry of agent_logic.py's method_outputs.json. */
export function logicCodeStatus(method: MethodOutput): LogicCodeStatus {
  if (method.status === 'skipped') return 'SKIP';
  if (method.status === 'error') return 'ERROR';
  if (typeof method.code === 'string' && /\bTODO\b|NotImplementedException/.test(method.code)) return 'TODO';
  return 'DONE';
}

/** compile_ok means the run exited cleanly with nothing left to review (no errors, no TODOs). */
export function summarizeLogicMethods(methods: MethodOutput[], exitCode: number): LogicSummary {
  const counts = { done: 0, todo: 0, skip: 0, error: 0 };
  for (const method of methods) {
    const status = logicCodeStatus(method);
    if (status === 'DONE') counts.done++;
    else if (status === 'TODO') counts.todo++;
    else if (status === 'SKIP') counts.skip++;
    else counts.error++;
  }
  return { ...counts, compile_ok: exitCode === 0 && counts.error === 0 && counts.todo === 0 };
}
