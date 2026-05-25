#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { makeReport, validateFile } = require("./wpf-graph-validator");

function argValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

async function readInput() {
  const file = argValue("--file");
  const url = argValue("--url");

  if (file) {
    return {
      source: file,
      report: validateFile(path.resolve(process.cwd(), file), {}),
    };
  }

  if (url) {
    const res = await fetch(url);
    const json = await res.json();
    return {
      source: url,
      report: makeReport(json, {}),
    };
  }

  throw new Error("Usage: node scripts/test-wpf-graph.js --file <graph.json> OR --url <api-url>");
}

function writeReport(source, report) {
  const out = argValue("--out");
  const payload = {
    source,
    generatedAt: new Date().toISOString(),
    ...report,
  };

  const text = JSON.stringify(payload, null, 2);
  if (out) {
    fs.mkdirSync(path.dirname(path.resolve(process.cwd(), out)), { recursive: true });
    fs.writeFileSync(path.resolve(process.cwd(), out), text, "utf-8");
  }
  console.log(text);
}

readInput()
  .then(({ source, report }) => {
    writeReport(source, report);
    process.exit(report.success ? 0 : 1);
  })
  .catch((err) => {
    const report = {
      success: false,
      summary: { errors: 1, warnings: 0, nodes: 0, edges: 0 },
      errors: [{ rule: "runner", message: err.message }],
      warnings: [],
    };
    writeReport("runner", report);
    process.exit(1);
  });
