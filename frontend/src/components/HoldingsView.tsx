import React from "react";

export function HoldingsView({
  holdings,
  sectorAllocation,
  overlapAnalysis,
}: {
  holdings: Array<{ company_name: string; weight_pct: number; sector?: string }>;
  sectorAllocation: Record<string, number>;
  overlapAnalysis?: any;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
          Live Scraped Top Portfolio Holdings
        </h3>
        <div className="space-y-1.5 text-xs text-slate-700 max-h-60 overflow-y-auto">
          {holdings.slice(0, 15).map((h, idx) => (
            <div
              key={h.company_name}
              className="flex items-center justify-between py-1.5 border-b border-slate-100"
            >
              <div>
                <span className="text-slate-400 font-mono mr-1">{idx + 1}.</span>
                <span className="font-semibold text-slate-800">{h.company_name}</span>
                {h.sector && (
                  <span className="text-[10px] text-slate-500 ml-1.5 px-1.5 py-0.5 rounded bg-slate-100">
                    {h.sector}
                  </span>
                )}
              </div>
              <span className="font-bold text-emerald-700">{h.weight_pct}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
          {overlapAnalysis?.pairwise_overlap?.length
            ? "Pairwise Portfolio Holdings Overlap"
            : "Sector Allocation (%)"}
        </h3>
        {overlapAnalysis?.pairwise_overlap?.length ? (
          <div className="space-y-2 text-xs">
            {overlapAnalysis.pairwise_overlap.map((pair: any, idx: number) => (
              <div key={idx} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex justify-between font-semibold text-slate-900">
                  <span>
                    {pair.fund_a} ↔ {pair.fund_b}
                  </span>
                  <span className="text-blue-700">{pair.weight_overlap_pct}% Overlap</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  {pair.common_stocks_count} Common Stocks • {pair.diagnosis}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2 text-xs">
            {Object.entries(sectorAllocation || {}).map(([sector, weight]) => (
              <div key={sector} className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-700 font-medium">{sector}</span>
                  <span className="font-bold text-blue-700">{weight}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600"
                    style={{ width: `${Math.min(100, Number(weight) * 2)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
