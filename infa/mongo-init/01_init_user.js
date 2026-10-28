// Runs once, on the first start with an empty data volume.
// The root account comes from MONGO_INITDB_ROOT_USERNAME / MONGO_INITDB_ROOT_PASSWORD
// (infa/.env) — never put credentials in this file.
db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || 'vba_brain_core');
db.createCollection('_init');
print('vba_brain MongoDB init complete');
