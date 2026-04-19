interface Props {
  mode: "optimize" | "tune";
  runAfterTune: boolean;
  gaParams: Record<string, string>;
  optunaParams: Record<string, string>;
  status: string;
  dataReady: boolean;
  onModeChange: (mode: "optimize" | "tune") => void;
  onRunAfterTuneChange: (v: boolean) => void;
  onGaParam: (field: string, value: string) => void;
  onOptunaParam: (field: string, value: string) => void;
  onRun: () => void;
  onCancel: () => void;
  onReset: () => void;
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
  onModeChange, onRunAfterTuneChange, onGaParam, onOptunaParam, onRun, onCancel, onReset,
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
      <div className="flex bg-gray-100 rounded-lg p-0.5 gap-0.5 mb-4 max-w-xs">
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
              <span className="text-xs text-gray-500">Consolidation mode</span>
              <select
                className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                value={gaParams.consolidation_mode || "once"}
                onChange={(e) => onGaParam("consolidation_mode", e.target.value)}
                disabled={disabled}
              >
                <option value="once">once</option>
                <option value="directional">directional</option>
              </select>
            </label>
          </div>
        </div>
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

      {/* Action buttons */}
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
    </section>
  );
}
