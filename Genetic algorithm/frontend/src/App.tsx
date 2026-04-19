import { useReducer, useEffect, useRef } from "react";
import DataImport, { type FileInfo } from "./components/DataImport";
import MatrixPreview from "./components/MatrixPreview";

// --- Types ---

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

type Status = "idle" | "running" | "done" | "error" | "cancelled";

interface AppState {
  // Data
  freqFile: FileInfo | null;
  consolFile: FileInfo | null;
  freqMatrix: number[][] | null;
  consolMatrix: number[][] | null;
  units: string[];
  dataError: string | null;

  // Run config
  mode: "optimize" | "tune";
  runAfterTune: boolean;
  gaParams: Record<string, string>;
  optunaParams: Record<string, string>;

  // Run state
  status: Status;
  runId: string | null;
  phase: "idle" | "tune" | "optimize";
  progressData: ProgressPoint[];
  trialData: TrialPoint[];
  result: {
    fitness?: number;
    resultPath?: string;
    figurePath?: string;
    bestParams?: Record<string, number | string>;
  } | null;
  error: string | null;
}

type Action =
  | { type: "setData"; freqFile: FileInfo; consolFile: FileInfo; freqMatrix: number[][]; consolMatrix: number[][]; units: string[] }
  | { type: "dataError"; message: string }
  | { type: "setMode"; mode: "optimize" | "tune" }
  | { type: "setRunAfterTune"; value: boolean }
  | { type: "setGaParam"; field: string; value: string }
  | { type: "setOptunaParam"; field: string; value: string }
  | { type: "start"; runId: string }
  | { type: "phase"; phase: "tune" | "optimize" }
  | { type: "progress"; point: ProgressPoint }
  | { type: "trial"; point: TrialPoint }
  | { type: "done"; result: AppState["result"] }
  | { type: "error"; message: string }
  | { type: "cancelled" }
  | { type: "reset" }
  | { type: "replaceFile"; which: "freq" | "consol"; file: FileInfo; freqMatrix: number[][]; consolMatrix: number[][]; units: string[] };

const defaultGaParams: Record<string, string> = {
  alpha: "0.15", beta: "0.05", gamma: "0.15", delta: "0.20",
  max_clusters: "10", target_clusters: "10", consolidation_mode: "once",
  population_size: "200", n_generations: "400",
  cxpb: "0.5", mutpb: "0.1", tournsize: "5",
};

const defaultOptunaParams: Record<string, string> = {
  param_group: "weights", n_trials: "50", n_jobs: "1",
  trial_generations: "100", trial_population: "100",
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "setData":
      return {
        ...state,
        freqFile: action.freqFile, consolFile: action.consolFile,
        freqMatrix: action.freqMatrix, consolMatrix: action.consolMatrix,
        units: action.units, dataError: null,
      };
    case "dataError":
      return { ...state, dataError: action.message };
    case "replaceFile": {
      const update: Partial<AppState> = {
        freqMatrix: action.freqMatrix,
        consolMatrix: action.consolMatrix,
        units: action.units,
        dataError: null,
      };
      if (action.which === "freq") update.freqFile = action.file;
      else update.consolFile = action.file;
      return { ...state, ...update };
    }
    case "setMode":
      return { ...state, mode: action.mode };
    case "setRunAfterTune":
      return { ...state, runAfterTune: action.value };
    case "setGaParam":
      return { ...state, gaParams: { ...state.gaParams, [action.field]: action.value } };
    case "setOptunaParam":
      return { ...state, optunaParams: { ...state.optunaParams, [action.field]: action.value } };
    case "start":
      return { ...state, status: "running", runId: action.runId, progressData: [], trialData: [], result: null, error: null, phase: "idle" };
    case "phase":
      return { ...state, phase: action.phase };
    case "progress":
      return { ...state, progressData: [...state.progressData, action.point] };
    case "trial":
      return { ...state, trialData: [...state.trialData, action.point] };
    case "done":
      return { ...state, status: "done", result: action.result };
    case "error":
      return { ...state, status: "error", error: action.message };
    case "cancelled":
      return { ...state, status: "cancelled" };
    case "reset":
      return { ...state, status: "idle", runId: null, phase: "idle", progressData: [], trialData: [], result: null, error: null };
  }
}

const initialState: AppState = {
  freqFile: null, consolFile: null,
  freqMatrix: null, consolMatrix: null,
  units: [], dataError: null,
  mode: "optimize", runAfterTune: false,
  gaParams: { ...defaultGaParams },
  optunaParams: { ...defaultOptunaParams },
  status: "idle", runId: null, phase: "idle",
  progressData: [], trialData: [],
  result: null, error: null,
};

export default function App() {
  const [s, dispatch] = useReducer(reducer, initialState);
  const esRef = useRef<EventSource | null>(null);
  const loaded = useRef(false);

  const dataReady = s.freqMatrix !== null && s.consolMatrix !== null;

  // Load config defaults + matrix data on mount
  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;

    (async () => {
      try {
        // Load config for params
        const cfgRes = await fetch("/api/config");
        const cfg = await cfgRes.json();
        if (cfg.ga) {
          for (const [k, v] of Object.entries(cfg.ga)) {
            if (k in defaultGaParams) dispatch({ type: "setGaParam", field: k, value: String(v) });
          }
        }
        if (cfg.optuna) {
          for (const [k, v] of Object.entries(cfg.optuna)) {
            if (k in defaultOptunaParams) dispatch({ type: "setOptunaParam", field: k, value: String(v) });
          }
        }

        // Load matrix preview
        const matRes = await fetch("/api/matrix-preview");
        if (!matRes.ok) throw new Error("Failed to load matrices");
        const mat = await matRes.json();

        dispatch({
          type: "setData",
          freqFile: { name: cfg.data?.freq_csv || "frequency.csv", path: cfg.data?.freq_csv || "", rows: mat.shape[0], cols: mat.shape[1] },
          consolFile: { name: cfg.data?.consol_csv || "consolidation.csv", path: cfg.data?.consol_csv || "", rows: mat.shape[0], cols: mat.shape[1] },
          freqMatrix: mat.freq,
          consolMatrix: mat.consol,
          units: mat.units,
        });
      } catch (e: unknown) {
        dispatch({ type: "dataError", message: e instanceof Error ? e.message : "Failed to load" });
      }
    })();
  }, []);

  // File replacement handler
  async function handleReplace(which: "freq" | "consol", file: File) {
    try {
      // Upload file
      const formData = new FormData();
      formData.append("files", file);
      const upRes = await fetch("/api/upload", { method: "POST", body: formData });
      if (!upRes.ok) throw new Error("Upload failed");
      const { paths } = await upRes.json();
      const uploadedPath = paths[0];

      // Re-fetch matrix preview with the new path
      const freqPath = which === "freq" ? uploadedPath : s.freqFile?.path || "";
      const consolPath = which === "consol" ? uploadedPath : s.consolFile?.path || "";
      const matRes = await fetch(`/api/matrix-preview?freq_csv=${encodeURIComponent(freqPath)}&consol_csv=${encodeURIComponent(consolPath)}`);
      if (!matRes.ok) {
        const err = await matRes.json();
        throw new Error(err.detail || "Failed to load matrix");
      }
      const mat = await matRes.json();

      dispatch({
        type: "replaceFile",
        which,
        file: { name: file.name, path: uploadedPath, rows: mat.shape[0], cols: mat.shape[1] },
        freqMatrix: mat.freq,
        consolMatrix: mat.consol,
        units: mat.units,
      });
    } catch (e: unknown) {
      dispatch({ type: "dataError", message: e instanceof Error ? e.message : "Upload failed" });
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-slate-800 text-white px-6 py-3 flex items-center gap-2">
        <span className="text-lg font-semibold">DSM GA</span>
        <span className="text-slate-400 text-sm">Optimization Toolkit</span>
      </nav>
      <main className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        {/* Section 1: Data Import */}
        <DataImport
          freqFile={s.freqFile}
          consolFile={s.consolFile}
          onReplace={handleReplace}
          disabled={s.status === "running"}
        />

        {s.dataError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-700">{s.dataError}</p>
          </div>
        )}

        {/* Section 2: Matrix Preview */}
        <MatrixPreview
          freqMatrix={s.freqMatrix}
          consolMatrix={s.consolMatrix}
          units={s.units}
        />

        {/* Section 3: Configure & Run — placeholder */}
        <section className={`bg-white rounded-lg border border-gray-200 p-6 ${!dataReady ? "opacity-50 pointer-events-none" : ""}`}>
          <div className="flex items-center gap-2">
            <span className={`${dataReady ? "bg-blue-600" : "bg-gray-400"} text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold`}>3</span>
            <h2 className="text-base font-semibold">Configure & Run</h2>
          </div>
          <p className="text-sm text-gray-500 mt-2">{dataReady ? "Coming next" : "Load data first"}</p>
        </section>

        {/* Section 4: Results — placeholder */}
        <section className="bg-white rounded-lg border border-gray-200 p-6 opacity-50">
          <div className="flex items-center gap-2">
            <span className="bg-gray-400 text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold">4</span>
            <h2 className="text-base font-semibold">Results</h2>
          </div>
          <p className="text-sm text-gray-400 mt-2">Run an optimization first</p>
        </section>
      </main>
    </div>
  );
}
