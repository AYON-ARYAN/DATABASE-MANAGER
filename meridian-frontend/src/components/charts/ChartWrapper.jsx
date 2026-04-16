import { useRef, useEffect } from 'react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, ArcElement,
  PointElement, Title, Tooltip, Legend, Filler
} from 'chart.js'
import { Bar, Line, Pie, Doughnut } from 'react-chartjs-2'
import { CHART_COLORS } from '../../lib/constants'

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement, ArcElement,
  PointElement, Title, Tooltip, Legend, Filler
)

const commonOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#a1a1aa', font: { size: 11 } }
    },
    tooltip: {
      backgroundColor: 'rgba(0,0,0,0.8)',
      borderColor: 'rgba(255,255,255,0.1)',
      borderWidth: 1,
      titleColor: '#f4f4f5',
      bodyColor: '#a1a1aa',
      cornerRadius: 8,
      padding: 10,
    }
  },
  scales: {
    x: {
      ticks: { color: '#71717a', font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.04)' },
      border: { color: 'rgba(255,255,255,0.06)' },
    },
    y: {
      ticks: { color: '#71717a', font: { size: 10 } },
      grid: { color: 'rgba(255,255,255,0.04)' },
      border: { color: 'rgba(255,255,255,0.06)' },
    }
  }
}

const pieOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'right',
      labels: { color: '#a1a1aa', font: { size: 11 }, padding: 12, usePointStyle: true }
    },
    tooltip: commonOptions.plugins.tooltip,
  }
}

function buildDataset(labels, data, chartType) {
  const colors = labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length])
  const colorsAlpha = colors.map(c => c + '30')

  if (chartType === 'pie' || chartType === 'doughnut') {
    return {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderColor: 'rgba(9,9,11,0.8)',
        borderWidth: 2,
      }]
    }
  }

  if (chartType === 'line' || chartType === 'area') {
    return {
      labels,
      datasets: [{
        label: 'Value',
        data,
        borderColor: CHART_COLORS[0],
        backgroundColor: CHART_COLORS[0] + '20',
        fill: chartType === 'area',
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: CHART_COLORS[0],
      }]
    }
  }

  return {
    labels,
    datasets: [{
      label: 'Value',
      data,
      backgroundColor: colorsAlpha,
      borderColor: colors,
      borderWidth: 1.5,
      borderRadius: 6,
    }]
  }
}

export default function ChartWrapper({ type = 'bar', labels = [], data = [], height = 300, rawConfig }) {
  const chartData = rawConfig || buildDataset(labels, data, type)
  const opts = (type === 'pie' || type === 'doughnut')
    ? pieOptions
    : commonOptions

  const ChartComponent = { bar: Bar, line: Line, pie: Pie, doughnut: Doughnut, area: Line }[type] || Bar

  return (
    <div style={{ height }}>
      <ChartComponent data={chartData} options={opts} />
    </div>
  )
}
