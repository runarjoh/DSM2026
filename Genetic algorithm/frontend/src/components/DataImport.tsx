import { useRef } from "react";

export interface FileInfo {
  name: string;
  path: string;
  rows: number;
  cols: number;
}

interface Props {
  freqFile: FileInfo | null;
  consolFile: FileInfo | null;
  onReplace: (which: "freq" | "consol", file: File) => void;
  disabled: boolean;
}

function FileCard({
  label,
  info,
  onReplace,
  disabled,
}: {
  label: string;
  info: FileInfo | null;
  onReplace: (f: File) => void;
  disabled: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="border border-dashed border-gray-300 rounded-lg p-4 text-center">
      <div className="text-sm font-semibold text-gray-700">{label}</div>
      {info ? (
        <>
          <div className="text-xs text-gray-500 mt-1 truncate">{info.name}</div>
          <div className="text-xs text-gray-400 mt-0.5">
            {info.rows} x {info.cols}
          </div>
        </>
      ) : (
        <div className="text-xs text-gray-400 mt-1">Not loaded</div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onReplace(f);
          e.target.value = "";
        }}
      />
      <button
        className="mt-2 text-xs px-3 py-1 border border-gray-300 rounded bg-white text-blue-600 hover:bg-gray-50 disabled:opacity-50"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
      >
        Replace file...
      </button>
    </div>
  );
}

export default function DataImport({ freqFile, consolFile, onReplace, disabled }: Props) {
  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="bg-blue-600 text-white rounded-full w-6 h-6 inline-flex items-center justify-center text-xs font-bold">
          1
        </span>
        <h2 className="text-base font-semibold">Data Import</h2>
        {freqFile && consolFile && (
          <span className="ml-auto text-xs text-green-600 font-medium">Loaded from config</span>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FileCard
          label="Interaction Frequency Matrix"
          info={freqFile}
          onReplace={(f) => onReplace("freq", f)}
          disabled={disabled}
        />
        <FileCard
          label="Consolidation Potential Matrix"
          info={consolFile}
          onReplace={(f) => onReplace("consol", f)}
          disabled={disabled}
        />
      </div>
    </section>
  );
}
