export function ResultPanel({ result }: { result: any }) {
  if (!result) return null;

  return (
    <div className="flex flex-col gap-3 p-6 bg-slate-900 rounded-xl shadow-lg border border-slate-800 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <h2 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
          Task Result
        </h2>
      </div>

      <div className="space-y-4 pt-2">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="p-3 bg-slate-950 rounded border border-slate-800">
            <span className="block text-slate-500 mb-1 uppercase text-xs font-semibold tracking-wider">Status</span>
            <span className={result.completed ? 'text-green-400' : 'text-red-400 font-medium'}>
              {result.completed ? 'Completed Successfully' : `Failed (${result.reason})`}
            </span>
          </div>
          <div className="p-3 bg-slate-950 rounded border border-slate-800">
            <span className="block text-slate-500 mb-1 uppercase text-xs font-semibold tracking-wider">Iterations</span>
            <span className="text-slate-300 font-mono">{result.iterations}</span>
          </div>
        </div>

        {result.extracted_data && Object.keys(result.extracted_data).length > 0 && (
          <div className="p-4 bg-slate-950 rounded border border-slate-800">
             <span className="block text-slate-500 mb-3 uppercase text-xs font-semibold tracking-wider">Extracted Data</span>
             <div className="space-y-2">
                {Object.entries(result.extracted_data).map(([key, value]) => (
                  <div key={key} className="flex flex-col text-sm border-l-2 border-blue-500 pl-3 py-1">
                     <span className="text-slate-400 font-mono text-xs mb-1">{key}</span>
                     <span className="text-slate-200">{String(value)}</span>
                  </div>
                ))}
             </div>
          </div>
        )}
      </div>
    </div>
  );
}
