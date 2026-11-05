import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";

export function RollingReturnChart({
  rollingData,
  drawdownData,
}: {
  rollingData: Array<{ date: string; fund_rolling_cagr: number; benchmark_rolling_cagr: number }>;
  drawdownData: Array<{ date: string; fund_drawdown_pct: number; benchmark_drawdown_pct: number }>;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          3Y Rolling Return (%) — Fund vs Benchmark
        </h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rollingData}>
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="fund_rolling_cagr"
                name="Fund Rolling CAGR %"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="benchmark_rolling_cagr"
                name="Benchmark Rolling CAGR %"
                stroke="#64748b"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Underwater Drawdown Curve (%)
        </h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={drawdownData}>
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="fund_drawdown_pct"
                name="Fund Drawdown %"
                stroke="#f43f5e"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="benchmark_drawdown_pct"
                name="Benchmark Drawdown %"
                stroke="#64748b"
                strokeDasharray="3 3"
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

