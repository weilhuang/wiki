import test from 'node:test'
import assert from 'node:assert/strict'
import { groupExperimentRecords } from '../scripts/experiment-records.mjs'

test('Shared experiment groups retain all executions, versions and downloadable artifacts', () => {
  const first = { record: { id: 'lab.model', resourceGroup: 'lab' }, e: { scope: ['model'], notCovered: ['cluster'], versions: ['Python 3.12'], artifacts: [] } }
  const second = { record: { id: 'lab.runtime', resourceGroup: 'lab' }, e: { scope: ['loopback'], notCovered: ['cluster', 'load'], versions: ['Linux'], artifacts: [{ path: 'examples/lab.zip', sha256: 'a' }, { path: 'examples/results.txt', sha256: 'b' }] } }
  const [group] = groupExperimentRecords([first, second])
  assert.deepEqual(group.ids, ['lab.model', 'lab.runtime'])
  assert.deepEqual(group.e.scope, ['model', 'loopback'])
  assert.deepEqual(group.e.notCovered, ['cluster', 'load'])
  assert.deepEqual(group.e.versions, ['Python 3.12', 'Linux'])
  assert.equal(group.e.artifacts.length, 2)
  assert.deepEqual(first.e.artifacts, [], 'grouping must not mutate the evidence registry')
  assert.deepEqual(groupExperimentRecords([first]), [], 'a downloads section must not invent an empty download entry')
  assert.throws(() => groupExperimentRecords([second, { ...second, e: { ...second.e, artifacts: [{ path: 'examples/lab.zip', sha256: 'different' }] } }]), /Conflicting lab artifact/)
})
