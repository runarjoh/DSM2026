interface Props {
  matrix: number[][];
  units: string[];
  binary?: boolean;
}

export default function DataTable({ matrix, units, binary = false }: Props) {
  return (
    <div className="overflow-auto max-h-[500px] border border-gray-200 rounded">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="sticky top-0 left-0 z-20 bg-gray-100 border border-gray-200 px-2 py-1" />
            {units.map((u, i) => (
              <th
                key={i}
                className="sticky top-0 z-10 bg-gray-100 border border-gray-200 px-1.5 py-1 font-medium text-gray-600 whitespace-nowrap"
              >
                {u}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, r) => (
            <tr key={r}>
              <th className="sticky left-0 z-10 bg-gray-100 border border-gray-200 px-2 py-1 font-medium text-gray-600 whitespace-nowrap text-right">
                {units[r]}
              </th>
              {row.map((val, c) => (
                <td
                  key={c}
                  className={`border border-gray-200 px-1.5 py-1 text-center ${
                    r === c ? "bg-gray-100" : ""
                  }`}
                >
                  {binary ? (val === 1 ? "1" : "") : (val === 0 ? "" : val % 1 === 0 ? val : val.toFixed(2))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
