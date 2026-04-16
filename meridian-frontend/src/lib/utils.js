export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

export function formatNumber(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString()
}

export function truncate(str, len = 50) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

export function timeAgo(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
