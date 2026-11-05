# Indian Mutual Fund AI Evaluation Agent

A production-grade, **stateless on-demand AI Analyst** for evaluating Indian Mutual Funds.

When a user asks to evaluate a mutual fund or compare multiple schemes, the agent:
1. **Resolves AMFI Scheme Codes Live** via `mfapi.in`, automatically prioritizing **Direct Plan - Growth** schemes.
2. **Fetches Live Daily NAV & SEBI Benchmark TRI History** (`Nifty 50 TRI`, `Nifty 500 TRI`, `Nifty Midcap 150 TRI`, `Nifty Smallcap 250 TRI`).
3. **Scrapes Live Fund Fundamentals & Portfolio Disclosures** (Expense Ratio/TER, AUM in ₹ Crores, Exit Load, Fund Manager & Tenure, Top 25 Stock Holdings, Sector Split, and Category Peers).
4. **Runs Gemini Google Search Grounding** (`google-genai` Interactions API with `gemini-3.8-flash`) for recent manager commentary, AMC developments, and qualitative context.
5. **Computes a Deterministic 100-Point Composite Score in Memory** (`numpy` / `pandas`) across 5 institutional pillars—delivering an actionable verdict (`STRONG CONTENDER / CORE BUY`, `WORTH CONSIDERING / HOLD`, `WATCHLIST / NEUTRAL`, or `AVOID / SWITCH CANDIDATE`) with detailed strengths, red flags, and suitability advice.

---

## 100-Point Scoring Rubric

| Pillar | Max Score | Key Quantitative & Qualitative Signals |
| :--- | :---: | :--- |
| **1. Performance Consistency** | **30 pts** | 3Y & 5Y Daily Rolling Return Median vs Benchmark + % of Rolling Windows Outperforming Benchmark |
| **2. Downside Protection & Risk** | **25 pts** | Monthly Downside Capture Ratio, Sortino Ratio vs Benchmark, Max Drawdown & Ulcer Index |
| **3. Alpha & Risk-Adjusted Return** | **20 pts** | Annualized 3Y Jensen's Alpha ($\alpha$), CAPM Beta ($\beta$), Sharpe Ratio, Information Ratio |
| **4. Cost, Size & Liquidity Health** | **15 pts** | Direct Expense Ratio (TER %) + AUM Bloat / Liquidity Assessment (especially for Small/Mid-Cap funds) |
| **5. Portfolio & Manager Quality** | **10 pts** | Lead Fund Manager Tenure Stability + Top-10 Holdings Concentration Balance |

---

## Quickstart

### 1. Backend & Embedded Interactive Dashboard (Zero Node.js Required)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: configure your Gemini API key for AI synthesis & Google Search Grounding
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=...

# Start the FastAPI server + Interactive Dashboard
uvicorn app.main:app --reload --port 8000
```

Open **`http://localhost:8000`** in your browser to use the split-screen **AI Analyst Chat + 100-Point Live Scorecard + Rolling Return & Drawdown Charts + Holdings/Overlap Dashboard**.

### 2. Run Unit Tests

```bash
cd backend
PYTHONPATH=. pytest -v
```

### 3. Optional Standalone Next.js Frontend

```bash
cd frontend
npm install
npm run dev
```
