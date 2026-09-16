import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/labels.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { evaluationTimingLabel } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('unmerged human assessments show PR state, then a distinct publication date once merged', () => {
  const human = { source: 'human', status: 'available_in_open_pr', publication_date: '2026-09-16' };
  assert.equal(evaluationTimingLabel(human), 'Open PR');
  assert.equal(evaluationTimingLabel({ ...human, status: 'in_progress' }), 'Draft PR');
  assert.equal(evaluationTimingLabel({ ...human, status: 'complete' }), 'Published 2026-09-16');
  assert.equal(evaluationTimingLabel({ ...human, status: 'complete', publication_date: null }), 'Date not recorded');
  assert.equal(evaluationTimingLabel({ source: 'llm', status: 'complete', evaluation_date: '2026-09-16' }), '2026-09-16');
});
