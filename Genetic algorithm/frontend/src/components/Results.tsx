import {
  LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar,
} from "recharts";

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
  resultPath?: string;
  figurePath?: string;
  bestParams?: Record<string, number | string>;
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
}

export default function Results({ status, phase, progressData, trialData, result, error, sensitivityType, sensitivityProgress = [], sensitivityResult }: Props) {
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

          {/* DSM figure */}
          {result.figurePath && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 mb-2">Optimized DSM</div>
              <img
                src={`/api/results/${result.figurePath}`}
                alt="Optimized DSM Figure"
                className="max-w-full rounded border border-gray-200"
              />
            </div>
          )}

          {/* Downloads */}
          <div className="flex gap-3">
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
                Download Figure
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
