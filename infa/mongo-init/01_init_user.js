db = db.getSiblingDB('admin');
db.createUser({
  user: 'vba_brain',
  pwd: 'vba_brain2024',
  roles: [{ role: 'root', db: 'admin' }]
});
db = db.getSiblingDB('vba_brain_core');
db.createCollection('_init');
print('vba_brain MongoDB init complete');
