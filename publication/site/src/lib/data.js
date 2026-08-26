import fs from 'node:fs';
import path from 'node:path';

const dataPath = path.resolve(process.cwd(), 'public/generated/publication.json');

export function loadPublication() {
  return JSON.parse(fs.readFileSync(dataPath, 'utf8'));
}

export function basePath(value = '') {
  const normalized = value.replace(/^\/+/, '');
  return `/retrospective-complexity-eval/${normalized}`;
}
