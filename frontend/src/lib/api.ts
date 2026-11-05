/**
 * Typed API Client for the Stateless Indian Mutual Fund Evaluation Agent Backend.
 */

export interface PillarScore {
  name: string;
  score: number;
  max_score: number;
  rating_label: string;
  rationale: string;
}

export interface FundScorecardData {
  scheme_code: number;
  scheme_name: string;
  sebi_category: string;
  benchmark_name: string;
  total_score: number;
  max_score: number;
  letter_grade: string;
  verdict: string;
  verdict_badge_color: string;
  executive_summary: string;
  pillars: PillarScore[];
  strengths: string[];
  risks_and_red_flags: string[];
  investor_suitability: Record<string, string>;
}

export interface AgentResponsePayload {
  query: string;
  interaction_id?: string | null;
  markdown_report: string;
  primary_fund?: any;
  compared_funds: any[];
  overlap_analysis?: any;
  execution_steps: string[];
  citations: Array<{ title: string; url: string }>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function sendChatQuery(
  message: string,
  previousInteractionId?: string | null
): Promise<AgentResponsePayload> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      previous_interaction_id: previousInteractionId || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to evaluate mutual fund");
  }
  return res.json();
}

