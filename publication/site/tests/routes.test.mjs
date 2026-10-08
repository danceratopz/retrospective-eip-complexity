import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/routes.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const routes = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

const original = 'hegota:2488:llm:r2';
const updated = `${original}:hegota-2026-09-16-abcdef0`;

test('two evaluations of the same EIP survive comparison URL round trips', () => {
  const url = new URL(routes.compareRoute({ assessments: [original, updated], order: 'stable' }), 'https://example.test');
  const state = routes.parseCompareState(url.search);
  assert.deepEqual(state.assessments, [original, updated]);
  assert.equal(state.order, 'stable');
});

test('detail links select an immutable evaluation and keep legacy rubric links valid', () => {
  const url = new URL(routes.eipRoute(2488, { fork: 'hegota', view: 'llm', assessment: updated }), 'https://example.test');
  assert.equal(url.pathname, '/retrospective-eip-complexity/eips/2488/');
  assert.equal(routes.parseEipViewState(url.search).assessment, updated);
  assert.equal(routes.parseEipViewState('?fork=amsterdam&view=llm&rubric=1').rubric, 1);
});

test('comparison parser rejects malformed IDs without discarding original IDs', () => {
  assert.deepEqual(routes.parseCompareState(`?a=${original},${original},${updated},hegota:2488:llm:r2:../bad`).assessments, [original, updated]);
});
