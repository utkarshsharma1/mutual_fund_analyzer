import React from "react";
import { FundScorecardData } from "../lib/api";

export function FundScorecard({
  scorecard,
  latestNav,
  latestNavDate,
  expenseRatio,
  aumCrores,
  fundManager,
}: {
  scorecard: FundScorecardData;
  latestNav?: number;
  latestNavDate?: string;
  expenseRatio?: number | null;
  aumCrores?: number | null;
  fundManager?: string | null;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4 shadow-xs">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
            {scorecard.sebi_category}
          </span>
          <h2 className="text-xl font-bold text-slate-900 mt-1">{scorecard.scheme_name}</h2>
          <p className="text-xs text-slate-500 mt-1">
            Benchmark: {scorecard.benchmark_name}
            {latestNav ? ` • NAV: ₹${latestNav} (${latestNavDate})` : ""}
            {expenseRatio != null ? ` • TER: ${expenseRatio}%` : ""}
            {aumCrores != null ? ` • AUM: ₹${aumCrores.toLocaleString()} Cr` : ""}
            {fundManager ? ` • Manager: ${fundManager}` : ""}
          </p>
        </div>

        <div className="flex items-center gap-4 bg-slate-50 px-4 py-3 rounded-xl border border-slate-200">
          <div className="text-right">
            <div className="text-[11px] uppercase font-semibold text-slate-500">100-Pt Verdict</div>
            <div className="text-xs font-bold text-emerald-700">{scorecard.verdict}</div>
          </div>
          <div className="w-16 h-16 rounded-full bg-white border-2 border-emerald-500 flex flex-col items-center justify-center shadow-xs">
            <span className="text-xl font-extrabold text-slate-900">{scorecard.total_score}</span>
            <span className="text-[10px] font-bold text-emerald-700">
              Grade {scorecard.letter_grade}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {scorecard.pillars.map((pillar) => {
          const pct = Math.round((pillar.score / pillar.max_score) * 100);
          return (
            <div
              key={pillar.name}
              title={pillar.rationale}
              className="bg-slate-50 p-3 rounded-lg border border-slate-200 flex flex-col justify-between"
            >
              <div>
                <div className="text-[11px] text-slate-500 font-semibold">{pillar.name}</div>
                <div className="text-base font-extrabold text-slate-900 mt-0.5">
                  {pillar.score}{" "}
                  <span className="text-xs font-normal text-slate-400">/ {pillar.max_score}</span>
                </div>
              </div>
              <div className="mt-2">
                <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="text-[10px] text-blue-700 mt-1 font-semibold">
                  {pillar.rating_label}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
