import client from './client'

export const getHealth = async () => {
  const response = await client.get('/health')
  return response.data
}

export const getStats = async () => {
  const response = await client.get('/admin/stats')
  return response.data
}

export const getCorpusHealth = async () => {
  const response = await client.get('/admin/corpus-health')
  return response.data
}

export const getBenchmarkTrend = async () => {
  const response = await client.get('/admin/benchmark-trend')
  return response.data
}

export const getPendingApprovals = async () => {
  const response = await client.get('/admin/pending-approvals')
  return response.data
}

export const approveRepair = async (approvalId, decision, reason = '') => {
  const response = await client.post(
    `/admin/approve-repair/${approvalId}`,
    { decision, reason }
  )
  return response.data
}

export const getLatestBenchmark = async () => {
  const response = await client.get('/admin/latest-benchmark')
  return response.data
}
