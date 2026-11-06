import React from "react";

export function RollingReturnChart({
  quantReport,
  comparedFunds,
  activeFundIndex,
  onSelectComparedFund,
}: {
  quantReport: any;
  comparedFunds?: any[];
  activeFundIndex?: number;
  onSelectComparedFund?: (idx: number) => void;
}) {
  const horizons = ["1Y", "3Y", "5Y", "7Y", "10Y"];
  const trMap = quantReport?.trailing_returns_cagr_pct || {};
  const rlMap = quantReport?.rolling_returns || {};
  const rm = quantReport?.risk_metrics || {};

  return (
    <div className="space-y-5">
      {comparedFunds && comparedFunds.length >= 2 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Multi-Fund Head-to-Head Leaderboard ({comparedFunds.length} Funds)
              </h3>
              <p className="text-xs text-slate-500">
                Click any row to inspect that fund&apos;s detailed 100-Point Scorecard and holdings.
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-700 border-y border-slate-200 font-semibold">
                  <th className="py-2 px-3">Rank</th>
                  <th className="py-2 px-3">Mutual Fund</th>
                  <th className="py-2 px-3 text-center">Score</th>
                  <th className="py-2 px-3">Verdict</th>
                  <th className="py-2 px-3 text-right">3Y Rolling Median</th>
                  <th className="py-2 px-3 text-right">3Y Beat %</th>
                  <th className="py-2 px-3 text-right">3Y Alpha</th>
                  <th className="py-2 px-3 text-right">Sortino</th>
                  <th className="py-2 px-3 text-right">Downside Cap</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {comparedFunds.map((f, idx) => {
                  const sc = f.scorecard;
                  const qr = f.quant_report;
                  const r3 = qr?.rolling_returns?.["3Y"] || qr?.rolling_returns?.["1Y"];
                  const isSelected = idx === activeFundIndex;
                  return (
                    <tr
                      key={f.scheme_code}
                      onClick={() => onSelectComparedFund?.(idx)}
                      className={`cursor-pointer ${
                        isSelected ? "bg-blue-50 font-medium" : "hover:bg-slate-50"
                      }`}
                    >
                      <td className="py-2.5 px-3 font-bold text-slate-700">#{idx + 1}</td>
                      <td className="py-2.5 px-3 font-semibold text-slate-900">{f.scheme_name}</td>
                      <td className="py-2.5 px-3 text-center font-bold">
                        {sc.total_score} ({sc.letter_grade})
                      </td>
                      <td className="py-2.5 px-3 text-emerald-700 font-semibold">{sc.verdict}</td>
                      <td className="py-2.5 px-3 text-right">
                        {r3 ? `${r3.fund_median_cagr_pct}%` : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold text-blue-700">
                        {r3 ? `${r3.outperformance_consistency_pct}%` : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold">
                        {qr?.risk_metrics?.jensen_alpha_pct}%
                      </td>
                      <td className="py-2.5 px-3 text-right">{qr?.risk_metrics?.sortino_ratio}</td>
                      <td className="py-2.5 px-3 text-right">
                        {qr?.risk_metrics?.downside_capture_ratio}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
        <div className="md:col-span-7 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
            Trailing vs Daily Rolling Return Consistency
          </h3>
          <table className="w-full text-xs text-left border-collapse">
            <thead>
              <tr className="bg-slate-100 text-slate-700 border-y border-slate-200 font-semibold">
                <th className="py-2 px-2.5">Horizon</th>
                <th className="py-2 px-2.5 text-right">Fund CAGR</th>
                <th className="py-2 px-2.5 text-right">Benchmark</th>
                <th className="py-2 px-2.5 text-right">Rolling Median</th>
                <th className="py-2 px-2.5 text-right">Rolling Beat %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-700">
              {horizons.map((h) => {
                const tr = trMap[h] || {};
                const rl = rlMap[h];
                if (tr.fund_cagr_pct == null && !rl) return null;
                return (
                  <tr key={h}>
                    <td className="py-2 px-2.5 font-bold text-slate-800">{h}</td>
                    <td className="py-2 px-2.5 text-right font-semibold text-slate-900">
                      {tr.fund_cagr_pct != null ? `${tr.fund_cagr_pct}%` : "—"}
                    </td>
                    <td className="py-2 px-2.5 text-right text-slate-500">
                      {tr.benchmark_cagr_pct != null ? `${tr.benchmark_cagr_pct}%` : "—"}
                    </td>
                    <td className="py-2 px-2.5 text-right">
                      {rl ? `${rl.fund_median_cagr_pct}%` : "—"}
                    </td>
                    <td className="py-2 px-2.5 text-right font-bold text-emerald-700">
                      {rl ? `${rl.outperformance_consistency_pct}%` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="md:col-span-5 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
            Risk, Alpha & Market Capture Ratios (3Y)
          </h3>
          <div className="grid grid-cols-2 gap-2.5 text-xs">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-slate-500">Jensen&apos;s Alpha</div>
              <div className="text-sm font-bold text-emerald-700 mt-0.5">
                {rm.jensen_alpha_pct}%
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-slate-500">Sharpe Ratio</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">{rm.sharpe_ratio}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-slate-500">Sortino Ratio</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">{rm.sortino_ratio}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-slate-500">Beta</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">{rm.beta}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-slate-500">Upside Capture</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">
                {rm.upside_capture_ratio}%
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-slate-500">Downside Capture</div>
              <div className="text-sm font-bold text-emerald-700 mt-0.5">
                {rm.downside_capture_ratio}%
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
