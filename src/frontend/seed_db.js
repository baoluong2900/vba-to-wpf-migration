/**
 * seed_db.js — Seed Layer 1 JSON files from database_json/ into MongoDB.
 *
 * Rules:
 *   - Reads all *.json and *.jsonl files from each subfolder
 *   - UPSERT only (no deleteMany — never wipes existing data)
 *   - Skips .gitkeep and non-json files
 *   - Folder name = collection name
 *   - Only processes folders that actually exist
 *
 * Usage:
 *   node seed_db.js
 *   node seed_db.js --dry-run       (list files, no write)
 *   node seed_db.js --only forms    (single folder)
 */

const fs   = require('fs');
const path = require('path');
const { MongoClient } = require('mongodb');

// ── Args ──────────────────────────────────────────────────────────────────────
const isDryRun  = process.argv.includes('--dry-run');
const onlyIdx   = process.argv.indexOf('--only');
const onlyFolder = onlyIdx !== -1 ? process.argv[onlyIdx + 1] : null;

// ── Config ────────────────────────────────────────────────────────────────────
let config;
try {
    const configPath = path.join(__dirname, '../config.json');
    config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
} catch (err) {
    console.error('❌ Cannot read config.json:', err.message);
    process.exit(1);
}

const uri    = config.mongodb.uri;
const dbName = config.mongodb.db;

// ── Base dir ──────────────────────────────────────────────────────────────────
const baseDir = path.join(__dirname, '../database_json');

// ── Helpers ───────────────────────────────────────────────────────────────────
function cleanLargeFields(obj) {
    if (!obj || typeof obj !== 'object') return;
    for (const key of Object.keys(obj)) {
        const lower = key.toLowerCase();
        if (lower === 'picturedata' || lower === 'picturedata_base64') {
            delete obj[key];
        } else if (typeof obj[key] === 'string' && obj[key].length > 500_000) {
            delete obj[key]; // drop strings > 500 KB
        } else if (typeof obj[key] === 'object') {
            cleanLargeFields(obj[key]);
        }
    }
}

function parseFile(filePath) {
    const raw = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '');
    if (filePath.endsWith('.jsonl')) {
        const merged = {};
        for (const line of raw.split('\n').filter(l => l.trim())) {
            try { Object.assign(merged, JSON.parse(line)); }
            catch { /* skip bad line */ }
        }
        return merged;
    }
    return JSON.parse(raw);
}

function getRecordName(data, fileStem) {
    return data.name
        || data.screen_id
        || data.form_name
        || data.screen_name
        || data.query_name
        || data.table_name
        || data.macro_name
        || data.module_name
        || fileStem;
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function seed() {
    // Discover folders automatically
    const allFolders = fs.readdirSync(baseDir, { withFileTypes: true })
        .filter(e => e.isDirectory())
        .map(e => e.name);

    const folders = onlyFolder
        ? allFolders.filter(f => f === onlyFolder)
        : allFolders;

    if (folders.length === 0) {
        console.log('No folders found in', baseDir);
        return;
    }

    if (isDryRun) {
        console.log('[DRY-RUN] Would seed these folders →', folders.join(', '));
    }

    const client = new MongoClient(uri);
    try {
        if (!isDryRun) {
            console.log('Connecting to MongoDB...');
            await client.connect();
            console.log('Connected.\n');
        }

        const db = isDryRun ? null : client.db(dbName);
        let totalOk = 0, totalSkip = 0, totalErr = 0;

        for (const folderName of folders) {
            const folderPath = path.join(baseDir, folderName);
            const collectionName = folderName;   // folder name = collection name

            const files = fs.readdirSync(folderPath)
                .filter(f => (f.endsWith('.json') || f.endsWith('.jsonl')) && f !== '.gitkeep');

            console.log(`📂 [${collectionName}] ${files.length} file(s)`);

            if (isDryRun) {
                files.forEach(f => console.log(`   • ${f}`));
                totalOk += files.length;
                continue;
            }

            const col = db.collection(collectionName);
            let ok = 0, skip = 0, err = 0;

            for (const file of files) {
                const filePath = path.join(folderPath, file);
                const stem     = path.basename(file, path.extname(file));
                try {
                    const data = parseFile(filePath);
                    if (!data || Object.keys(data).length === 0) { skip++; continue; }

                    const recordName = getRecordName(data, stem);
                    if (!data.name) data.name = recordName;

                    cleanLargeFields(data);

                    await col.updateOne(
                        { name: recordName },
                        { $set: data },
                        { upsert: true }
                    );
                    ok++;
                } catch (e) {
                    console.error(`   ❌ ${file}: ${e.message}`);
                    err++;
                }
            }

            console.log(`   ✅ upserted=${ok}  skipped=${skip}  errors=${err}`);
            totalOk += ok; totalSkip += skip; totalErr += err;
        }

        console.log(`\n🎉 Done — upserted=${totalOk}  skipped=${totalSkip}  errors=${totalErr}`);

    } finally {
        if (!isDryRun) await client.close();
    }
}

seed().catch(err => { console.error('Fatal:', err); process.exit(1); });
