/** Apply frequency threshold + normalize/binary preprocessing to a matrix. */
export function preprocessMatrix(
  matrix: number[][],
  mode: "normalize" | "binary",
  threshold: number,
): number[][] {
  // Step 1: threshold filter — only applied when threshold > 0
  const filtered = threshold > 0
    ? matrix.map((row) => row.map((v) => (v > 0 && v < threshold ? 0 : v)))
    : matrix;

  // Step 2: normalize or binarize
  if (mode === "binary") {
    return filtered.map((row) => row.map((v) => (v > 0 ? 1 : 0)));
  }

  // normalize to [0, 1]
  const max = Math.max(...filtered.flat()) || 1;
  return filtered.map((row) => row.map((v) => v / max));
}
