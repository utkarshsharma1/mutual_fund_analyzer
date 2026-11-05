import React from "react";
import { FundScorecardData } from "../lib/api";

export function FundScorecard({
  scorecard,
  latestNav,
  latestNavDate,
  expenseRatio,
  aumCrores,
}: {
  scorecard: FundScorecardData;
  latestNav?: number;
  latestNavDate?: string;
  expenseRatio?: number | null;
  aumCrores?: number | null;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <span className="text-xs font-medium px-2.5 py-0.5 rounded bg-slate-800 text-blue-300">
            {scorecard.sebi_category}
          </span>
          <h2 className="text-xl font-bold text-white mt-1">{scorecard.scheme_name}</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Benchmark: {scorecard.benchmark_name}
            {latestNav ? ` • NAV: ₹${latestNav} (${latestNavDate})` : ""}
            {expenseRatio != null ? ` • TER: ${expenseRatio}%` : ""}
            {aumCrores != null ? ` • AUM: ₹${aumCrores.toLocaleString()} Cr` : ""}
          </p>
        </div>

        <div className="flex items-center gap-4 bg-slate-950 px-4 py-3 rounded-xl border border-slate-800">
          <div className="text-right">
            <div className="text-[11px] uppercase text-slate-400">100-Pt Verdict</div>
            <div className="text-xs font-bold text-emerald-400">{scorecard.verdict}</div>
          </div>
          <div className="w-16 h-16 rounded-full border-2 border-emerald-500 flex flex-col items-center justify-center">
            <span className="text-xl font-extrabold text-white">{scorecard.total_score}</span>
            <span className="text-[10px] font-semibold text-emerald-400">
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
              className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 flex flex-col justify-between"
            >
              <div>
                <div className="text-[11px] text-slate-400 font-medium">{pillar.name}</div>
                <div className="text-base font-bold text-white mt-0.5">
                  {pillar.score}{" "}
                  <span className="text-xs text-slate-500">/ {pillar.max_score}</span>
                </div>
              </div>
              <div className="mt-2">
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-emerald-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="text-[10px] text-emerald-400 mt-1 font-medium">
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

