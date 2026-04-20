import { useState } from "react";

interface Props {
  status: "idle" | "running" | "done" | "error" | "cancelled";
  dataReady: boolean;
  onRun: (type: "importance" | "robustness" | "sweep", config: Record<string, number | string>) => void;
  onCancel: () => void;
}

export default function SensitivityPanel({ status, dataReady, onRun, onCancel }: Props) {
  const [openSection, setOpenSection] = useState<string | null>("importance");

  // Importance fields
  const [impTrials, setImpTrials] = useState("30");
  const [impParamGroup, setImpParamGroup] = useState("all");

  // Robustness fields
  const [robRepeats, setRobRepeats] = useState("10");

  // Sweep fields
  const [sweepSteps, setSweepSteps] = useState("10");
  const [sweepRange, setSweepRange] = useState("2.0");

  const disabled = !dataReady || status === "running";

  function toggle(section: string) {
    setOpenSection((prev) => (prev === section ? null : section));
  }

  return (
    <div className="mb-4 space-y-3">
      {/* Parameter Importance */}
      <div className="border border-gray-200 rounded-lg">
        <button
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
          onClick={() => toggle("importance")}
        >
          <span>Parameter Importance</span>
          <span className="text-gray-400 text-xs">{openSection === "importance" ? "▲" : "▼"}</span>
        </button>
        {openSection === "importance" && (
          <div className="px-4 pb-4 border-t border-gray-100">
            <p className="text-xs text-gray-500 mt-2 mb-3">
              Computes fANOVA importance scores. Will reuse previous tuning study if available.
            </p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <label className="block">
                <span className="text-xs text-gray-500">Number of trials</span>
                <input
                  type="number"
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={impTrials}
                  onChange={(e) => setImpTrials(e.target.value)}
                  disabled={disabled}
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-500">Parameter group</span>
                <select
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={impParamGroup}
                  onChange={(e) => setImpParamGroup(e.target.value)}
                  disabled={disabled}
                >
                  <option value="weights">weights</option>
                  <option value="ga_operators">ga_operators</option>
                  <option value="clustering">clustering</option>
                  <option value="fitness_and_clustering">fitness_and_clustering</option>
                  <option value="all">all</option>
                </select>
              </label>
            </div>
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              onClick={() => onRun("importance", { n_trials: parseInt(impTrials), param_group: impParamGroup })}
              disabled={disabled}
            >
              {status === "running" ? "Running..." : "Run Importance Analysis"}
            </button>
            {status === "running" && (
              <button
                className="ml-2 bg-red-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-red-700"
                onClick={onCancel}
              >
                Cancel
              </button>
            )}
          </div>
        )}
      </div>

      {/* Robustness Analysis */}
      <div className="border border-gray-200 rounded-lg">
        <button
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
          onClick={() => toggle("robustness")}
        >
          <span>Robustness Analysis</span>
          <span className="text-gray-400 text-xs">{openSection === "robustness" ? "▲" : "▼"}</span>
        </button>
        {openSection === "robustness" && (
          <div className="px-4 pb-4 border-t border-gray-100">
            <p className="text-xs text-gray-500 mt-2 mb-3">
              Runs the GA multiple times with current parameters to measure result stability.
            </p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <label className="block">
                <span className="text-xs text-gray-500">Number of repeats</span>
                <input
                  type="number"
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={robRepeats}
                  onChange={(e) => setRobRepeats(e.target.value)}
                  disabled={disabled}
                />
              </label>
            </div>
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              onClick={() => onRun("robustness", { n_repeats: parseInt(robRepeats) })}
              disabled={disabled}
            >
              {status === "running" ? "Running..." : "Run Robustness Analysis"}
            </button>
            {status === "running" && (
              <button
                className="ml-2 bg-red-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-red-700"
                onClick={onCancel}
              >
                Cancel
              </button>
            )}
          </div>
        )}
      </div>

      {/* Weight Sensitivity Sweep */}
      <div className="border border-gray-200 rounded-lg">
        <button
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
          onClick={() => toggle("sweep")}
        >
          <span>Weight Sensitivity Sweep</span>
          <span className="text-gray-400 text-xs">{openSection === "sweep" ? "▲" : "▼"}</span>
        </button>
        {openSection === "sweep" && (
          <div className="px-4 pb-4 border-t border-gray-100">
            <p className="text-xs text-gray-500 mt-2 mb-3">
              Varies each fitness weight independently to measure sensitivity.
            </p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <label className="block">
                <span className="text-xs text-gray-500">Number of steps</span>
                <input
                  type="number"
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={sweepSteps}
                  onChange={(e) => setSweepSteps(e.target.value)}
                  disabled={disabled}
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-500">Range multiplier</span>
                <input
                  type="number"
                  step="0.1"
                  className="mt-1 block w-full rounded border-gray-300 border px-2 py-1 text-sm"
                  value={sweepRange}
                  onChange={(e) => setSweepRange(e.target.value)}
                  disabled={disabled}
                />
              </label>
            </div>
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              onClick={() => onRun("sweep", { n_steps: parseInt(sweepSteps), range_multiplier: parseFloat(sweepRange) })}
              disabled={disabled}
            >
              {status === "running" ? "Running..." : "Run Sweep Analysis"}
            </button>
            {status === "running" && (
              <button
                className="ml-2 bg-red-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-red-700"
                onClick={onCancel}
              >
                Cancel
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
