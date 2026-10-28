/**
 * Static checks for converted SQL. Nothing is executed: the console has no PostgreSQL
 * execution path, so this only catches problems visible in the text itself — leftover Access
 * syntax and broken quoting. Error codes are the PostgreSQL SQLSTATE the server would raise.
 */

export interface StaticCheckResult {
  success: boolean;
  /** Always true: tells the UI no rows/rowcount exist because nothing ran. */
  preview: true;
  message?: string;
  error_code?: string;
  error_message?: string;
}

const SYNTAX_ERROR = '42601';
const UNDEFINED_FUNCTION = '42883';

const ACCESS_FUNCTION =
  /\b(DLOOKUP|DCOUNT|DSUM|DMAX|DMIN|DAVG|DFIRST|DLAST|IIF|NZ|MID|INSTR|LEN|CSTR|CINT|CLNG|CDBL|CDATE)\s*\(/i;

const ACCESS_SYNTAX: { pattern: RegExp; message: string }[] = [
  { pattern: /\bDISTINCTROW\b/i, message: 'DISTINCTROW is Access-only — use DISTINCT.' },
  { pattern: /\bSELECT\s+(DISTINCT\s+)?TOP\s+\d+/i, message: 'SELECT TOP n is not PostgreSQL — use LIMIT n.' },
  { pattern: /#\d{1,4}[-/]\d{1,2}[-/]\d{1,4}#/, message: "Access #date# literal — use a quoted literal such as DATE '2024-01-31'." },
  { pattern: /\[[^\]]+\]\s*!\s*\[/, message: 'Access form reference ([Forms]![…]) — replace it with a bind variable.' },
];

/** Replace comments and string literals with blanks; flag an unterminated literal. */
function stripCommentsAndLiterals(sql: string): { code: string; unterminated: boolean } {
  let code = '';
  let i = 0;
  while (i < sql.length) {
    const ch = sql[i];
    const next = sql[i + 1];
    if (ch === '-' && next === '-') {
      const end = sql.indexOf('\n', i);
      i = end === -1 ? sql.length : end;
      code += ' ';
    } else if (ch === '/' && next === '*') {
      const end = sql.indexOf('*/', i + 2);
      i = end === -1 ? sql.length : end + 2;
      code += ' ';
    } else if (ch === "'") {
      let j = i + 1;
      while (j < sql.length && !(sql[j] === "'" && sql[j + 1] !== "'")) {
        j += sql[j] === "'" ? 2 : 1; // '' is an escaped quote
      }
      if (j >= sql.length) return { code, unterminated: true };
      code += "''";
      i = j + 1;
    } else {
      code += ch;
      i += 1;
    }
  }
  return { code, unterminated: false };
}

function failure(error_code: string, error_message: string): StaticCheckResult {
  return { success: false, preview: true, error_code, error_message };
}

export function staticSqlCheck(sql: string): StaticCheckResult {
  if (!sql || !sql.trim()) {
    return failure(SYNTAX_ERROR, 'The target SQL is empty.');
  }

  const { code, unterminated } = stripCommentsAndLiterals(sql);
  if (unterminated) {
    return failure(SYNTAX_ERROR, 'Unterminated quoted string.');
  }

  let depth = 0;
  for (const ch of code) {
    if (ch === '(') depth += 1;
    if (ch === ')' && --depth < 0) break;
  }
  if (depth !== 0) {
    return failure(SYNTAX_ERROR, 'Unbalanced parentheses.');
  }

  const fn = code.match(ACCESS_FUNCTION);
  if (fn) {
    return failure(
      UNDEFINED_FUNCTION,
      `Access function ${fn[1].toUpperCase()}() does not exist in PostgreSQL — use COALESCE, CASE WHEN, SUBSTRING, POSITION, LENGTH or CAST.`,
    );
  }
  for (const rule of ACCESS_SYNTAX) {
    if (rule.pattern.test(code)) return failure(SYNTAX_ERROR, rule.message);
  }

  return {
    success: true,
    preview: true,
    message: 'Static check passed: no Access-only syntax found. The query was not executed — no PostgreSQL connection is configured for the console.',
  };
}
