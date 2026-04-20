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

interface Props {
  status: "idle" | "running" | "done" | "error" | "cancelled";
  phase: "idle" | "tune" | "optimize";
  progressData: ProgressPoint[];
  trialData: TrialPoint[];
  result: ResultData | null;
  error: string | null;
  sensitivityType?: "importance" | "robustness" | "sweep" | null;
  sensitivityResult?: SensitivityResult | null;
}

export default function Results({ status, phase, progressData, trialData, result, error, sensitivityType, sensitivityResult }: Props) {
  const hasData = progressData.length > 0 || trialData.length > 0 || status === "done" || status === "error" || status === "cancelled" || sensitivityResult != null;

  return (
    <section className={`bg-white rounded-lg border border-gray-200 p-6 ${!hasData ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-2 mb-4">
        <span className={`${status === "done" ? "bg-green-600" : hasData ? "bg-blue-600" : "bg-gray-400"} text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold`}>
          4
        </span>
        <h2 className="text-base font-semibold">Results</h2>
        {status === "running" && phase === "tune" && (
          <span className="text-xs text-blue-600 font-medium ml-2">Phase 1: Tuning</span>
        )}
        {status === "running" && phase === "optimize" && (
          <span className="text-xs text-blue-600 font-medium ml-2">Phase 2: Optimizing</span>
        )}
        {status === "done" && result?.fitness != null && (
          <span className="text-xs text-green-600 font-medium ml-auto">
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
          <div className="text-xs font-semibold text-gray-500 mb-2">
            Optimization — Generation {progressData[progressData.length - 1].gen}
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
              {Object.entries(sensitivityResult.sweeps).map(([weight, data]) => (
                <div key={weight} className="mb-4">
                  <div className="text-xs font-medium text-gray-600 mb-1">{weight}</div>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={data}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="value" label={{value: weight, position: "insideBottom", offset: -5}} tickFormatter={(v: number) => v.toFixed(2)} />
                      <YAxis label={{value: "Fitness", angle: -90, position: "insideLeft"}} />
                      <Tooltip />
                      <Line type="monotone" dataKey="fitness" stroke="#3b82f6" dot={{r: 3}} name="Fitness" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ))}
            </div>
          )}

          {sensitivityResult.logPath && (
            <div className="text-xs text-gray-400 mt-2">Results saved to: {sensitivityResult.logPath}</div>
          )}
        </div>
      )}

      {/* Error */}
      {status === "error" && error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mt-2">
          <p className="text-sm text-red-700 font-medium">Error</p>
          <pre className="text-xs text-red-600 mt-1 whitespace-pre-wrap">{error}</pre>
        </div>
      )}

      {/* Cancelled */}
      {status === "cancelled" && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mt-2">
          <p className="text-sm text-yellow-700">Run cancelled.</p>
        </div>
      )}
    </section>
  );
}
