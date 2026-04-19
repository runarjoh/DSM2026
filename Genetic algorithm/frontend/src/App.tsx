export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-slate-800 text-white px-6 py-3 flex items-center gap-2">
        <span className="text-lg font-semibold">DSM GA</span>
        <span className="text-slate-400 text-sm">Optimization Toolkit</span>
      </nav>
      <main className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        {/* Section 1: Data Import — placeholder */}
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold">1. Data Import</h2>
          <p className="text-sm text-gray-500 mt-1">Coming next</p>
        </section>

        {/* Section 2: Matrix Preview — placeholder */}
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold">2. Matrix Preview</h2>
          <p className="text-sm text-gray-500 mt-1">Coming next</p>
        </section>

        {/* Section 3: Configure & Run — placeholder */}
        <section className="bg-white rounded-lg border border-gray-200 p-6 opacity-50">
          <h2 className="text-base font-semibold">3. Configure & Run</h2>
          <p className="text-sm text-gray-500 mt-1">Load data first</p>
        </section>

        {/* Section 4: Results — placeholder */}
        <section className="bg-white rounded-lg border border-gray-200 p-6 opacity-50">
          <h2 className="text-base font-semibold">4. Results</h2>
          <p className="text-sm text-gray-500 mt-1">Run an optimization first</p>
        </section>
      </main>
    </div>
  );
}
