"use client";

import React, { useState } from "react";
import { AgentResponsePayload, sendChatQuery } from "../lib/api";
import { ChatPanel } from "../components/ChatPanel";
import { FundScorecard } from "../components/FundScorecard";
import { RollingReturnChart } from "../components/RollingReturnChart";
import { HoldingsView } from "../components/HoldingsView";

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState<AgentResponsePayload | null>(null);

  const handleQuery = async (query: string) => {
    setLoading(true);
    try {
      const res = await sendChatQuery(query, payload?.interaction_id);
      setPayload(res);
    } finally {
      setLoading(false);
    }
  };

  const primary = payload?.primary_fund;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
      <section className="lg:col-span-5">
        <ChatPanel
          onSubmitQuery={handleQuery}
          loading={loading}
          executionSteps={payload?.execution_steps || []}
          markdownReport={payload?.markdown_report || ""}
        />
      </section>
      <section className="lg:col-span-7 space-y-5">
        {primary && (
          <>
            <FundScorecard
              scorecard={primary.scorecard}
              latestNav={primary.latest_nav}
              latestNavDate={primary.latest_nav_date}
              expenseRatio={primary.fundamentals?.expense_ratio_pct}
              aumCrores={primary.fundamentals?.aum_crores}
            />
            <RollingReturnChart
              rollingData={primary.quant_report?.chart_rolling_3y || []}
              drawdownData={primary.quant_report?.chart_drawdown || []}
            />
            <HoldingsView
              holdings={primary.fundamentals?.top_holdings || []}
              sectorAllocation={primary.fundamentals?.sector_allocation || {}}
              overlapAnalysis={payload?.overlap_analysis}
            />
          </>
        )}
      </section>
    </main>
  );
}

