interface FitnessComponent { weight: number; value: number }

interface FitnessStats {
  fitness: number;
  mdl: number;
  nClusters: number;
  components: Record<string, FitnessComponent>;
  freqWithin: number;
  freqOutside: number;
  consolWithin: number;
  consolOutside: number;
  bothWithin: number;
  bothOutside: number;
  noFreqWithin: number;
  noFreqOutside: number;
  noConsolWithin: number;
  noConsolOutside: number;
  blankWithin: number;
  blankOutside: number;
}

export type { FitnessStats };

function pct(n: number, d: number): string {
  if (d === 0) return "—";
  return (n / d * 100).toFixed(1) + "%";
}

function PctDelta({ now, before }: { now: number; before: number }) {
  const diff = now - before;
  if (Math.abs(diff) < 0.05) return <span style={{ color: "#8B92A5" }}>--</span>;
  const positive = diff > 0;
  return (
    <span style={{ color: positive ? "#16a34a" : "#dc2626" }}>
      {positive ? "+" : ""}{diff.toFixed(1)}pp
    </span>
  );
}

function NumDelta({ now, before, fmt }: { now: number; before: number; fmt?: (n: number) => string }) {
  const diff = now - before;
  if (Math.abs(diff) < 0.005) return <span style={{ color: "#8B92A5" }}>--</span>;
  const f = fmt || ((n: number) => n.toFixed(1));
  return (
    <span style={{ color: diff < 0 ? "#16a34a" : "#dc2626" }}>
      {diff > 0 ? "+" : ""}{f(diff)}
    </span>
  );
}

const COMPONENT_LABELS: Record<string, string> = {
  mdl: "MDL",
  freq_between: "Freq between",
  freq_gap: "Freq gap",
  consol_between: "Consol between",
  consol_gap: "Consol gap",
  size_imbalance: "Size imbalance",
  singleton_penalty: "Singleton penalty",
};

function computeRates(s: FitnessStats) {
  const totalWithinCells = s.freqWithin + s.noFreqWithin;
  const totalFreq = s.freqWithin + s.freqOutside;
  const totalConsol = s.consolWithin + s.consolOutside;
  const totalBoth = s.bothWithin + s.bothOutside;

  return {
    freqCapture: totalFreq > 0 ? s.freqWithin / totalFreq * 100 : 0,
    consolCapture: totalConsol > 0 ? s.consolWithin / totalConsol * 100 : 0,
    bothCapture: totalBoth > 0 ? s.bothWithin / totalBoth * 100 : 0,
    density: totalWithinCells > 0 ? s.freqWithin / totalWithinCells * 100 : 0,
    alignment: totalWithinCells > 0 ? s.consolWithin / totalWithinCells * 100 : 0,
    noise: totalWithinCells > 0 ? s.blankWithin / totalWithinCells * 100 : 0,
  };
}

export default function StatsTable({ stats, beforeStats, showCounts = false, freqThreshold = 0 }: { stats: FitnessStats; beforeStats?: FitnessStats | null; showCounts?: boolean; freqThreshold?: number }) {
  const hasBefore = beforeStats != null;
  const mono = { fontFamily: "'JetBrains Mono', monospace" };

  const rates = computeRates(stats);
  const prevRates = hasBefore ? computeRates(beforeStats) : null;

  const fitnessDelta = hasBefore ? stats.fitness - beforeStats.fitness : 0;
  const fitnessPct = hasBefore && beforeStats.fitness !== 0
    ? ((fitnessDelta / beforeStats.fitness) * 100).toFixed(1)
    : null;

  const rateRows = [
    { label: "Freq capture", desc: "Interactions within clusters", value: rates.freqCapture, prev: prevRates?.freqCapture },
    { label: "Consol capture", desc: "Consol potential within clusters", value: rates.consolCapture, prev: prevRates?.consolCapture },
    { label: "Both capture", desc: "Freq + consol within clusters", value: rates.bothCapture, prev: prevRates?.bothCapture },
    { label: "Cluster density", desc: "Within-cluster pairs with interactions", value: rates.density, prev: prevRates?.density },
    { label: "Cluster alignment", desc: "Within-cluster pairs with consol potential", value: rates.alignment, prev: prevRates?.alignment },
    { label: "Cluster noise", desc: "Within-cluster pairs that are empty", value: rates.noise, prev: prevRates?.noise },
  ];

  const componentKeys = Object.keys(stats.components);
  const prevComponents = hasBefore ? beforeStats.components : null;

  const countRows = [
    { label: "Interaction freq", within: stats.freqWithin, outside: stats.freqOutside, bWithin: beforeStats?.freqWithin },
    { label: "Consol potential", within: stats.consolWithin, outside: stats.consolOutside, bWithin: beforeStats?.consolWithin },
    { label: "Freq + consol", within: stats.bothWithin, outside: stats.bothOutside, bWithin: beforeStats?.bothWithin },
    { label: "No interaction", within: stats.noFreqWithin, outside: stats.noFreqOutside, bWithin: beforeStats?.noFreqWithin },
    { label: "No consol potential", within: stats.noConsolWithin, outside: stats.noConsolOutside, bWithin: beforeStats?.noConsolWithin },
    { label: "Empty", within: stats.blankWithin, outside: stats.blankOutside, bWithin: beforeStats?.blankWithin },
  ];

  return (
    <div className="mt-4 rounded-lg border overflow-hidden" style={{ borderColor: "#E2E5EB", background: "#FAFBFC" }}>
      {/* Header with fitness */}
      <div className="px-4 py-2.5 flex items-center justify-between" style={{ borderBottom: "1px solid #E2E5EB" }}>
        <div className="flex items-center gap-3">
          <span
            className="text-xs font-semibold tracking-wide uppercase"
            style={{ color: "#8B92A5", fontFamily: "'Plus Jakarta Sans', sans-serif", letterSpacing: "0.06em" }}
          >
            Cluster Statistics
          </span>
          {freqThreshold > 0 && (
            <span className="text-[10px] tabular-nums px-1.5 py-0.5 rounded" style={{ ...mono, color: "#6366f1", background: "#eef2ff" }}>
              freq &ge; {freqThreshold}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="text-xs" style={{ color: "#8B92A5" }}>Clusters</span>
            <span className="text-sm font-bold tabular-nums" style={{ ...mono, color: "#1A1D26" }}>
              {stats.nClusters}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs" style={{ color: "#8B92A5" }}>MDL</span>
            <span className="text-sm font-bold tabular-nums" style={{ ...mono, color: "#1A1D26" }}>
              {stats.mdl.toFixed(1)}
            </span>
            {hasBefore && (
              <span className="text-xs tabular-nums" style={{ ...mono, color: beforeStats.mdl > stats.mdl ? "#16a34a" : beforeStats.mdl < stats.mdl ? "#dc2626" : "#8B92A5" }}>
                ({stats.mdl < beforeStats.mdl ? "" : "+"}{(stats.mdl - beforeStats.mdl).toFixed(1)})
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {hasBefore && (
              <span className="text-xs tabular-nums" style={{ ...mono, color: "#8B92A5" }}>
                {beforeStats.fitness.toFixed(2)}
                <span className="mx-1" style={{ color: "#C0C4D0" }}>&rarr;</span>
              </span>
            )}
            <span className="text-xs" style={{ color: "#8B92A5" }}>Fitness</span>
            <span className="text-sm font-bold tabular-nums" style={{ ...mono, color: "#1A1D26" }}>
              {stats.fitness.toFixed(2)}
            </span>
            {hasBefore && fitnessPct && (
              <span
                className="text-xs font-semibold tabular-nums px-1.5 py-0.5 rounded"
                style={{
                  ...mono,
                  color: fitnessDelta <= 0 ? "#16a34a" : "#dc2626",
                  background: fitnessDelta <= 0 ? "#f0fdf4" : "#fef2f2",
                }}
              >
                {fitnessDelta <= 0 ? "" : "+"}{fitnessPct}%
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Fitness decomposition */}
      <table className="w-full text-xs" style={{ borderCollapse: "separate", borderSpacing: 0 }}>
        <thead>
          <tr style={{ background: "#F3F4F8" }}>
            <th className="text-left font-medium px-4 py-1.5" style={{ color: "#8B92A5" }}>Fitness component</th>
            <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Weight</th>
            {hasBefore && (
              <>
                <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Before</th>
                <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>&Delta;</th>
              </>
            )}
            <th className="text-right font-medium px-4 py-1.5" style={{ color: "#8B92A5" }}>Value</th>
          </tr>
        </thead>
        <tbody>
          {componentKeys.map((key, i) => {
            const comp = stats.components[key];
            const prev = prevComponents?.[key];
            const pctOfTotal = stats.fitness > 0 ? (comp.value / stats.fitness * 100).toFixed(0) : "0";
            return (
              <tr
                key={key}
                style={{
                  background: i % 2 === 0 ? "#FFFFFF" : "#FAFBFC",
                  borderBottom: i < componentKeys.length - 1 ? "1px solid #F0F1F4" : undefined,
                }}
              >
                <td className="px-4 py-1.5 font-medium" style={{ color: "#4A4F63" }}>
                  {COMPONENT_LABELS[key] || key}
                </td>
                <td className="text-right px-3 py-1.5 tabular-nums" style={{ ...mono, color: "#8B92A5" }}>
                  {(comp.weight * 100).toFixed(1)}%
                </td>
                {hasBefore && (
                  <>
                    <td className="text-right px-3 py-1.5 tabular-nums" style={{ ...mono, color: "#8B92A5" }}>
                      {prev ? prev.value.toFixed(1) : "—"}
                    </td>
                    <td className="text-right px-3 py-1.5 tabular-nums font-medium" style={mono}>
                      {prev ? <NumDelta now={comp.value} before={prev.value} /> : "—"}
                    </td>
                  </>
                )}
                <td className="text-right px-4 py-1.5 tabular-nums font-semibold" style={{ ...mono, color: "#1A1D26" }}>
                  {comp.value.toFixed(1)}
                  <span className="font-normal ml-1" style={{ color: "#A0A5B8" }}>({pctOfTotal}%)</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Divider */}
      <div style={{ borderTop: "1px solid #E2E5EB" }} />

      {/* Rates table */}
      <table className="w-full text-xs" style={{ borderCollapse: "separate", borderSpacing: 0 }}>
        <thead>
          <tr style={{ background: "#F3F4F8" }}>
            <th className="text-left font-medium px-4 py-1.5" style={{ color: "#8B92A5" }}>Rate</th>
            {hasBefore && (
              <>
                <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Before</th>
                <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>&Delta;</th>
              </>
            )}
            <th className="text-right font-medium px-4 py-1.5" style={{ color: "#8B92A5" }}>Value</th>
          </tr>
        </thead>
        <tbody>
          {rateRows.map((r, i) => (
            <tr
              key={r.label}
              style={{
                background: i % 2 === 0 ? "#FFFFFF" : "#FAFBFC",
                borderBottom: i < rateRows.length - 1 ? "1px solid #F0F1F4" : undefined,
              }}
            >
              <td className="px-4 py-1.5">
                <div className="font-medium" style={{ color: "#4A4F63" }}>{r.label}</div>
                <div className="text-[10px]" style={{ color: "#A0A5B8" }}>{r.desc}</div>
              </td>
              {hasBefore && r.prev != null && (
                <>
                  <td className="text-right px-3 py-1.5 tabular-nums" style={{ ...mono, color: "#8B92A5" }}>
                    {r.prev.toFixed(1)}%
                  </td>
                  <td className="text-right px-3 py-1.5 tabular-nums font-medium" style={mono}>
                    <PctDelta now={r.value} before={r.prev} />
                  </td>
                </>
              )}
              {hasBefore && r.prev == null && (
                <>
                  <td /><td />
                </>
              )}
              <td className="text-right px-4 py-1.5 tabular-nums font-semibold" style={{ ...mono, color: "#1A1D26" }}>
                {r.value.toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showCounts && <>
      {/* Divider */}
      <div style={{ borderTop: "1px solid #E2E5EB" }} />

      {/* Counts table */}
      <table className="w-full text-xs" style={{ borderCollapse: "separate", borderSpacing: 0 }}>
        <thead>
          <tr style={{ background: "#F3F4F8" }}>
            <th className="text-left font-medium px-4 py-1.5" style={{ color: "#8B92A5" }}>Cell count</th>
            {hasBefore && (
              <>
                <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Prev In</th>
                <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>&Delta; In</th>
              </>
            )}
            <th className="text-right font-medium px-3 py-1.5" style={{ color: "#3B82C4" }}>Within</th>
            <th className="text-right font-medium px-3 py-1.5" style={{ color: "#A0785C" }}>Outside</th>
            <th className="text-right font-medium px-4 py-1.5" style={{ color: "#8B92A5" }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {countRows.map((r, i) => {
            const total = r.within + r.outside;
            const prevWithin = r.bWithin ?? null;
            const deltaWithin = prevWithin != null ? r.within - prevWithin : null;
            return (
              <tr
                key={r.label}
                style={{
                  background: i % 2 === 0 ? "#FFFFFF" : "#FAFBFC",
                  borderBottom: i < countRows.length - 1 ? "1px solid #F0F1F4" : undefined,
                }}
              >
                <td className="px-4 py-1.5 font-medium" style={{ color: "#4A4F63" }}>{r.label}</td>
                {hasBefore && (
                  <>
                    <td className="text-right px-3 py-1.5 tabular-nums" style={{ ...mono, color: "#8B92A5" }}>
                      {prevWithin}
                    </td>
                    <td className="text-right px-3 py-1.5 tabular-nums font-medium" style={mono}>
                      {deltaWithin != null && deltaWithin !== 0 ? (
                        <span style={{ color: deltaWithin > 0 ? "#16a34a" : "#dc2626" }}>
                          {deltaWithin > 0 ? "+" : ""}{deltaWithin}
                        </span>
                      ) : <span style={{ color: "#8B92A5" }}>--</span>}
                    </td>
                  </>
                )}
                <td className="text-right px-3 py-1.5 tabular-nums" style={{ ...mono, color: "#2B6CB0" }}>{r.within}</td>
                <td className="text-right px-3 py-1.5 tabular-nums" style={{ ...mono, color: "#9C6644" }}>{r.outside}</td>
                <td className="text-right px-4 py-1.5 tabular-nums font-semibold" style={{ ...mono, color: "#1A1D26" }}>{total}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </>}
    </div>
  );
}
