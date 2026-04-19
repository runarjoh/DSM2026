import { useMemo } from "react";

interface Props {
  matrix: number[][];
  units: string[];
  binary?: boolean; // true for consolidation (0/1), false for frequency (continuous)
  consolOverlay?: number[][] | null; // when set, draw consolidation borders on top of frequency colors
}

const FREQ_COLORS = [
  "#eff6ff", "#dbeafe", "#bfdbfe", "#93c5fd",
  "#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8",
];

function freqColor(value: number, max: number): string {
  if (max === 0) return FREQ_COLORS[0];
  const idx = Math.min(Math.floor((value / max) * (FREQ_COLORS.length - 1)), FREQ_COLORS.length - 1);
  return FREQ_COLORS[idx];
}

export default function Heatmap({ matrix, units, binary = false, consolOverlay = null }: Props) {
  const n = units.length;

  const maxVal = useMemo(() => {
    if (binary) return 1;
    let m = 0;
    for (let r = 0; r < n; r++)
      for (let c = 0; c < n; c++)
        if (r !== c && matrix[r][c] > m) m = matrix[r][c];
    return m;
  }, [matrix, n, binary]);

  // Scale cell size and font based on matrix dimension
  const cellSize = n <= 16 ? 28 : n <= 24 ? 22 : n <= 32 ? 18 : 14;
  const fontSize = n <= 16 ? 10 : n <= 24 ? 8 : n <= 32 ? 7 : 6;
  const labelFontSize = n <= 16 ? 11 : n <= 24 ? 9 : n <= 32 ? 7 : 6;
  // Estimate label margin from longest unit name (~0.55 chars per px at given font size)
  const maxLabelLen = useMemo(() => Math.max(...units.map((u) => u.length)), [units]);
  const labelMargin = Math.max(70, Math.ceil(maxLabelLen * labelFontSize * 0.55) + 10);

  // Extra space above the grid for rotated column labels (text rotated -45° extends upward and left)
  const colLabelExtent = Math.ceil(maxLabelLen * labelFontSize * 0.55 * Math.sin(Math.PI / 4));
  const topPad = Math.max(0, colLabelExtent - labelMargin + 10);
  const svgW = labelMargin + n * cellSize;
  const svgH = labelMargin + topPad + n * cellSize;

  return (
    <div className="overflow-auto" style={{ paddingTop: topPad > 0 ? 0 : undefined }}>
      <svg width={svgW} height={svgH} overflow="visible" className="mx-auto">
        <g transform={`translate(0, ${topPad})`}>
        {/* Column labels (top, rotated 45deg) */}
        {units.map((u, i) => (
          <text
            key={`col-${i}`}
            x={labelMargin + i * cellSize + cellSize / 2}
            y={labelMargin - 4}
            fontSize={labelFontSize}
            fill="#374151"
            textAnchor="start"
            transform={`rotate(-45, ${labelMargin + i * cellSize + cellSize / 2}, ${labelMargin - 4})`}
          >
            {u}
          </text>
        ))}

        {/* Row labels (left) */}
        {units.map((u, i) => (
          <text
            key={`row-${i}`}
            x={labelMargin - 4}
            y={labelMargin + i * cellSize + cellSize / 2 + fontSize / 3}
            fontSize={labelFontSize}
            fill="#374151"
            textAnchor="end"
          >
            {u}
          </text>
        ))}

        {/* Cells */}
        {matrix.map((row, r) =>
          row.map((val, c) => {
            const isDiag = r === c;
            let fill = "#f8fafc";
            if (isDiag) {
              fill = "#d1d5db";
            } else if (binary) {
              fill = val === 1 ? "#3b82f6" : "#f8fafc";
            } else if (val > 0) {
              fill = freqColor(val, maxVal);
            }

            return (
              <g key={`${r}-${c}`}>
                <rect
                  x={labelMargin + c * cellSize}
                  y={labelMargin + r * cellSize}
                  width={cellSize}
                  height={cellSize}
                  fill={fill}
                  stroke="#e5e7eb"
                  strokeWidth={0.5}
                />
                {!isDiag && !binary && val > 0 && cellSize >= 18 && (
                  <text
                    x={labelMargin + c * cellSize + cellSize / 2}
                    y={labelMargin + r * cellSize + cellSize / 2 + fontSize / 3}
                    fontSize={fontSize}
                    fill={val / maxVal > 0.5 ? "#ffffff" : "#6b7280"}
                    textAnchor="middle"
                  >
                    {val % 1 === 0 ? val : val.toFixed(1)}
                  </text>
                )}
                {/* Consolidation overlay border */}
                {consolOverlay && !isDiag && consolOverlay[r]?.[c] === 1 && (
                  <rect
                    x={labelMargin + c * cellSize + 1}
                    y={labelMargin + r * cellSize + 1}
                    width={cellSize - 2}
                    height={cellSize - 2}
                    fill="none"
                    stroke="#f97316"
                    strokeWidth={2}
                    rx={1}
                  />
                )}
              </g>
            );
          })
        )}
        </g>
      </svg>

      {/* Legend */}
      <div className="flex justify-center items-center gap-1 mt-3 text-xs text-gray-500">
        {binary ? (
          <>
            <div className="w-4 h-3 bg-gray-50 border border-gray-200 rounded-sm" />
            <span>No potential</span>
            <div className="w-4 h-3 bg-blue-500 rounded-sm ml-2" />
            <span>Consolidation potential</span>
          </>
        ) : (
          <>
            <span>Low</span>
            {FREQ_COLORS.filter((_, i) => i % 2 === 0).map((c, i) => (
              <div key={i} className="w-4 h-3 rounded-sm" style={{ background: c }} />
            ))}
            <span>High</span>
            {consolOverlay && (
              <>
                <span className="ml-3">|</span>
                <div className="w-4 h-3 rounded-sm border-2 border-orange-500 ml-1" />
                <span>Consolidation potential</span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
