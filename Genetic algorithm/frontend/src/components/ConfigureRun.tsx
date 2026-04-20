import SensitivityPanel from "./SensitivityPanel";

interface Props {
  mode: "optimize" | "tune" | "sensitivity";
  runAfterTune: boolean;
  gaParams: Record<string, string>;
  optunaParams: Record<string, string>;
  status: "idle" | "running" | "done" | "error" | "cancelled";
  dataReady: boolean;
  onModeChange: (mode: "optimize" | "tune" | "sensitivity") => void;
  onRunAfterTuneChange: (v: boolean) => void;
  onGaParam: (field: string, value: string) => void;
  onOptunaParam: (field: string, value: string) => void;
  onRun: () => void;
  onCancel: () => void;
  onReset: () => void;
  onSensitivityRun: (type: "importance" | "robustness" | "sweep", config: Record<string, number | string>) => void;
}

const gaFields = [
  { key: "alpha", label: "Alpha (\u03B1)" },
  { key: "beta", label: "Beta (\u03B2)" },
  { key: "gamma", label: "Gamma (\u03B3)" },
  { key: "delta", label: "Delta (\u03B4)" },
  { key: "max_clusters", label: "Max clusters" },
  { key: "target_clusters", label: "Target clusters" },
  { key: "population_size", label: "Population" },
  { key: "n_generations", label: "Generations" },
  { key: "cxpb", label: "Crossover (cxpb)" },
  { key: "mutpb", label: "Mutation (mutpb)" },
  { key: "tournsize", label: "Tournament size" },
];

const optunaFields = [
  { key: "n_trials", label: "Trials" },
  { key: "n_jobs", label: "Parallel jobs" },
  { key: "trial_generations", label: "Trial generations" },
  { key: "trial_population", label: "Trial population" },
];

export default function ConfigureRun({
  mode, runAfterTune, gaParams, optunaParams, status, dataReady,
  onModeChange, onRunAfterTuneChange, onGaParam, onOptunaParam, onRun, onCancel, onReset, onSensitivityRun,
}: Props) {
  const running = status === "running";
  const disabled = !dataReady || running;

  return (
    <section className={`bg-white rounded-lg border border-gray-200 p-6 ${!dataReady ? "opacity-50 pointer-events-none" : ""}`}>
      <div className="flex items-center gap-2 mb-4">
        <span className={`${dataReady ? "bg-blue-600" : "bg-gray-400"} text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold`}>
          3
        </span>
        <h2 className="text-base font-semibold">Configure & Run</h2>
      </div>

      {/* Mode toggle */}
      <div className="flex bg-gray-100 rounded-lg p-0.5 gap-0.5 mb-4 max-w-md">
        <button
          className={`flex-1 text-sm py-2 rounded-md font-medium ${mode === "optimize" ? "bg-blue-600 text-white" : "text-gray-500"}`}
          onClick={() => onModeChange("optimize")}
          disabled={running}
        >
          Optimize
        </button>
        <button
          className={`flex-1 text-sm py-2 rounded-md font-medium ${mode === "tune" ? "bg-blue-600 text-white" : "text-gray-500"}`}
          onClick={() => onModeChange("tune")}
          disabled={running}
        >
          Tune Parameters
        </button>
        <button
          className={`flex-1 text-sm py-2 rounded-md font-medium ${mode === "sensitivity" ? "bg-blue-600 text-white" : "text-gray-500"}`}
          onClick={() => onModeChange("sensitivity")}
          disabled={running}
        >
          Sensitivity
        </button>
      </div>

      {/* Fitness function selector — always visible */}
      <div className="flex items-center gap-3 mb-3">
        <label className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Fitness function</span>
          <select
            className="rounded border-gray-300 border px-2 py-1 text-sm"
            value={gaParams.fitness_mode || "classic"}
            onChange={(e) => onGaParam("fitness_mode", e.target.value)}
            disabled={disabled}
          >
            <option value="classic">Type 3 only</option>
            <option value="mdl_pure">Type 3 + Type 4 errors</option>
          </select>
        </label>
      </div>

      {/* Fitness formula display */}
      <div className="mb-4 p-3 bg-gray-50 rounded border border-gray-200">
        <div className="text-xs font-semibold text-gray-500 mb-1">Fitness formula</div>
        {(gaParams.fitness_mode || "classic") === "classic" ? (
          <div className="text-xs text-gray-600 font-mono leading-relaxed">
            <span className="text-gray-400">f = </span>
            <span>(1-{"\u03B1"}-{"\u03B2"}-{"\u03B3"}-{"\u03B4"})</span>
            <span className="text-gray-400"> · </span><span>MDL</span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B1"}</span>
            <span className="text-gray-400"> · </span><span>S1<sub>cross-boundary</sub></span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B2"}</span>
            <span className="text-gray-400"> · </span><span>S2<sub>missing-within</sub></span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B3"}</span>
            <span className="text-gray-400"> · </span><span>S3<sub>consol-omission</sub></span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B4"}</span>
            <span className="text-gray-400"> · </span><span>SizeImbalance</span>
          </div>
        ) : (
          <div className="text-xs text-gray-600 font-mono leading-relaxed">
            <span className="text-gray-400">f = </span>
            <span>(1-{"\u03B1"}-{"\u03B2"}-{"\u03B3"}-{"\u03B4"})</span>
            <span className="text-gray-400"> · </span><span>MDL</span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B1"}</span>
            <span className="text-gray-400"> · </span><span>S1<sub>cross-boundary</sub></span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B2"}</span>
            <span className="text-gray-400"> · </span><span>S2<sub>missing-within</sub></span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B3"}</span>
            <span className="text-gray-400"> · </span><span>S3<sub>consol-omission</sub></span>
            <span className="text-gray-400"> + </span>
            <span className="text-blue-600">{"\u03B4"}</span>
            <span className="text-gray-400"> · </span><span>S4<sub>consol-overreach</sub></span>
          </div>
        )}
        <div className="text-xs text-gray-400 mt-1">
          {(gaParams.fitness_mode || "classic") === "classic"
            ? "S1-S3 scaled by 2\u00B7log\u2082(n+1). Size imbalance = \u2211(cluster_size - ideal_size)\u00B2 / target_clusters."
            : "All error terms scaled by 2\u00B7log\u2082(n+1). S4 counts within-cluster pairs with no consolidation potential."}
        </div>
      </div>

      {/* GA params — shown for Optimize mode */}
      {mode === "optimize" && (
        <div className="mb-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {gaFields.map((f) => (
              <label key={f.key} className="block">
                <span className="text-xs text-gray-500">{f.label}</span>
                <input
                  type="number"
                  step="any"
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={gaParams[f.key] || ""}
                  onChange={(e) => onGaParam(f.key, e.target.value)}
                  disabled={disabled}
                />
              </label>
            ))}
            <label className="block">
              <span className="text-xs text-gray-500">Consolidation counting</span>
              <select
                className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                value={gaParams.consolidation_mode || "once"}
                onChange={(e) => onGaParam("consolidation_mode", e.target.value)}
                disabled={disabled}
              >
                <option value="once">Once per pair</option>
                <option value="directional">Directional (count both cells)</option>
              </select>
            </label>
          </div>
        </div>
      )}

      {/* Sensitivity — shown for Sensitivity mode */}
      {mode === "sensitivity" && (
        <SensitivityPanel
          status={status}
          dataReady={dataReady}
          onRun={onSensitivityRun}
          onCancel={onCancel}
        />
      )}

      {/* Optuna params — shown for Tune mode */}
      {mode === "tune" && (
        <div className="mb-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <label className="block">
              <span className="text-xs text-gray-500">Parameter group</span>
              <select
                className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                value={optunaParams.param_group || "weights"}
                onChange={(e) => onOptunaParam("param_group", e.target.value)}
                disabled={disabled}
              >
                <option value="weights">weights</option>
                <option value="ga_operators">ga_operators</option>
                <option value="clustering">clustering</option>
                <option value="fitness_and_clustering">fitness_and_clustering</option>
                <option value="all">all</option>
              </select>
            </label>
            {optunaFields.map((f) => (
              <label key={f.key} className="block">
                <span className="text-xs text-gray-500">{f.label}</span>
                <input
                  type="number"
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={optunaParams[f.key] || ""}
                  onChange={(e) => onOptunaParam(f.key, e.target.value)}
                  disabled={disabled}
                />
              </label>
            ))}
          </div>

          <label className="flex items-center gap-2 mt-3 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={runAfterTune}
              onChange={(e) => onRunAfterTuneChange(e.target.checked)}
              disabled={disabled}
              className="accent-blue-600"
            />
            Run optimization after tuning
          </label>
        </div>
      )}

      {/* Action buttons — hidden in sensitivity mode (has its own buttons) */}
      {mode !== "sensitivity" && (
        <div className="flex gap-3 items-center">
          <button
            className="bg-blue-600 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            onClick={onRun}
            disabled={disabled}
          >
            {running ? "Running..." : mode === "optimize" ? "Run Optimization" : "Start Tuning"}
          </button>
          {running && (
            <button
              className="bg-red-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-red-700"
              onClick={onCancel}
            >
              Cancel
            </button>
          )}
          {status !== "idle" && !running && (
            <button
              className="bg-gray-200 text-gray-700 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-300"
              onClick={onReset}
            >
              Reset
            </button>
          )}
        </div>
      )}
      {mode === "sensitivity" && status !== "idle" && status !== "running" && (
        <div className="flex gap-3 items-center">
          <button
            className="bg-gray-200 text-gray-700 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-300"
            onClick={onReset}
          >
            Reset
          </button>
        </div>
      )}
    </section>
  );
}
