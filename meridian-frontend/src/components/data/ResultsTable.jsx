import { useState } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'

export default function ResultsTable({ columns = [], rows = [], maxHeight = '400px' }) {
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  if (!columns.length) return null

  const handleSort = (idx) => {
    if (sortCol === idx) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(idx)
      setSortDir('asc')
    }
  }

  const sortedRows = sortCol !== null
    ? [...rows].sort((a, b) => {
        const va = a[sortCol]
        const vb = b[sortCol]
        const na = Number(va), nb = Number(vb)
        if (!isNaN(na) && !isNaN(nb)) return sortDir === 'asc' ? na - nb : nb - na
        return sortDir === 'asc'
          ? String(va).localeCompare(String(vb))
          : String(vb).localeCompare(String(va))
      })
    : rows

  return (
    <div className="overflow-auto rounded-lg border border-white/[0.06]" style={{ maxHeight }}>
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="bg-white/[0.04]">
            {columns.map((col, i) => (
              <th
                key={i}
                onClick={() => handleSort(i)}
                className="px-3 py-2.5 text-left text-xs font-semibold text-zinc-300 cursor-pointer hover:text-white select-none whitespace-nowrap border-b border-white/[0.06]"
              >
                <span className="flex items-center gap-1">
                  {col}
                  {sortCol === i && (
                    sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, i) => (
            <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 text-zinc-300 whitespace-nowrap max-w-xs truncate">
                  {cell === null ? <span className="text-zinc-600 italic">NULL</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
