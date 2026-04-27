import { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar,
} from "recharts";
import Heatmap from "./Heatmap";
import StatsTable, { type FitnessStats } from "./StatsTable";
import { preprocessMatrix } from "../utils/preprocess";

interface ProgressPoint {
  gen: number;
  avg: number;
  min: number;
  max: number;
}

interface TrialPoint {
  trial: number;
  value: number;
  best: number;
}

interface ResultData {
  fitness?: number;
  mdl?: number;
  nClusters?: number;
  components?: Record<string, { weight: number; value: number }>;
  freqWithin?: number;
  freqOutside?: number;
  consolWithin?: number;
  consolOutside?: number;
  bothWithin?: number;
  bothOutside?: number;
  noFreqWithin?: number;
  noFreqOutside?: number;
  noConsolWithin?: number;
  noConsolOutside?: number;
  blankWithin?: number;
  blankOutside?: number;
  resultPath?: string;
  figurePath?: string;
  configFigurePath?: string;
  statsFigurePath?: string;
  bestParams?: Record<string, number | string>;
  resultFreq?: number[][];
  resultConsol?: number[][];
  resultUnits?: string[];
  resultGroups?: number[];
}

interface SensitivityResult {
  importances?: Record<string, number>;
  source?: string;
  robustness?: { runs: {run: number; fitness: number}[]; meanFitness: number; stdFitness: number; minFitness: number; maxFitness: number; ariMean: number };
  sweeps?: Record<string, {value: number; fitness: number; nClusters: number}[]>;
  logPath?: string;
}

interface SensitivityProgressPoint {
  label: string;
  run: number;
  total: number;
  fitness: number;
}

interface PreviewData {
  freqMatrix: number[][];
  consolMatrix: number[][];
  units: string[];
  groups: number[] | null;
  fitnessStats: FitnessStats | null;
}

interface ResultEntry {
  filename: string;
  type: string;
  date: string;
  n_clusters: number | null;
  n_units: number | null;
  fitness: number | null;
  has_figure: boolean;
  display_name: string;
  sensitivity?: boolean;
}

interface Props {
  status: "idle" | "running" | "done" | "error" | "cancelled";
  phase: "idle" | "tune" | "optimize";
  progressData: ProgressPoint[];
  trialData: TrialPoint[];
  result: ResultData | null;
  error: string | null;
  sensitivityType?: "importance" | "robustness" | "sweep" | null;
  sensitivityProgress?: SensitivityProgressPoint[];
  sensitivityResult?: SensitivityResult | null;
  preprocessMode?: string;
  freqThreshold?: number;
  preview?: PreviewData | null;
  resultsList?: ResultEntry[];
  activeResultFile?: string | null;
  onLoadResult?: (filename: string) => void;
  onRenameResult?: (filename: string, name: string) => void;
}

export default function Results({ status, phase, progressData, trialData, result, error, sensitivityType, sensitivityProgress = [], sensitivityResult, preprocessMode = "normalize", freqThreshold = 0, preview = null, resultsList = [], activeResultFile = null, onLoadResult, onRenameResult }: Props) {
  const [resultView, setResultView] = useState<"freq" | "consol" | "combined">("combined");
  const [showPreprocessed, setShowPreprocessed] = useState(true);
  const [showBefore, setShowBefore] = useState(false);
  const [showCounts, setShowCounts] = useState(false);

  const displayResultFreq = useMemo(() => {
    if (!result?.resultFreq || !showPreprocessed) return result?.resultFreq;
    return preprocessMatrix(result.resultFreq, preprocessMode as "normalize" | "binary", freqThreshold);
  }, [result?.resultFreq, showPreprocessed, preprocessMode, freqThreshold]);

  const displayPreviewFreq = useMemo(() => {
    if (!preview?.freqMatrix || !showPreprocessed) return preview?.freqMatrix;
    return preprocessMatrix(preview.freqMatrix, preprocessMode as "normalize" | "binary", freqThreshold);
  }, [preview?.freqMatrix, showPreprocessed, preprocessMode, freqThreshold]);

  const hasData = progressData.length > 0 || trialData.length > 0 || sensitivityProgress.length > 0 || status === "done" || status === "error" || status === "cancelled" || sensitivityResult != null;

  return (
    <section className={`bg-white rounded-rc border p-6 shadow-rc ${!hasData ? "opacity-50" : ""}`} style={{ borderColor: "#EBEEF3" }}>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold" style={{ background: status === "done" ? "#00D9A5" : hasData ? "#3B4FE4" : "#8B92A5" }}>
          4
        </span>
        <h2 className="text-base font-semibold font-heading" style={{ color: "#1A1D26" }}>Results</h2>
        {status === "running" && phase === "tune" && (
          <span className="text-xs font-medium ml-2" style={{ color: "#3B4FE4" }}>Phase 1: Tuning</span>
        )}
        {status === "running" && phase === "optimize" && (
          <span className="text-xs font-medium ml-2" style={{ color: "#3B4FE4" }}>Phase 2: Optimizing</span>
        )}
        {status === "running" && sensitivityType === "importance" && (
          <span className="text-xs font-medium ml-2" style={{ color: "#3B4FE4" }}>
            Running importance analysis{trialData.length > 0 ? ` — ${trialData.length} trials` : ""}
          </span>
        )}
        {status === "running" && sensitivityType === "robustness" && sensitivityProgress.length > 0 && (
          <span className="text-xs font-medium ml-2" style={{ color: "#3B4FE4" }}>
            Robustness — {sensitivityProgress[sensitivityProgress.length - 1].label}
          </span>
        )}
        {status === "running" && sensitivityType === "sweep" && sensitivityProgress.length > 0 && (
          <span className="text-xs font-medium ml-2" style={{ color: "#3B4FE4" }}>
            Sweep — {sensitivityProgress[sensitivityProgress.length - 1].label}
          </span>
        )}
        {status === "done" && result?.fitness != null && (
          <span className="text-xs font-medium ml-auto" style={{ color: "#00B589" }}>
            Final fitness: {result.fitness.toFixed(4)}
          </span>
        )}
      </div>

      {!hasData && (
        <div className="border border-dashed border-gray-200 rounded-lg p-8 text-center text-sm text-gray-400">
          Progress chart, optimized DSM figure, and download links will appear here
        </div>
      )}

      {/* Trial chart (tuning) */}
      {trialData.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-semibold text-gray-500 mb-2">
            Tuning — {trialData.length} trials
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trialData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="trial" label={{ value: "Trial", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Fitness", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="value" stroke="#6366f1" dot={{ r: 2 }} name="Trial value" />
              <Line type="stepAfter" dataKey="best" stroke="#ef4444" dot={false} strokeWidth={2} name="Best so far" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Progress chart (optimization) */}
      {progressData.length > 0 && (
        <div className="mb-4">
          <div className="flex items-baseline gap-3 mb-2">
            <div className="text-xs font-semibold text-gray-500">
              Optimization — Generation {progressData[progressData.length - 1].gen}
            </div>
            <div className="text-sm font-mono ml-auto">
              <span className="text-gray-400">Best fitness: </span>
              <span className="text-red-600 font-bold">{Math.min(...progressData.map(p => p.min)).toFixed(4)}</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="gen" label={{ value: "Generation", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Fitness", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="avg" stroke="#000000" dot={false} name="Average" />
              <Line type="monotone" dataKey="min" stroke="#ef4444" dot={false} name="Minimum" />
              <Line type="monotone" dataKey="max" stroke="#22c55e" dot={false} name="Maximum" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Sensitivity progress (robustness / sweep) */}
      {sensitivityProgress.length > 0 && !sensitivityResult && (sensitivityType === "robustness" || sensitivityType === "sweep") && (
        <div className="mb-4">
          <div className="text-xs font-semibold text-gray-500 mb-2">
            {sensitivityType === "robustness" ? "Robustness Runs" : "Weight Sweep"} — {sensitivityProgress.length} / {sensitivityProgress[sensitivityProgress.length - 1].total} completed
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sensitivityProgress.map((p, i) => ({ index: i + 1, fitness: p.fitness, label: p.label }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="index" label={{ value: sensitivityType === "robustness" ? "Run" : "Step", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Fitness", angle: -90, position: "insideLeft" }} />
              <Tooltip content={({ payload }) => {
                if (!payload?.[0]) return null;
                const d = payload[0].payload as { label: string; fitness: number };
                return <div className="bg-white border border-gray-200 rounded p-2 text-xs shadow"><div className="font-medium">{d.label}</div><div>Fitness: {d.fitness.toFixed(2)}</div></div>;
              }} />
              <Bar dataKey="fitness" fill={sensitivityType === "robustness" ? "#6366f1" : "#3b82f6"} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Completion result */}
      {status === "done" && result && (
        <div className="border-t border-gray-200 pt-4 mt-2">
          {/* Best params from tuning */}
          {result.bestParams && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 mb-2">Best Parameters (Optuna)</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1">
                {Object.entries(result.bestParams).map(([k, v]) => (
                  <div key={k} className="text-sm">
                    <span className="text-gray-500">{k}:</span>{" "}
                    <span className="font-mono">{typeof v === "number" ? v.toFixed(4) : v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* DSM result with toggles */}
          {result.resultFreq && result.resultConsol && result.resultUnits && (
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="text-xs font-semibold" style={{ color: "#5A6178" }}>
                  {showBefore ? "Before Optimization" : "Optimized DSM"}
                </div>
                {preview && (
                  <button
                    className="text-xs px-2.5 py-1 rounded border transition-colors duration-200"
                    style={showBefore
                      ? { borderColor: "#f59e0b", background: "#fffbeb", color: "#d97706" }
                      : { borderColor: "#E2E5EB", color: "#5A6178" }}
                    onClick={() => setShowBefore(!showBefore)}
                  >
                    {showBefore ? "Show After" : "Show Before"}
                  </button>
                )}
              </div>
              <div className="flex items-center gap-1 mb-2 ml-8">
                <span className="text-xs text-gray-400 mr-1">Values:</span>
                {(["raw", "preprocessed"] as const).map((v) => (
                  <button
                    key={v}
                    className="text-xs px-2 py-0.5 rounded border transition-colors duration-200"
                    style={(v === "preprocessed") === showPreprocessed
                      ? { borderColor: "#10b981", background: "#ecfdf5", color: "#059669" }
                      : { borderColor: "#E2E5EB", color: "#5A6178" }}
                    onClick={() => setShowPreprocessed(v === "preprocessed")}
                  >
                    {v === "raw" ? "Raw" : "Preprocessed"}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1 mb-4 ml-8">
                <span className="text-xs text-gray-400 mr-1">Layer:</span>
                {(["freq", "consol", "combined"] as const).map((v) => (
                  <button
                    key={v}
                    className="text-xs px-2 py-0.5 rounded border transition-colors duration-200"
                    style={resultView === v ? { borderColor: "#3B4FE4", background: "#EEF0FD", color: "#3B4FE4" } : { borderColor: "#E2E5EB", color: "#5A6178" }}
                    onClick={() => setResultView(v)}
                  >
                    {v === "freq" ? "Frequency" : v === "consol" ? "Consolidation" : "Combined"}
                  </button>
                ))}
              </div>
              <Heatmap
                matrix={showBefore && preview
                  ? (resultView === "consol" ? preview.consolMatrix : (displayPreviewFreq || preview.freqMatrix))
                  : (resultView === "consol" ? result.resultConsol : (displayResultFreq || result.resultFreq))}
                units={showBefore && preview ? preview.units : result.resultUnits}
                binary={resultView === "consol" || (showPreprocessed && preprocessMode === "binary" && resultView === "freq")}
                consolOverlay={resultView === "combined" ? (showBefore && preview ? preview.consolMatrix : result.resultConsol) : null}
                groups={showBefore && preview ? preview.groups : result.resultGroups}
              />
              {result.fitness != null && result.freqWithin != null && (
                <>
                  <div className="flex items-center gap-1 mt-3 mb-1">
                    <button
                      className="text-xs px-2 py-0.5 rounded border transition-colors duration-200"
                      style={showCounts
                        ? { borderColor: "#3B4FE4", background: "#EEF0FD", color: "#3B4FE4" }
                        : { borderColor: "#E2E5EB", color: "#5A6178" }}
                      onClick={() => setShowCounts(!showCounts)}
                    >
                      {showCounts ? "Hide cell counts" : "Show cell counts"}
                    </button>
                  </div>
                  <StatsTable
                    stats={{
                      fitness: result.fitness,
                      mdl: result.mdl!, nClusters: result.nClusters!,
                      components: result.components!,
                      freqWithin: result.freqWithin!, freqOutside: result.freqOutside!,
                      consolWithin: result.consolWithin!, consolOutside: result.consolOutside!,
                      bothWithin: result.bothWithin!, bothOutside: result.bothOutside!,
                      noFreqWithin: result.noFreqWithin!, noFreqOutside: result.noFreqOutside!,
                      noConsolWithin: result.noConsolWithin!, noConsolOutside: result.noConsolOutside!,
                      blankWithin: result.blankWithin!, blankOutside: result.blankOutside!,
                    }}
                    beforeStats={preview?.fitnessStats}
                    showCounts={showCounts}
                    freqThreshold={freqThreshold}
                  />
                </>
              )}
            </div>
          )}

          {/* Downloads */}
          <div className="flex flex-wrap gap-3">
            {result.resultPath && (
              <a
                href={`/api/results/${result.resultPath}`}
                download
                className="text-sm text-blue-600 hover:underline"
              >
                Download Excel
              </a>
            )}
            {result.figurePath && (
              <a
                href={`/api/results/${result.figurePath}`}
                download
                className="text-sm text-blue-600 hover:underline"
              >
                Download DSM Figure
              </a>
            )}
            {result.statsFigurePath && (
              <a
                href={`/api/results/${result.statsFigurePath}`}
                download
                className="text-sm text-blue-600 hover:underline"
              >
                Download Statistics
              </a>
            )}
            {result.configFigurePath && (
              <a
                href={`/api/results/${result.configFigurePath}`}
                download
                className="text-sm text-blue-600 hover:underline"
              >
                Download Config
              </a>
            )}
          </div>
        </div>
      )}

      {/* Sensitivity results */}
      {status === "done" && sensitivityResult && (
        <div className="border-t border-gray-200 pt-4 mt-2">
          {/* Importance */}
          {sensitivityType === "importance" && sensitivityResult.importances && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 mb-1">
                Parameter Importance (fANOVA) — {sensitivityResult.source === "reused" ? "from previous tuning" : "from dedicated study"}
              </div>
              <p className="text-xs text-gray-400 mb-2">
                Shows which parameters have the most influence on fitness outcome. Higher scores mean changes to that parameter produce larger fitness differences.
              </p>
              <ResponsiveContainer width="100%" height={Math.max(200, Object.keys(sensitivityResult.importances).length * 35)}>
                <BarChart data={Object.entries(sensitivityResult.importances).map(([k, v]) => ({name: k, importance: v})).sort((a, b) => b.importance - a.importance)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 1]} />
                  <YAxis type="category" dataKey="name" width={120} tick={{fontSize: 11}} />
                  <Tooltip />
                  <Bar dataKey="importance" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Robustness */}
          {sensitivityType === "robustness" && sensitivityResult.robustness && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 mb-2">Robustness Analysis</div>
              <p className="text-xs text-gray-400 mb-2">
                Each bar shows the final fitness from an independent GA run with identical parameters. Low variance and high ARI (Adjusted Rand Index) indicate the GA converges to consistent clustering solutions.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                <div className="text-sm"><span className="text-gray-500">Mean:</span> <span className="font-mono">{sensitivityResult.robustness.meanFitness.toFixed(2)}</span></div>
                <div className="text-sm"><span className="text-gray-500">Std:</span> <span className="font-mono">{sensitivityResult.robustness.stdFitness.toFixed(2)}</span></div>
                <div className="text-sm"><span className="text-gray-500">Min:</span> <span className="font-mono">{sensitivityResult.robustness.minFitness.toFixed(2)}</span></div>
                <div className="text-sm"><span className="text-gray-500">Max:</span> <span className="font-mono">{sensitivityResult.robustness.maxFitness.toFixed(2)}</span></div>
              </div>
              <div className="text-sm mb-3"><span className="text-gray-500">Mean ARI (cluster stability):</span> <span className="font-mono">{sensitivityResult.robustness.ariMean.toFixed(4)}</span></div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={sensitivityResult.robustness.runs}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="run" label={{value: "Run", position: "insideBottom", offset: -5}} />
                  <YAxis label={{value: "Fitness", angle: -90, position: "insideLeft"}} />
                  <Tooltip />
                  <Bar dataKey="fitness" fill="#6366f1" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Sweep */}
          {sensitivityType === "sweep" && sensitivityResult.sweeps && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 mb-2">Weight Sensitivity Sweep</div>
              <p className="text-xs text-gray-400 mb-2">
                Each chart varies one fitness weight while holding the others constant. Blue line shows the composite fitness (lower is better). Orange line shows the number of clusters in the optimal solution. Steep fitness curves indicate the result is sensitive to that weight.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(sensitivityResult.sweeps).map(([weight, data]) => (
                  <div key={weight}>
                    <div className="text-xs font-medium text-gray-600 mb-1">{weight}</div>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="value" tickFormatter={(v: number) => v.toFixed(2)} tick={{fontSize: 10}} />
                        <YAxis yAxisId="fitness" label={{value: "Fitness", angle: -90, position: "insideLeft"}} tick={{fontSize: 10}} />
                        <YAxis yAxisId="clusters" orientation="right" label={{value: "Clusters", angle: 90, position: "insideRight"}} tick={{fontSize: 10}} domain={[0, "auto"]} />
                        <Tooltip formatter={(v: number, name: string) => [name === "nClusters" ? v : v.toFixed(1), name === "nClusters" ? "Clusters" : "Fitness"]} />
                        <Legend />
                        <Line yAxisId="fitness" type="monotone" dataKey="fitness" stroke="#3b82f6" dot={{r: 3}} strokeWidth={1.5} name="Fitness" />
                        <Line yAxisId="clusters" type="stepAfter" dataKey="nClusters" stroke="#f97316" dot={{r: 2}} strokeWidth={1.5} strokeDasharray="4 2" name="Clusters" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ))}
              </div>
            </div>
          )}

          {sensitivityResult.logPath && (
            <div className="text-xs text-gray-400 mt-2">Results saved to: {sensitivityResult.logPath}</div>
          )}
        </div>
      )}

      {/* Previous results selector */}
      {resultsList.length > 0 && (
        <div className="border-t border-gray-200 pt-4 mt-4">
          <div className="text-xs font-semibold mb-2" style={{ color: "#5A6178" }}>Previous Results</div>
          <div className="rounded-lg border overflow-hidden" style={{ borderColor: "#E2E5EB", maxHeight: 200, overflowY: "auto" }}>
            <table className="w-full text-xs" style={{ borderCollapse: "separate", borderSpacing: 0 }}>
              <thead>
                <tr style={{ background: "#F3F4F8", position: "sticky", top: 0 }}>
                  <th className="text-left font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Name</th>
                  <th className="text-left font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Date</th>
                  <th className="text-left font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Type</th>
                  <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Fitness</th>
                  <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Clusters</th>
                  <th className="text-right font-medium px-3 py-1.5" style={{ color: "#8B92A5" }}>Units</th>
                  <th className="px-3 py-1.5" />
                </tr>
              </thead>
              <tbody>
                {resultsList.map((r, i) => {
                  const isActive = r.filename === activeResultFile;
                  return (
                    <tr
                      key={r.filename}
                      style={{
                        background: isActive ? "#EEF0FD" : i % 2 === 0 ? "#FFFFFF" : "#FAFBFC",
                        borderBottom: i < resultsList.length - 1 ? "1px solid #F0F1F4" : undefined,
                      }}
                    >
                      <td className="px-3 py-1">
                        <input
                          key={r.display_name}
                          className="text-xs w-full bg-transparent border-0 border-b outline-none py-0.5 px-0"
                          style={{ borderColor: r.display_name ? "transparent" : "#E2E5EB", color: "#4A4F63", minWidth: 80 }}
                          placeholder="Untitled"
                          defaultValue={r.display_name}
                          onFocus={(e) => { e.target.style.borderColor = "#3B4FE4"; }}
                          onBlur={(e) => {
                            e.target.style.borderColor = e.target.value ? "transparent" : "#E2E5EB";
                            if (e.target.value !== r.display_name) onRenameResult?.(r.filename, e.target.value);
                          }}
                          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                        />
                      </td>
                      <td className="px-3 py-1.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#4A4F63" }}>
                        {r.date}
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                          style={
                            r.type === "Tune + Optimize" ? { color: "#7c3aed", background: "#f5f3ff" }
                            : r.type === "Importance" ? { color: "#0d9488", background: "#f0fdfa" }
                            : r.type === "Robustness" ? { color: "#c2410c", background: "#fff7ed" }
                            : r.type === "Sweep" ? { color: "#4338ca", background: "#eef2ff" }
                            : { color: "#2563eb", background: "#eff6ff" }
                          }
                        >
                          {r.type}
                        </span>
                      </td>
                      <td className="text-right px-3 py-1.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#4A4F63" }}>
                        {r.fitness != null ? r.fitness.toFixed(1) : "—"}
                      </td>
                      <td className="text-right px-3 py-1.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#4A4F63" }}>
                        {r.n_clusters ?? "—"}
                      </td>
                      <td className="text-right px-3 py-1.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace", color: "#4A4F63" }}>
                        {r.n_units ?? "—"}
                      </td>
                      <td className="px-3 py-1.5">
                        {r.sensitivity ? (
                          <span className="text-[10px]" style={{ color: "#8B92A5" }}></span>
                        ) : isActive ? (
                          <span className="text-[10px] font-medium" style={{ color: "#3B4FE4" }}>Active</span>
                        ) : (
                          <button
                            className="text-[10px] px-2 py-0.5 rounded border transition-colors duration-200"
                            style={{ borderColor: "#E2E5EB", color: "#5A6178" }}
                            onClick={() => onLoadResult?.(r.filename)}
                          >
                            Load
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Error */}
      {status === "error" && error && (
        <div className="rounded-rc p-3 mt-2" style={{ background: "#F5F0FF", border: "1px solid #D4C4FF" }}>
          <p className="text-sm font-medium" style={{ color: "#5A3FCC" }}>Error</p>
          <pre className="text-xs mt-1 whitespace-pre-wrap font-mono" style={{ color: "#7C5CFF" }}>{error}</pre>
        </div>
      )}

      {/* Cancelled */}
      {status === "cancelled" && (
        <div className="rounded-rc p-3 mt-2" style={{ background: "#F1F3F7", border: "1px solid #E2E5EB" }}>
          <p className="text-sm" style={{ color: "#5A6178" }}>Run cancelled.</p>
        </div>
      )}
    </section>
  );
}
