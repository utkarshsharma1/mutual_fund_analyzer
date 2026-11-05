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
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Live Scraped Top Portfolio Holdings
        </h3>
        <div className="space-y-2 text-xs text-slate-200 max-h-60 overflow-y-auto">
          {holdings.slice(0, 12).map((h) => (
            <div
              key={h.company_name}
              className="flex items-center justify-between py-1 border-b border-slate-800/60"
            >
              <div>
                <span className="font-medium">{h.company_name}</span>
                {h.sector && <span className="text-[10px] text-slate-500 ml-1.5">{h.sector}</span>}
              </div>
              <span className="font-semibold text-emerald-400">{h.weight_pct}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          {overlapAnalysis?.pairwise_overlap?.length
            ? "Pairwise Portfolio Holdings Overlap"
            : "Sector Allocation (%)"}
        </h3>
        {overlapAnalysis?.pairwise_overlap?.length ? (
          <div className="space-y-2 text-xs">
            {overlapAnalysis.pairwise_overlap.map((pair: any, idx: number) => (
              <div key={idx} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                <div className="flex justify-between font-semibold text-white">
                  <span>
                    {pair.fund_a} ↔ {pair.fund_b}
                  </span>
                  <span className="text-blue-400">{pair.weight_overlap_pct}% Overlap</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
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
                  <span className="text-slate-300">{sector}</span>
                  <span className="font-semibold text-blue-400">{weight}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500"
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

