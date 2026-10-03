/** Several executions can support one downloadable lab without losing their scope. */
export function groupExperimentRecords(entries) {
  const grouped = new Map()
  for (const { record, e } of entries) {
    const key = record.resourceGroup || record.id
    if (!grouped.has(key)) grouped.set(key, { record, e: { ...e, scope: [], notCovered: [], versions: [], artifacts: [] }, ids: [] })
    const group = grouped.get(key)
    group.ids.push(record.id)
    for (const field of ['scope', 'notCovered', 'versions']) group.e[field] = [...new Set([...group.e[field], ...(e[field] || [])])]
    for (const artifact of e.artifacts || []) {
      const existing = group.e.artifacts.find(item => item.path === artifact.path)
      if (existing && existing.sha256 !== artifact.sha256) throw new Error(`Conflicting lab artifact identity: ${artifact.path}`)
      if (!existing) group.e.artifacts.push({ ...artifact })
    }
  }
  return [...grouped.values()].filter(group => group.e.artifacts.length)
}
