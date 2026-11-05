import React, { useState } from "react";

export function ChatPanel({
  onSubmitQuery,
  loading,
  executionSteps,
  markdownReport,
}: {
  onSubmitQuery: (query: string) => void;
  loading: boolean;
  executionSteps: string[];
  markdownReport: string;
}) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSubmitQuery(input.trim());
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask to evaluate a mutual fund or compare funds..."
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-white"
          />
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 font-semibold text-sm text-white disabled:opacity-50"
          >
            {loading ? "Analyzing..." : "Analyze Live"}
          </button>
        </form>
        {executionSteps.length > 0 && (
          <div className="text-xs text-slate-400 bg-slate-950 rounded-lg p-3 border border-slate-800 space-y-1">
            {executionSteps.map((s, idx) => (
              <div key={idx}>✓ {s}</div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 flex-1 overflow-y-auto">
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200 leading-relaxed">
          {markdownReport || "Enter an Indian Mutual Fund name above to generate a live 100-Point Evaluation."}
        </pre>
      </div>
    </div>
  );
}

