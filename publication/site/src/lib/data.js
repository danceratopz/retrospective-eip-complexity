import fs from 'node:fs';
import path from 'node:path';

const dataPath = path.resolve(process.cwd(), 'public/generated/publication.json');
let cached = null;

export function loadPublication() {
  if (!cached) cached = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
  return cached;
}

export function basePath(value = '') {
  const normalized = value.replace(/^\/+/, '');
  return `/retrospective-eip-complexity/${normalized}`;
}
