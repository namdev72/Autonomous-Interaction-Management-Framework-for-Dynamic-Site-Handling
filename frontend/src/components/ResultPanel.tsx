export function ResultPanel({ result }: { result: any }) {
  if (!result) return null;
  const comparison = result.extracted_data?.answer ? result.extracted_data : null;
  const regularData = result.extracted_data && !comparison
    ? Object.entries(result.extracted_data)
    : [];

  return (
    <div className="flex flex-col gap-3 p-6 bg-slate-900 rounded-xl shadow-lg border border-slate-800 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <h2 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
          Task Result
        </h2>
      </div>

      <div className="space-y-4 pt-2">
        {comparison && (
          <div className="p-4 bg-slate-950 rounded border border-slate-800">
            <span className="block text-slate-500 mb-3 uppercase text-xs font-semibold tracking-wider">Answer</span>
            <p className="text-slate-200 whitespace-pre-wrap">{comparison.answer}</p>
            {comparison.offers?.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-slate-500 border-b border-slate-800">
                    <tr><th className="py-2 pr-3">Site</th><th className="py-2 pr-3">Product</th><th className="py-2 pr-3">Price</th><th className="py-2">Rating</th></tr>
                  </thead>
                  <tbody>
                    {comparison.offers.map((offer: any) => (
                      <tr key={`${offer.site}-${offer.product_url}`} className="border-b border-slate-900 text-slate-300">
                        <td className="py-2 pr-3">{offer.site}</td>
                        <td className="py-2 pr-3 max-w-xs">{offer.title}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{offer.currency} {offer.price?.toLocaleString()}</td>
                        <td className="py-2">{offer.rating ?? 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {comparison.warnings?.length > 0 && (
              <div className="mt-4 text-sm text-amber-300">
                {comparison.warnings.map((warning: string) => <p key={warning}>{warning}</p>)}
              </div>
            )}
          </div>
        )}

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

        {regularData.length > 0 && (
          <div className="p-4 bg-slate-950 rounded border border-slate-800">
             <span className="block text-slate-500 mb-3 uppercase text-xs font-semibold tracking-wider">Extracted Data</span>
             <div className="space-y-2">
                {regularData.map(([key, value]) => (
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
