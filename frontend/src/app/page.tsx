"use client";

import React, { useState } from "react";
import {
  AgentResponsePayload,
  compareMultipleFunds,
  sendChatQuery,
} from "../lib/api";
import { ChatPanel } from "../components/ChatPanel";
import { FundScorecard } from "../components/FundScorecard";
import { RollingReturnChart } from "../components/RollingReturnChart";
import { HoldingsView } from "../components/HoldingsView";

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState<AgentResponsePayload | null>(null);
  const [activeFundIdx, setActiveFundIdx] = useState(0);

  const handleQuery = async (query: string) => {
    setLoading(true);
    try {
      const res = await sendChatQuery(query, payload?.interaction_id);
      setPayload(res);
      setActiveFundIdx(0);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async (queries: string[]) => {
    setLoading(true);
    try {
      const res = await compareMultipleFunds(queries);
      setPayload(res);
      setActiveFundIdx(0);
    } finally {
      setLoading(false);
    }
  };

  const activeFund =
    payload?.compared_funds && payload.compared_funds.length >= 2
      ? payload.compared_funds[activeFundIdx] || payload.primary_fund
      : payload?.primary_fund;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
      <section className="lg:col-span-5">
        <ChatPanel
          onSubmitQuery={handleQuery}
          onCompareMultiple={handleCompare}
          loading={loading}
          executionSteps={payload?.execution_steps || []}
          markdownReport={payload?.markdown_report || ""}
        />
      </section>
      <section className="lg:col-span-7 space-y-5">
        {activeFund && (
          <>
            <FundScorecard
              scorecard={activeFund.scorecard}
              latestNav={activeFund.latest_nav}
              latestNavDate={activeFund.latest_nav_date}
              expenseRatio={activeFund.fundamentals?.expense_ratio_pct}
              aumCrores={activeFund.fundamentals?.aum_crores}
              fundManager={activeFund.fundamentals?.fund_manager}
            />
            <RollingReturnChart
              quantReport={activeFund.quant_report}
              comparedFunds={payload?.compared_funds}
              activeFundIndex={activeFundIdx}
              onSelectComparedFund={setActiveFundIdx}
            />
            <HoldingsView
              holdings={activeFund.fundamentals?.top_holdings || []}
              sectorAllocation={activeFund.fundamentals?.sector_allocation || {}}
              overlapAnalysis={payload?.overlap_analysis}
            />
          </>
        )}
      </section>
    </main>
  );
}
