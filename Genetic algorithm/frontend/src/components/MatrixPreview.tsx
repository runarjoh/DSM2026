import { useState } from "react";
import Heatmap from "./Heatmap";
import DataTable from "./DataTable";

interface Props {
  freqMatrix: number[][] | null;
  consolMatrix: number[][] | null;
  units: string[];
  groups?: number[] | null;
}

export default function MatrixPreview({ freqMatrix, consolMatrix, units, groups = null }: Props) {
  const [view, setView] = useState<"heatmap" | "table">("heatmap");
  const [which, setWhich] = useState<"freq" | "consol" | "combined">("combined");

  const matrix = which === "consol" ? consolMatrix : freqMatrix;
  const binary = which === "consol";

  return (
    <section className="bg-white rounded-rc border p-6 shadow-rc" style={{ borderColor: "#EBEEF3" }}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold" style={{ background: "#3B4FE4" }}>
          2
        </span>
        <h2 className="text-base font-semibold font-heading" style={{ color: "#1A1D26" }}>Matrix Preview</h2>
        {/* View toggle */}
        <div className="ml-auto flex rounded p-0.5 gap-0.5" style={{ background: "#F1F3F7" }}>
          <button
            className={`text-xs px-2.5 py-1 rounded transition-all duration-200 ${view === "heatmap" ? "text-white shadow-sm" : ""}`}
            style={view === "heatmap" ? { background: "#3B4FE4" } : { color: "#5A6178" }}
            onClick={() => setView("heatmap")}
          >
            Heatmap
          </button>
          <button
            className={`text-xs px-2.5 py-1 rounded transition-all duration-200 ${view === "table" ? "text-white shadow-sm" : ""}`}
            style={view === "table" ? { background: "#3B4FE4" } : { color: "#5A6178" }}
            onClick={() => setView("table")}
          >
            Table
          </button>
        </div>
      </div>

      {/* Matrix selector tabs */}
      <div className="flex gap-1 mb-4 ml-8">
        <button
          className={`text-xs px-2 py-0.5 rounded border transition-colors duration-200`}
          style={which === "freq" ? { borderColor: "#3B4FE4", background: "#EEF0FD", color: "#3B4FE4" } : { borderColor: "#E2E5EB", color: "#5A6178" }}
          onClick={() => setWhich("freq")}
        >
          Frequency
        </button>
        <button
          className={`text-xs px-2 py-0.5 rounded border transition-colors duration-200`}
          style={which === "consol" ? { borderColor: "#3B4FE4", background: "#EEF0FD", color: "#3B4FE4" } : { borderColor: "#E2E5EB", color: "#5A6178" }}
          onClick={() => setWhich("consol")}
        >
          Consolidation
        </button>
        <button
          className={`text-xs px-2 py-0.5 rounded border transition-colors duration-200`}
          style={which === "combined" ? { borderColor: "#3B4FE4", background: "#EEF0FD", color: "#3B4FE4" } : { borderColor: "#E2E5EB", color: "#5A6178" }}
          onClick={() => setWhich("combined")}
        >
          Combined
        </button>
      </div>

      {matrix ? (
        view === "heatmap" ? (
          <Heatmap matrix={matrix} units={units} binary={binary} consolOverlay={which === "combined" ? consolMatrix : null} groups={groups} />
        ) : (
          <DataTable matrix={matrix} units={units} binary={binary} />
        )
      ) : (
        <p className="text-sm text-gray-400">Loading matrix data...</p>
      )}
    </section>
  );
}
