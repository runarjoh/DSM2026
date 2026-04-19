import { useState } from "react";
import Heatmap from "./Heatmap";
import DataTable from "./DataTable";

interface Props {
  freqMatrix: number[][] | null;
  consolMatrix: number[][] | null;
  units: string[];
}

export default function MatrixPreview({ freqMatrix, consolMatrix, units }: Props) {
  const [view, setView] = useState<"heatmap" | "table">("heatmap");
  const [which, setWhich] = useState<"freq" | "consol">("freq");

  const matrix = which === "freq" ? freqMatrix : consolMatrix;
  const binary = which === "consol";

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-1">
        <span className="bg-blue-600 text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold">
          2
        </span>
        <h2 className="text-base font-semibold">Matrix Preview</h2>
        {/* View toggle */}
        <div className="ml-auto flex bg-gray-100 rounded p-0.5 gap-0.5">
          <button
            className={`text-xs px-2.5 py-1 rounded ${view === "heatmap" ? "bg-blue-600 text-white" : "text-gray-500"}`}
            onClick={() => setView("heatmap")}
          >
            Heatmap
          </button>
          <button
            className={`text-xs px-2.5 py-1 rounded ${view === "table" ? "bg-blue-600 text-white" : "text-gray-500"}`}
            onClick={() => setView("table")}
          >
            Table
          </button>
        </div>
      </div>

      {/* Matrix selector tabs */}
      <div className="flex gap-1 mb-4 ml-8">
        <button
          className={`text-xs px-2 py-0.5 rounded border ${which === "freq" ? "border-blue-600 bg-blue-50 text-blue-600" : "border-gray-200 text-gray-500"}`}
          onClick={() => setWhich("freq")}
        >
          Frequency
        </button>
        <button
          className={`text-xs px-2 py-0.5 rounded border ${which === "consol" ? "border-blue-600 bg-blue-50 text-blue-600" : "border-gray-200 text-gray-500"}`}
          onClick={() => setWhich("consol")}
        >
          Consolidation
        </button>
      </div>

      {matrix ? (
        view === "heatmap" ? (
          <Heatmap matrix={matrix} units={units} binary={binary} />
        ) : (
          <DataTable matrix={matrix} units={units} binary={binary} />
        )
      ) : (
        <p className="text-sm text-gray-400">Loading matrix data...</p>
      )}
    </section>
  );
}
