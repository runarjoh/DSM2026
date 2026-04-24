import { useMemo } from "react";

interface Props {
  matrix: number[][];
  units: string[];
  binary?: boolean; // true for consolidation (0/1), false for frequency (continuous)
  consolOverlay?: number[][] | null; // when set, use blue fill for consolidation cells
  groups?: number[] | null; // cluster assignments — draws cluster rectangles and labels
}

const FREQ_COLORS = [
  "#EEEFFE", "#D8DCFC", "#B5BCF7", "#919CF2",
  "#6E7DED", "#5B6EF7", "#3B4FE4", "#2D3DB8",
];

function freqColor(value: number, max: number): string {
  if (max === 0) return FREQ_COLORS[0];
  const idx = Math.min(Math.floor((value / max) * (FREQ_COLORS.length - 1)), FREQ_COLORS.length - 1);
  return FREQ_COLORS[idx];
}

export default function Heatmap({ matrix, units, binary = false, consolOverlay = null, groups = null }: Props) {
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

  // Extra space above the grid for rotated column labels (text rotated 90° extends straight up)
  const colLabelExtent = Math.ceil(maxLabelLen * labelFontSize * 0.55);
  const topPad = Math.max(0, colLabelExtent - labelMargin + 10);
  const svgW = labelMargin + n * cellSize;
  const svgH = labelMargin + topPad + n * cellSize;

  return (
    <div className="overflow-auto" style={{ paddingTop: topPad > 0 ? 0 : undefined }}>
      <svg viewBox={`0 0 ${svgW} ${svgH}`} width="100%" overflow="visible" className="mx-auto">
        <g transform={`translate(0, ${topPad})`}>
        {/* Column labels (top, rotated 90deg — matching matplotlib) */}
        {units.map((u, i) => (
          <text
            key={`col-${i}`}
            x={labelMargin + i * cellSize + cellSize / 2}
            y={labelMargin - 4}
            fontSize={labelFontSize}
            fill="#111111"
            textAnchor="start"
            dominantBaseline="central"
            transform={`rotate(-90, ${labelMargin + i * cellSize + cellSize / 2}, ${labelMargin - 4})`}
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
            fill="#111111"
            textAnchor="end"
          >
            {u}
          </text>
        ))}

        {/* Cells */}
        {matrix.map((row, r) =>
          row.map((val, c) => {
            const isDiag = r === c;
            const hasConsol = consolOverlay && !isDiag && consolOverlay[r]?.[c] === 1;
            let fill = "#ffffff";
            if (isDiag) {
              fill = "#e0e0e0";
            } else if (consolOverlay) {
              // Combined mode: blue fill for consolidation, white for no consolidation
              fill = hasConsol ? "#3B4FE4" : "#ffffff";
            } else if (binary) {
              fill = val === 1 ? "#3B4FE4" : "#ffffff";
            } else {
              // Frequency-only mode: color gradient
              if (val > 0) fill = freqColor(val, maxVal);
            }

            // Text color: white on blue, #333333 on white (matching matplotlib)
            const onBlue = consolOverlay
              ? hasConsol
              : (binary && val === 1) || (!binary && val / maxVal > 0.5);
            const textColor = onBlue ? "#ffffff" : "#333333";

            return (
              <g key={`${r}-${c}`}>
                <rect
                  x={labelMargin + c * cellSize}
                  y={labelMargin + r * cellSize}
                  width={cellSize}
                  height={cellSize}
                  fill={fill}
                  stroke="#f0f0f0"
                  strokeWidth={0.25}
                />
                {!isDiag && val > 0 && cellSize >= 18 && (
                  <text
                    x={labelMargin + c * cellSize + cellSize / 2}
                    y={labelMargin + r * cellSize + cellSize / 2 + fontSize / 3}
                    fontSize={fontSize}
                    fill={textColor}
                    textAnchor="middle"
                  >
                    {val % 1 === 0 ? val : val.toFixed(1)}
                  </text>
                )}
              </g>
            );
          })
        )}

        {/* Cluster rectangles and labels */}
        {groups && (() => {
          const clusterStart: Record<number, number> = {};
          const clusterEnd: Record<number, number> = {};
          groups.forEach((g, i) => {
            if (!(g in clusterStart)) clusterStart[g] = i;
            clusterEnd[g] = i;
          });
          const clusterIds = Object.keys(clusterStart).map(Number).sort((a, b) => a - b);
          const lw = Math.max(1.2, Math.min(2.0, 14.0 / n));
          const clblFs = Math.max(6, Math.min(10, 100.0 / n));
          return clusterIds.map((g) => {
            const s = clusterStart[g];
            const e = clusterEnd[g];
            const cx = labelMargin + (s + e) / 2 * cellSize + cellSize / 2;
            const cy = labelMargin + (s + e) / 2 * cellSize + cellSize / 2;
            return (
              <g key={`cluster-${g}`}>
                <rect
                  x={labelMargin + s * cellSize}
                  y={labelMargin + s * cellSize}
                  width={(e - s + 1) * cellSize}
                  height={(e - s + 1) * cellSize}
                  fill="none"
                  stroke="#111111"
                  strokeWidth={lw}
                />
                <rect
                  x={cx - clblFs * 1.2}
                  y={cy - clblFs * 0.7}
                  width={clblFs * 2.4}
                  height={clblFs * 1.4}
                  fill="white"
                  fillOpacity={0.75}
                  rx={2}
                />
                <text
                  x={cx}
                  y={cy + clblFs * 0.3}
                  fontSize={clblFs}
                  fontWeight="bold"
                  fill="#222222"
                  textAnchor="middle"
                >
                  G{g}
                </text>
              </g>
            );
          });
        })()}
        </g>
      </svg>

      {/* Legend */}
      <div className="flex justify-center items-center gap-1 mt-3 text-xs text-gray-500">
        {binary || consolOverlay ? (
          <>
            <div className="w-4 h-3 rounded-sm" style={{ background: "#3B4FE4" }} />
            <span>Consolidation potential</span>
            <div className="w-4 h-3 bg-white border border-gray-300 rounded-sm ml-2" />
            <span>No consolidation potential</span>
          </>
        ) : (
          <>
            <span>Low</span>
            {FREQ_COLORS.filter((_, i) => i % 2 === 0).map((c, i) => (
              <div key={i} className="w-4 h-3 rounded-sm" style={{ background: c }} />
            ))}
            <span>High</span>
          </>
        )}
      </div>
    </div>
  );
}
