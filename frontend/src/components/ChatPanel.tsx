import React, { useState } from "react";

export function ChatPanel({
  onSubmitQuery,
  onCompareMultiple,
  loading,
  executionSteps,
  markdownReport,
}: {
  onSubmitQuery: (query: string) => void;
  onCompareMultiple: (queries: string[]) => void;
  loading: boolean;
  executionSteps: string[];
  markdownReport: string;
}) {
  const [mode, setMode] = useState<"single" | "compare">("single");
  const [input, setInput] = useState("");
  const [compareList, setCompareList] = useState<string[]>([
    "Parag Parikh Flexi Cap Fund Direct Growth",
    "HDFC Flexi Cap Fund Direct Growth",
    "JM Flexicap Fund Direct Growth",
    "Quant Flexi Cap Fund Direct Growth",
    "Kotak Flexicap Fund Direct Growth",
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSubmitQuery(input.trim());
  };

  const handleCompareSubmit = () => {
    const valid = compareList.map((s) => s.trim()).filter(Boolean);
    if (valid.length >= 2 && !loading) {
      onCompareMultiple(valid);
    }
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs">
        <div className="flex rounded-lg bg-slate-100 p-1 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setMode("single")}
            className={`flex-1 py-2 px-3 rounded-md ${
              mode === "single" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600"
            }`}
          >
            Single Fund / AI Chat
          </button>
          <button
            type="button"
            onClick={() => setMode("compare")}
            className={`flex-1 py-2 px-3 rounded-md ${
              mode === "compare" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600"
            }`}
          >
            Compare Multiple Funds (5+)
          </button>
        </div>

        {mode === "single" ? (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask to evaluate a mutual fund or compare funds..."
              className="flex-1 bg-white border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm text-slate-900"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 font-semibold text-sm text-white disabled:opacity-50"
            >
              {loading ? "Analyzing..." : "Analyze Live"}
            </button>
          </form>
        ) : (
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs text-slate-600">
              <span>Compare 5+ Mutual Funds Side-by-Side:</span>
              {compareList.length < 10 && (
                <button
                  type="button"
                  onClick={() => setCompareList([...compareList, ""])}
                  className="font-semibold text-blue-600"
                >
                  + Add Another Fund
                </button>
              )}
            </div>
            {compareList.map((val, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-400 w-5">#{idx + 1}</span>
                <input
                  type="text"
                  value={val}
                  onChange={(e) => {
                    const next = [...compareList];
                    next[idx] = e.target.value;
                    setCompareList(next);
                  }}
                  placeholder={`Mutual Fund #${idx + 1}`}
                  className="flex-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900"
                />
                {compareList.length > 2 && (
                  <button
                    type="button"
                    onClick={() => setCompareList(compareList.filter((_, i) => i !== idx))}
                    className="text-slate-400 hover:text-rose-600 text-xs font-bold px-1"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={handleCompareSubmit}
              disabled={loading}
              className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-700 font-semibold text-xs text-white"
            >
              {loading ? "Comparing Funds..." : `Compare ${compareList.filter(Boolean).length} Funds`}
            </button>
          </div>
        )}

        {executionSteps.length > 0 && (
          <div className="text-xs text-slate-600 bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-1">
            {executionSteps.map((s, idx) => (
              <div key={idx}>✓ {s}</div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 flex-1 overflow-y-auto shadow-xs">
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-800 leading-relaxed">
          {markdownReport ||
            "Enter an Indian Mutual Fund name above or compare 5+ funds to generate a live 100-Point Evaluation."}
        </pre>
      </div>
    </div>
  );
}
