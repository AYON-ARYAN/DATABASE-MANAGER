import { useState, useEffect, useMemo } from 'react'
import AppShell from '../components/layout/AppShell'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input, { Select } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ResultsTable from '../components/data/ResultsTable'
import { useDb } from '../context/DbContext'
import { useToast } from '../context/ToastContext'
import {
  getJoinSchema, suggestJoins, previewJoinSql, executeJoin
} from '../api/joinCenter'
import {
  GitMerge, Plus, Trash2, Play, Eye, AlertCircle, Sparkles,
  ChevronDown, ChevronRight, Filter, ArrowUpDown
} from 'lucide-react'

const JOIN_TYPES = ['INNER', 'LEFT', 'RIGHT', 'FULL', 'CROSS']
const ON_OPS = ['=', '!=']
const FILTER_OPS = ['=', '!=', '<', '<=', '>', '>=', 'LIKE', 'NOT LIKE', 'IN', 'IS NULL', 'IS NOT NULL']
const DIRS = ['ASC', 'DESC']

function coerceValue(v) {
  if (v === '' || v == null) return v
  const n = Number(v)
  if (!Number.isNaN(n) && v.toString().trim() !== '') return n
  return v
}

function makeEmptyCondition(leftTable = '', rightTable = '') {
  return { left_table: leftTable, left_column: '', right_table: rightTable, right_column: '', op: '=' }
}

function makeEmptyJoin() {
  return {
    table: '',
    type: 'INNER',
    alias: '',
    on: [makeEmptyCondition()],
    columns: null,
    allColumns: true,
    suggestBadge: null,
  }
}

function makeEmptyFilter() {
  return { table: '', column: '', op: '=', value: '' }
}

function makeEmptyOrderBy() {
  return { table: '', column: '', dir: 'ASC' }
}

function SectionHeader({ icon: Icon, title, subtitle, right }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2.5">
        {Icon && (
          <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <Icon className="w-3.5 h-3.5 text-blue-400" />
          </div>
        )}
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
          {subtitle && <p className="text-[11px] text-zinc-500">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  )
}

function ColumnPicker({ columns = [], allSelected, selected, onAllToggle, onToggle }) {
  if (!columns.length) {
    return <p className="text-xs text-zinc-500 italic">No columns discovered for this table.</p>
  }
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-zinc-500">{columns.length} columns</span>
        <button
          onClick={onAllToggle}
          className="text-[11px] text-blue-400 hover:text-blue-300 cursor-pointer"
        >
          {allSelected ? 'Select none' : 'Select all'}
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5 max-h-52 overflow-y-auto p-0.5">
        {columns.map(col => {
          const checked = allSelected || selected.includes(col.name)
          return (
            <label
              key={col.name}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md border cursor-pointer transition-colors ${
                checked
                  ? 'bg-blue-500/10 border-blue-500/30 text-zinc-200'
                  : 'bg-white/[0.02] border-white/5 text-zinc-400 hover:bg-white/5'
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(col.name)}
                className="accent-blue-500"
              />
              <span className="text-xs truncate flex-1">{col.name}</span>
              {col.type && <span className="text-[10px] text-zinc-600 truncate">{col.type}</span>}
            </label>
          )
        })}
      </div>
    </div>
  )
}

function JoinRow({
  join, index, schema, availableLeftTables, onChange, onRemove, onSuggest, suggestLoading
}) {
  const rightColumns = schema.tables.find(t => t.name === join.table)?.columns || []
  const isCross = join.type === 'CROSS'

  const updateOn = (i, patch) => {
    const next = [...join.on]
    next[i] = { ...next[i], ...patch }
    onChange({ ...join, on: next })
  }

  const addCondition = () => {
    onChange({
      ...join,
      on: [...join.on, makeEmptyCondition(availableLeftTables[0] || '', join.table)]
    })
  }

  const removeCondition = (i) => {
    const next = join.on.filter((_, idx) => idx !== i)
    onChange({ ...join, on: next.length ? next : [makeEmptyCondition()] })
  }

  const toggleColumn = (name) => {
    if (join.allColumns) {
      const rest = rightColumns.map(c => c.name).filter(n => n !== name)
      onChange({ ...join, allColumns: false, columns: rest })
    } else {
      const sel = join.columns || []
      const next = sel.includes(name) ? sel.filter(n => n !== name) : [...sel, name]
      const allBack = next.length === rightColumns.length
      onChange({ ...join, allColumns: allBack, columns: allBack ? null : next })
    }
  }

  const toggleAll = () => {
    if (join.allColumns) {
      onChange({ ...join, allColumns: false, columns: [] })
    } else {
      onChange({ ...join, allColumns: true, columns: null })
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 relative">
      <button
        onClick={onRemove}
        className="absolute top-3 right-3 p-1.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 transition-colors cursor-pointer"
        title="Remove join"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>

      <div className="flex items-center gap-2 mb-3">
        <span className="text-[11px] text-zinc-500 uppercase tracking-wider">Join #{index + 1}</span>
        {join.suggestBadge && (
          <span className={`text-[10px] px-2 py-0.5 rounded-md border ${
            join.suggestBadge === 'fk'
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
          }`}>
            {join.suggestBadge === 'fk' ? 'FK-based' : 'name-match'}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3 pr-10">
        <Select
          label="Type"
          value={join.type}
          onChange={e => {
            const type = e.target.value
            const on = type === 'CROSS' ? [] : (join.on.length ? join.on : [makeEmptyCondition()])
            onChange({ ...join, type, on })
          }}
          options={JOIN_TYPES.map(t => ({ label: t, value: t }))}
        />
        <Select
          label="Table"
          value={join.table}
          onChange={e => {
            const table = e.target.value
            const newOn = (join.on || []).map(c => ({ ...c, right_table: table }))
            onChange({ ...join, table, on: newOn, allColumns: true, columns: null, suggestBadge: null })
          }}
          options={[
            { label: 'Select table…', value: '' },
            ...schema.tables
              .filter(t => !availableLeftTables.includes(t.name) || t.name === join.table)
              .map(t => ({ label: t.name, value: t.name }))
          ]}
        />
        <Input
          label="Alias (optional)"
          value={join.alias || ''}
          onChange={e => onChange({ ...join, alias: e.target.value })}
          placeholder={join.table || 'alias'}
        />
      </div>

      {!isCross && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-zinc-400">ON Conditions</span>
            <Button
              variant="secondary"
              size="sm"
              onClick={onSuggest}
              loading={suggestLoading}
              disabled={!join.table || availableLeftTables.length === 0}
            >
              <Sparkles className="w-3 h-3" /> Auto-suggest
            </Button>
          </div>

          <div className="space-y-2">
            {join.on.map((c, i) => {
              const leftTableObj = schema.tables.find(t => t.name === c.left_table)
              const leftCols = leftTableObj?.columns || []
              const leftMissing = !c.left_column
              const rightMissing = !c.right_column
              const leftTableMissing = !c.left_table
              return (
                <div key={i} className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto_1fr_1fr_auto] gap-2 items-end">
                  <div>
                    <Select
                      label={i === 0 ? 'Left table' : ''}
                      value={c.left_table}
                      onChange={e => updateOn(i, { left_table: e.target.value, left_column: '' })}
                      options={[
                        { label: 'Table…', value: '' },
                        ...availableLeftTables.map(t => ({ label: t, value: t }))
                      ]}
                    />
                  </div>
                  <div>
                    <Select
                      label={i === 0 ? 'Left column' : ''}
                      value={c.left_column}
                      onChange={e => updateOn(i, { left_column: e.target.value })}
                      options={[
                        { label: 'Column…', value: '' },
                        ...leftCols.map(col => ({ label: col.name, value: col.name }))
                      ]}
                      disabled={!c.left_table}
                    />
                    {(leftMissing || leftTableMissing) && (
                      <p className="text-[10px] text-rose-400 mt-1">Pick a column</p>
                    )}
                  </div>
                  <div className="pb-0.5">
                    <Select
                      label={i === 0 ? 'Op' : ''}
                      value={c.op}
                      onChange={e => updateOn(i, { op: e.target.value })}
                      options={ON_OPS.map(o => ({ label: o, value: o }))}
                    />
                  </div>
                  <div>
                    <Select
                      label={i === 0 ? 'Right table' : ''}
                      value={c.right_table || join.table}
                      disabled
                      onChange={() => {}}
                      options={[{ label: join.table || '(table)', value: c.right_table || join.table }]}
                    />
                  </div>
                  <div>
                    <Select
                      label={i === 0 ? 'Right column' : ''}
                      value={c.right_column}
                      onChange={e => updateOn(i, { right_column: e.target.value })}
                      options={[
                        { label: 'Column…', value: '' },
                        ...rightColumns.map(col => ({ label: col.name, value: col.name }))
                      ]}
                      disabled={!join.table}
                    />
                    {rightMissing && (
                      <p className="text-[10px] text-rose-400 mt-1">Pick a column</p>
                    )}
                  </div>
                  <div className="pb-0.5">
                    <button
                      onClick={() => removeCondition(i)}
                      className="p-2 rounded-md bg-white/5 hover:bg-rose-500/10 text-zinc-400 hover:text-rose-400 transition-colors cursor-pointer"
                      title="Remove condition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          <button
            onClick={addCondition}
            className="mt-2 text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 cursor-pointer"
          >
            <Plus className="w-3 h-3" /> Add AND condition
          </button>
        </div>
      )}

      {join.table && (
        <div className="pt-3 border-t border-white/5">
          <p className="text-xs font-medium text-zinc-400 mb-2">Columns to include</p>
          <ColumnPicker
            columns={rightColumns}
            allSelected={join.allColumns}
            selected={join.columns || []}
            onAllToggle={toggleAll}
            onToggle={toggleColumn}
          />
        </div>
      )}
    </div>
  )
}

function FilterRow({ row, schema, tables, onChange, onRemove }) {
  const tableObj = schema.tables.find(t => t.name === row.table)
  const cols = tableObj?.columns || []
  const needsValue = row.op !== 'IS NULL' && row.op !== 'IS NOT NULL'
  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto_2fr_auto] gap-2 items-end">
      <Select
        label=""
        value={row.table}
        onChange={e => onChange({ ...row, table: e.target.value, column: '' })}
        options={[
          { label: 'Table…', value: '' },
          ...tables.map(t => ({ label: t, value: t }))
        ]}
      />
      <Select
        label=""
        value={row.column}
        onChange={e => onChange({ ...row, column: e.target.value })}
        options={[
          { label: 'Column…', value: '' },
          ...cols.map(c => ({ label: c.name, value: c.name }))
        ]}
        disabled={!row.table}
      />
      <Select
        label=""
        value={row.op}
        onChange={e => onChange({ ...row, op: e.target.value })}
        options={FILTER_OPS.map(o => ({ label: o, value: o }))}
      />
      {needsValue ? (
        <Input
          value={row.value}
          onChange={e => onChange({ ...row, value: e.target.value })}
          placeholder={row.op === 'IN' ? 'comma,separated,values' : 'value'}
        />
      ) : (
        <div className="text-xs text-zinc-500 px-3 py-2 italic">(no value)</div>
      )}
      <button
        onClick={onRemove}
        className="p-2 rounded-md bg-white/5 hover:bg-rose-500/10 text-zinc-400 hover:text-rose-400 transition-colors cursor-pointer"
        title="Remove filter"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

function OrderByRow({ row, schema, tables, onChange, onRemove }) {
  const tableObj = schema.tables.find(t => t.name === row.table)
  const cols = tableObj?.columns || []
  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto_auto] gap-2 items-end">
      <Select
        label=""
        value={row.table}
        onChange={e => onChange({ ...row, table: e.target.value, column: '' })}
        options={[
          { label: 'Table…', value: '' },
          ...tables.map(t => ({ label: t, value: t }))
        ]}
      />
      <Select
        label=""
        value={row.column}
        onChange={e => onChange({ ...row, column: e.target.value })}
        options={[
          { label: 'Column…', value: '' },
          ...cols.map(c => ({ label: c.name, value: c.name }))
        ]}
        disabled={!row.table}
      />
      <Select
        label=""
        value={row.dir}
        onChange={e => onChange({ ...row, dir: e.target.value })}
        options={DIRS.map(d => ({ label: d, value: d }))}
      />
      <button
        onClick={onRemove}
        className="p-2 rounded-md bg-white/5 hover:bg-rose-500/10 text-zinc-400 hover:text-rose-400 transition-colors cursor-pointer"
        title="Remove"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export default function JoinCenterPage() {
  const { activeDb, dbInfo } = useDb()
  const toast = useToast()

  const [schema, setSchema] = useState(null)
  const [schemaLoading, setSchemaLoading] = useState(true)
  const [schemaError, setSchemaError] = useState(null)

  const [baseTable, setBaseTable] = useState('')
  const [baseAllColumns, setBaseAllColumns] = useState(true)
  const [baseColumns, setBaseColumns] = useState([])
  const [joins, setJoins] = useState([])
  const [filters, setFilters] = useState([])
  const [orderBy, setOrderBy] = useState([])
  const [limit, setLimit] = useState(100)

  const [filtersOpen, setFiltersOpen] = useState(false)
  const [sortOpen, setSortOpen] = useState(false)

  const [previewSql, setPreviewSql] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [executeLoading, setExecuteLoading] = useState(false)
  const [runError, setRunError] = useState(null)
  const [result, setResult] = useState(null)
  const [suggestingIdx, setSuggestingIdx] = useState(null)

  // Fetch schema on mount and whenever activeDb changes.
  useEffect(() => {
    let cancelled = false
    setSchemaLoading(true)
    setSchemaError(null)
    setSchema(null)
    setBaseTable('')
    setJoins([])
    setFilters([])
    setOrderBy([])
    setBaseAllColumns(true)
    setBaseColumns([])
    setPreviewSql('')
    setResult(null)
    setRunError(null)
    ;(async () => {
      try {
        const data = await getJoinSchema()
        if (cancelled) return
        setSchema(data)
      } catch (err) {
        if (cancelled) return
        setSchemaError(err.response?.data?.error || 'Failed to load schema')
      } finally {
        if (!cancelled) setSchemaLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [activeDb])

  const baseTableObj = useMemo(
    () => schema?.tables?.find(t => t.name === baseTable) || null,
    [schema, baseTable]
  )

  const baseColumnsList = baseTableObj?.columns || []

  const declaredTablesUpTo = (upToIndex) => {
    const list = [baseTable].filter(Boolean)
    for (let i = 0; i < upToIndex; i++) {
      if (joins[i]?.table) list.push(joins[i].table)
    }
    return list
  }

  const allTables = useMemo(() => {
    const list = [baseTable].filter(Boolean)
    joins.forEach(j => { if (j.table) list.push(j.table) })
    return list
  }, [baseTable, joins])

  const handleBaseTableChange = (e) => {
    const t = e.target.value
    setBaseTable(t)
    setBaseAllColumns(true)
    setBaseColumns([])
    setJoins([])
    setFilters([])
    setOrderBy([])
    setPreviewSql('')
    setResult(null)
    setRunError(null)
  }

  const toggleBaseColumn = (name) => {
    if (baseAllColumns) {
      const rest = baseColumnsList.map(c => c.name).filter(n => n !== name)
      setBaseAllColumns(false)
      setBaseColumns(rest)
    } else {
      const next = baseColumns.includes(name)
        ? baseColumns.filter(n => n !== name)
        : [...baseColumns, name]
      if (next.length === baseColumnsList.length) {
        setBaseAllColumns(true)
        setBaseColumns([])
      } else {
        setBaseColumns(next)
      }
    }
  }

  const toggleAllBase = () => {
    if (baseAllColumns) {
      setBaseAllColumns(false)
      setBaseColumns([])
    } else {
      setBaseAllColumns(true)
      setBaseColumns([])
    }
  }

  const addJoin = () => {
    const j = makeEmptyJoin()
    j.on[0].left_table = baseTable
    setJoins([...joins, j])
  }

  const updateJoin = (i, next) => {
    const copy = [...joins]
    copy[i] = next
    setJoins(copy)
  }

  const removeJoin = (i) => {
    setJoins(joins.filter((_, idx) => idx !== i))
  }

  const handleSuggest = async (i) => {
    const j = joins[i]
    if (!j?.table || !baseTable) return
    setSuggestingIdx(i)
    try {
      const data = await suggestJoins(baseTable, j.table)
      const suggestions = data?.suggestions || []
      const splitRef = (ref, fallbackTable) => {
        if (typeof ref !== 'string' || !ref.includes('.')) return [fallbackTable, ref || '']
        const dot = ref.indexOf('.')
        return [ref.slice(0, dot), ref.slice(dot + 1)]
      }
      const conditions = suggestions.map(s => {
        const [lt, lc] = splitRef(s.left, baseTable)
        const [rt, rc] = splitRef(s.right, j.table)
        return { left_table: lt, left_column: lc, right_table: rt, right_column: rc, op: '=' }
      })
      if (conditions.length === 0) {
        toast.error('No join conditions could be inferred')
        return
      }
      const badge = suggestions[0]?.confidence || 'name-match'
      updateJoin(i, { ...j, on: conditions, suggestBadge: badge })
      toast.success(`Suggested ${conditions.length} condition${conditions.length > 1 ? 's' : ''}`)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Suggestion failed')
    } finally {
      setSuggestingIdx(null)
    }
  }

  const buildSpec = () => {
    const spec = {
      base_table: baseTable,
      base_columns: baseAllColumns ? null : baseColumns,
      joins: joins.map(j => ({
        table: j.table,
        type: j.type,
        alias: j.alias ? j.alias : null,
        on: j.type === 'CROSS' ? [] : j.on.map(c => ({
          left_table: c.left_table,
          left_column: c.left_column,
          right_table: c.right_table || j.table,
          right_column: c.right_column,
          op: c.op || '=',
        })),
        columns: j.allColumns ? null : (j.columns || []),
      })),
      filters: filters.length ? filters.map(f => ({
        table: f.table,
        column: f.column,
        op: f.op,
        value: f.op === 'IN'
          ? f.value.split(',').map(s => s.trim()).filter(Boolean)
          : (f.op === 'IS NULL' || f.op === 'IS NOT NULL' ? null : coerceValue(f.value))
      })) : null,
      order_by: orderBy.length ? orderBy.map(o => ({
        table: o.table, column: o.column, dir: o.dir
      })) : null,
      limit: Number(limit) || 100,
    }
    return spec
  }

  const isRunnable = useMemo(() => {
    if (!baseTable) return false
    for (const j of joins) {
      if (!j.table) return false
      if (j.type !== 'CROSS') {
        if (!j.on || j.on.length === 0) return false
        for (const c of j.on) {
          if (!c.left_table || !c.left_column || !c.right_column) return false
        }
      }
    }
    return true
  }, [baseTable, joins])

  const handlePreview = async () => {
    setRunError(null)
    setPreviewLoading(true)
    try {
      const data = await previewJoinSql(buildSpec())
      setPreviewSql(data?.sql || '')
    } catch (err) {
      const payload = err.response?.data || {}
      setRunError({ message: payload.error || 'Preview failed', sql: payload.sql || null })
      setPreviewSql('')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleExecute = async () => {
    setRunError(null)
    setExecuteLoading(true)
    try {
      const data = await executeJoin(buildSpec())
      setResult(data)
      if (data?.sql) setPreviewSql(data.sql)
    } catch (err) {
      const payload = err.response?.data || {}
      setRunError({ message: payload.error || 'Execute failed', sql: payload.sql || null })
    } finally {
      setExecuteLoading(false)
    }
  }

  // ---------- render ----------

  if (schemaLoading) {
    return (
      <AppShell wide>
        <div className="flex items-center justify-center py-24">
          <LoadingSpinner size="lg" />
        </div>
      </AppShell>
    )
  }

  if (schemaError || !schema) {
    const dialect = dbInfo?.display_type || 'this database'
    return (
      <AppShell wide>
        <Card className="border border-rose-500/20">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center flex-shrink-0">
              <AlertCircle className="w-5 h-5 text-rose-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">Joins not available</h2>
              <p className="text-sm text-zinc-400 mt-1">
                {schemaError
                  ? schemaError
                  : `Joins are not supported for ${dialect}.`}
              </p>
              <p className="text-xs text-zinc-500 mt-2">
                Switch to a SQL database (SQLite/MySQL/PostgreSQL/MSSQL/Oracle) from the Databases page to use Join Center.
              </p>
            </div>
          </div>
        </Card>
      </AppShell>
    )
  }

  const schemaTables = schema.tables || []

  return (
    <AppShell wide>
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <GitMerge className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Join Center</h1>
            <p className="text-sm text-zinc-500">
              Build reliable SQL joins across tables in the current database.
              {activeDb && (
                <span className="ml-2 text-zinc-400">
                  · <span className="text-zinc-300">{activeDb}</span>
                  {dbInfo?.display_type && (
                    <span className="ml-1 text-[11px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {dbInfo.display_type}
                    </span>
                  )}
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {/* Base Table */}
        <Card>
          <SectionHeader
            title="Base Table"
            subtitle="Starting point for the join"
            right={
              baseTableObj?.row_count != null && (
                <span className="text-[11px] text-zinc-500">
                  {Number(baseTableObj.row_count).toLocaleString()} rows
                </span>
              )
            }
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <Select
              label="Table"
              value={baseTable}
              onChange={handleBaseTableChange}
              options={[
                { label: 'Select a table…', value: '' },
                ...schemaTables.map(t => ({ label: t.name, value: t.name }))
              ]}
            />
          </div>
          {baseTable && (
            <div>
              <p className="text-xs font-medium text-zinc-400 mb-2">Columns to include</p>
              <ColumnPicker
                columns={baseColumnsList}
                allSelected={baseAllColumns}
                selected={baseColumns}
                onAllToggle={toggleAllBase}
                onToggle={toggleBaseColumn}
              />
            </div>
          )}
        </Card>

        {/* Joins */}
        <Card>
          <SectionHeader
            icon={GitMerge}
            title="Joins"
            subtitle="Attach additional tables with join conditions"
            right={
              <Button size="sm" variant="secondary" onClick={addJoin} disabled={!baseTable}>
                <Plus className="w-3.5 h-3.5" /> Add join
              </Button>
            }
          />
          {joins.length === 0 ? (
            <p className="text-xs text-zinc-500 italic">
              {baseTable
                ? 'No joins yet. Click "Add join" to attach another table.'
                : 'Pick a base table first.'}
            </p>
          ) : (
            <div className="space-y-3">
              {joins.map((j, i) => (
                <JoinRow
                  key={i}
                  index={i}
                  join={j}
                  schema={schema}
                  availableLeftTables={declaredTablesUpTo(i)}
                  onChange={(next) => updateJoin(i, next)}
                  onRemove={() => removeJoin(i)}
                  onSuggest={() => handleSuggest(i)}
                  suggestLoading={suggestingIdx === i}
                />
              ))}
            </div>
          )}
        </Card>

        {/* Filters (collapsible) */}
        <Card>
          <button
            onClick={() => setFiltersOpen(o => !o)}
            className="w-full flex items-center justify-between cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                <Filter className="w-3.5 h-3.5 text-blue-400" />
              </div>
              <div className="text-left">
                <h3 className="text-sm font-semibold text-zinc-200">Filters</h3>
                <p className="text-[11px] text-zinc-500">
                  Optional WHERE clauses · {filters.length} active
                </p>
              </div>
            </div>
            {filtersOpen ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
          </button>
          {filtersOpen && (
            <div className="mt-4 space-y-2">
              {filters.map((f, i) => (
                <FilterRow
                  key={i}
                  row={f}
                  schema={schema}
                  tables={allTables}
                  onChange={(next) => {
                    const copy = [...filters]
                    copy[i] = next
                    setFilters(copy)
                  }}
                  onRemove={() => setFilters(filters.filter((_, idx) => idx !== i))}
                />
              ))}
              <button
                onClick={() => setFilters([...filters, makeEmptyFilter()])}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 cursor-pointer"
                disabled={!baseTable}
              >
                <Plus className="w-3 h-3" /> Add filter
              </button>
            </div>
          )}
        </Card>

        {/* Sort & Limit */}
        <Card>
          <button
            onClick={() => setSortOpen(o => !o)}
            className="w-full flex items-center justify-between cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                <ArrowUpDown className="w-3.5 h-3.5 text-blue-400" />
              </div>
              <div className="text-left">
                <h3 className="text-sm font-semibold text-zinc-200">Sort & Limit</h3>
                <p className="text-[11px] text-zinc-500">
                  {orderBy.length} ORDER BY clause{orderBy.length === 1 ? '' : 's'} · LIMIT {limit || 100}
                </p>
              </div>
            </div>
            {sortOpen ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
          </button>
          {sortOpen && (
            <div className="mt-4 space-y-3">
              <div className="space-y-2">
                {orderBy.map((o, i) => (
                  <OrderByRow
                    key={i}
                    row={o}
                    schema={schema}
                    tables={allTables}
                    onChange={(next) => {
                      const copy = [...orderBy]
                      copy[i] = next
                      setOrderBy(copy)
                    }}
                    onRemove={() => setOrderBy(orderBy.filter((_, idx) => idx !== i))}
                  />
                ))}
                <button
                  onClick={() => setOrderBy([...orderBy, makeEmptyOrderBy()])}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 cursor-pointer"
                  disabled={!baseTable}
                >
                  <Plus className="w-3 h-3" /> Add sort
                </button>
              </div>
              <div className="max-w-xs">
                <Input
                  label="Limit"
                  type="number"
                  min={1}
                  max={1000}
                  value={limit}
                  onChange={e => setLimit(e.target.value)}
                />
              </div>
            </div>
          )}
        </Card>

        {/* Error banner */}
        {runError && (
          <Card className="border border-rose-500/30 bg-rose-500/[0.04]">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-rose-400 font-medium">{runError.message}</p>
                {runError.sql && (
                  <pre className="mt-2 text-xs text-zinc-400 bg-black/30 rounded-md p-2 overflow-x-auto font-mono">
                    {runError.sql}
                  </pre>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="secondary"
            onClick={handlePreview}
            loading={previewLoading}
            disabled={!isRunnable}
          >
            <Eye className="w-4 h-4" /> Preview SQL
          </Button>
          <Button
            variant="primary"
            onClick={handleExecute}
            loading={executeLoading}
            disabled={!isRunnable}
          >
            <Play className="w-4 h-4" /> Execute
          </Button>
        </div>

        {/* Preview SQL output */}
        {previewSql && (
          <Card>
            <SectionHeader title="Generated SQL" subtitle="Preview of the query that will run" />
            <pre className="text-sm text-purple-300 font-mono bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
              {previewSql}
            </pre>
          </Card>
        )}

        {/* Results */}
        {result && result.columns && (
          <Card>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-zinc-200">Results</h3>
                <p className="text-[11px] text-zinc-500">
                  {(result.row_count ?? result.rows?.length ?? 0).toLocaleString()} rows returned
                  {result.truncated && (
                    <span className="ml-2 text-amber-400">(truncated)</span>
                  )}
                </p>
              </div>
            </div>
            {result.rows?.length > 0 ? (
              <ResultsTable columns={result.columns} rows={result.rows} maxHeight="520px" />
            ) : (
              <p className="text-xs text-zinc-500 italic">No rows matched.</p>
            )}
          </Card>
        )}
      </div>
    </AppShell>
  )
}
