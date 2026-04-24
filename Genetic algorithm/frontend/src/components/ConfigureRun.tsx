import React from "react";
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
  maxFreq: number;
}

// Single source of truth: weight fields per fitness mode
export const modeWeights: Record<string, { key: string; label: string }[]> = {
  classic: [
    { key: "alpha", label: "\u03B1 — S1 cross-boundary" },
    { key: "beta", label: "\u03B2 — S2 missing-within" },
    { key: "gamma", label: "\u03B3 — S3 consol-omission" },
  ],
  mdl_pure: [
    { key: "alpha", label: "\u03B1 — S1 cross-boundary" },
    { key: "beta", label: "\u03B2 — S2 missing-within" },
    { key: "gamma", label: "\u03B3 — S3 consol-omission" },
    { key: "delta", label: "\u03B4 — S4 consol-overreach" },
  ],
  full: [
    { key: "alpha", label: "\u03B1 — S1 cross-boundary" },
    { key: "beta", label: "\u03B2 — S2 missing-within" },
    { key: "gamma", label: "\u03B3 — S3 consol-omission" },
    { key: "delta", label: "\u03B4 — S4 consol-overreach" },
    { key: "epsilon", label: "\u03B5 — Size imbalance" },
  ],
  anti_singleton: [
    { key: "alpha", label: "\u03B1 — S1 cross-boundary" },
    { key: "beta", label: "\u03B2 — S2 missing-within" },
    { key: "gamma", label: "\u03B3 — S3 consol-omission" },
    { key: "delta", label: "\u03B4 — S4 consol-overreach" },
    { key: "epsilon", label: "\u03B5 — Size imbalance" },
    { key: "zeta", label: "\u03B6 — Singleton penalty" },
  ],
};

// Modes where target_clusters is used (size_imbalance / singleton_penalty)
const MODES_WITH_TARGET_CLUSTERS = new Set(["full", "anti_singleton"]);

// GA operator fields — target_clusters conditionally shown
function getOperatorFields(fitnessMode: string) {
  const fields = [
    { key: "max_clusters", label: "Max clusters" },
  ];
  if (MODES_WITH_TARGET_CLUSTERS.has(fitnessMode)) {
    fields.push({ key: "target_clusters", label: "Target clusters" });
  }
  fields.push(
    { key: "population_size", label: "Population" },
    { key: "n_generations", label: "Generations" },
    { key: "cxpb", label: "Crossover (cxpb)" },
    { key: "mutpb", label: "Mutation (mutpb)" },
    { key: "tournsize", label: "Tournament size" },
  );
  return fields;
}

const optunaFields = [
  { key: "n_trials", label: "Trials" },
  { key: "n_jobs", label: "Parallel jobs" },
  { key: "trial_generations", label: "Trial generations" },
  { key: "trial_population", label: "Trial population" },
];

export default function ConfigureRun({
  mode, runAfterTune, gaParams, optunaParams, status, dataReady,
  onModeChange, onRunAfterTuneChange, onGaParam, onOptunaParam, onRun, onCancel, onReset, onSensitivityRun, maxFreq,
}: Props) {
  const running = status === "running";
  const disabled = !dataReady || running;

  return (
    <section className={`bg-white rounded-rc border p-6 shadow-rc ${!dataReady ? "opacity-50 pointer-events-none" : ""}`} style={{ borderColor: "#EBEEF3" }}>
      <div className="flex items-center gap-2 mb-4">
        <span className={`text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold`} style={{ background: dataReady ? "#3B4FE4" : "#8B92A5" }}>
          3
        </span>
        <h2 className="text-base font-semibold font-heading" style={{ color: "#1A1D26" }}>Configure & Run</h2>
      </div>

      {/* Mode toggle */}
      <div className="flex rounded-lg p-0.5 gap-0.5 mb-4 max-w-md" style={{ background: "#F1F3F7" }}>
        <button
          className={`flex-1 text-sm py-2 rounded-md font-medium transition-all duration-200 ${mode === "optimize" ? "text-white shadow-sm" : ""}`}
          style={mode === "optimize" ? { background: "#3B4FE4" } : { color: "#5A6178" }}
          onClick={() => onModeChange("optimize")}
          disabled={running}
        >
          Optimize
        </button>
        <button
          className={`flex-1 text-sm py-2 rounded-md font-medium transition-all duration-200 ${mode === "tune" ? "text-white shadow-sm" : ""}`}
          style={mode === "tune" ? { background: "#3B4FE4" } : { color: "#5A6178" }}
          onClick={() => onModeChange("tune")}
          disabled={running}
        >
          Tune Parameters
        </button>
        <button
          className={`flex-1 text-sm py-2 rounded-md font-medium transition-all duration-200 ${mode === "sensitivity" ? "text-white shadow-sm" : ""}`}
          style={mode === "sensitivity" ? { background: "#3B4FE4" } : { color: "#5A6178" }}
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
            value={gaParams.fitness_mode || "mdl_pure"}
            onChange={(e) => onGaParam("fitness_mode", e.target.value)}
            disabled={disabled}
          >
            <option value="classic">Type 3 only</option>
            <option value="mdl_pure">Type 3 + Type 4 errors</option>
            <option value="full">Type 3 + Type 4 + Size balance</option>
            <option value="anti_singleton">Type 3 + Type 4 + Anti-singleton</option>
          </select>
        </label>
      </div>

      {/* Fitness formula display */}
      <div className="mb-4 p-3 bg-gray-50 rounded border border-gray-200">
        <div className="text-xs font-semibold text-gray-500 mb-1">Fitness formula</div>
        {(() => {
          const mode = gaParams.fitness_mode || "mdl_pure";
          const plus = <span className="text-gray-400"> + </span>;
          const dot = <span className="text-gray-400"> · </span>;
          const w = (s: string) => <span className="text-blue-600">{s}</span>;

          // Build mdl_weight display from active weights
          const activeWeights = modeWeights[mode] || modeWeights.classic;
          const mdlWeightParts = activeWeights.map((w) => w.label.charAt(0));

          // Build terms list
          const terms: React.ReactNode[] = [
            <span key="mdl"><span>(1-{mdlWeightParts.join("-")})</span>{dot}<span>MDL</span></span>,
            <span key="s1">{w("\u03B1")}{dot}<span>S1<sub>cross-boundary</sub></span></span>,
            <span key="s2">{w("\u03B2")}{dot}<span>S2<sub>missing-within</sub></span></span>,
            <span key="s3">{w("\u03B3")}{dot}<span>S3<sub>consol-omission</sub></span></span>,
          ];
          if (mode !== "classic") {
            terms.push(<span key="s4">{w("\u03B4")}{dot}<span>S4<sub>consol-overreach</sub></span></span>);
          }
          if (mode === "full" || mode === "anti_singleton") {
            terms.push(<span key="si">{w("\u03B5")}{dot}<span className="text-emerald-600">SizeImbalance</span></span>);
          }
          if (mode === "anti_singleton") {
            terms.push(<span key="sp">{w("\u03B6")}{dot}<span className="text-red-500">SingletonPenalty</span></span>);
          }

          return (
            <div className="text-xs text-gray-600 font-mono leading-relaxed">
              <span className="text-gray-400">f = </span>
              {terms.map((t, i) => <span key={i}>{i > 0 && plus}{t}</span>)}
            </div>
          );
        })()}
        <div className="text-xs text-gray-400 mt-1">
          {(() => {
            const mode = gaParams.fitness_mode || "mdl_pure";
            if (mode === "classic") return "S1-S3 scaled by 2\u00B7log\u2082(n+1). Only frequency and consolidation errors, no structural balance terms.";
            if (mode === "mdl_pure") return "All error terms scaled by 2\u00B7log\u2082(n+1). S4 counts within-cluster pairs with no consolidation potential.";
            if (mode === "full") return "All error terms + size imbalance scaled by 2\u00B7log\u2082(n+1). Adds structural pressure for even cluster sizes.";
            return "All error terms + size imbalance + singleton\u00B2/target_clusters, all scaled by 2\u00B7log\u2082(n+1). Quadratic singleton penalty escalates sharply with more isolated units.";
          })()}
        </div>
      </div>

      {/* GA params — shown for Optimize mode */}
      {mode === "optimize" && (
        <div className="mb-4">
          {/* Weight parameters — dynamic per fitness mode */}
          <div className="text-xs font-semibold text-gray-400 mb-1">Weights</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 mb-3">
            {(modeWeights[gaParams.fitness_mode || "mdl_pure"] || modeWeights.classic).map((f) => (
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
          </div>
          {/* Operator & clustering parameters — always shown */}
          <div className="text-xs font-semibold text-gray-400 mb-1">Operators & clustering</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {getOperatorFields(gaParams.fitness_mode || "mdl_pure").map((f) => (
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
            <label className="block col-span-2 sm:col-span-3 md:col-span-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Frequency threshold (min value to keep)</span>
                <span className="text-xs font-mono text-gray-700">{gaParams.freq_threshold || "0"} / {maxFreq}</span>
              </div>
              <input
                type="range"
                min="0"
                max={maxFreq}
                step="1"
                className="mt-1 block w-full accent-blue-600"
                value={gaParams.freq_threshold || "0"}
                onChange={(e) => onGaParam("freq_threshold", e.target.value)}
                disabled={disabled}
              />
            </label>
            <label className="block">
              <span className="text-xs text-gray-500">Matrix preprocessing</span>
              <select
                className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                value={gaParams.matrix_preprocess || "normalize"}
                onChange={(e) => onGaParam("matrix_preprocess", e.target.value)}
                disabled={disabled}
              >
                <option value="normalize">Normalize (0–1)</option>
                <option value="binary">Binary (0 or 1)</option>
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
            className="text-white px-5 py-2 rounded-md text-sm font-medium disabled:opacity-50 transition-colors duration-200"
            style={{ background: "#3B4FE4" }}
            onClick={onRun}
            disabled={disabled}
          >
            {running ? "Running..." : mode === "optimize" ? "Run Optimization" : "Start Tuning"}
          </button>
          {running && (
            <button
              className="text-white px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200"
              style={{ background: "#7C5CFF" }}
              onClick={onCancel}
            >
              Cancel
            </button>
          )}
          {status !== "idle" && !running && (
            <button
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200" style={{ background: "#F1F3F7", color: "#5A6178" }}
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
