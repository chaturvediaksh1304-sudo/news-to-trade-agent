"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import Cursor from "../components/Cursor";
import EquityCurve from "../components/EquityCurve";
import Intro from "../components/Intro";
import TickerLogo from "../components/TickerLogo";

type Reasoning = {
  id: number;
  ticker: string;
  headlines: string[];
  sentiment_score: number;
  debate_transcript: { bull?: string; bear?: string; risk?: string };
  decision: string;
  confidence: number;
  size_rationale: string;
  created_at: string;
};

type Trade = {
  id: number;
  ticker: string;
  side: string;
  qty: number;
  notional: number;
  stop_loss: number | null;
  take_profit: number | null;
  dry_run: 0 | 1;
  created_at: string;
};

type DaySummary = {
  date: string;
  trades: Trade[];
  buys: number;
  sells: number;
  notional: number;
  avgConfidence: number | null;
};

type State = {
  trades: Trade[];
  days: DaySummary[];
  reasoning: Reasoning[];
  equity: { date: string; equity: number }[];
  lastRun: string | null;
};

const EMPTY: State = { trades: [], days: [], reasoning: [], equity: [], lastRun: null };

function swarmActive(lastRun: string | null): boolean {
  if (!lastRun) return false;
  return Date.now() - new Date(lastRun + "Z").getTime() < 30 * 60 * 1000;
}

function dayLabel(date: string): string {
  return new Date(date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

const reveal = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] as const },
};

export default function Home() {
  const [state, setState] = useState<State>(EMPTY);
  const [selectedDays, setSelectedDays] = useState<string[]>([]);

  useEffect(() => {
    const load = () =>
      fetch("/api/state")
        .then((r) => r.json())
        .then((s: State) => {
          setState(s);
          setSelectedDays((prev) =>
            prev.length > 0 ? prev : s.days.slice(0, 2).map((d) => d.date)
          );
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, []);

  const toggleDay = (date: string) =>
    setSelectedDays((prev) =>
      prev.includes(date)
        ? prev.filter((d) => d !== date)
        : [...prev, date].slice(-3) // compare up to 3 days side by side
    );

  const active = swarmActive(state.lastRun);
  const tickers = [...new Set(state.trades.map((t) => t.ticker))];
  const equityNow = state.equity.at(-1)?.equity ?? null;
  const avgConfidence =
    state.reasoning.length > 0
      ? state.reasoning.reduce((s, r) => s + r.confidence, 0) / state.reasoning.length
      : null;
  const compared = state.days.filter((d) => selectedDays.includes(d.date));

  return (
    <>
      <Cursor />
      <Intro />

      <div className="glow-layer">
        <div className="glow a" />
        <div className="glow b" />
      </div>

      <nav>
        <div className="brand">NEWS-TO-TRADE&reg;</div>
        <div className="links">
          <a href="#history">History</a>
          <a href="#reasoning">Reasoning</a>
          <a href="#trades">Trades</a>
          <a href="#performance">Performance</a>
          <span className="status">
            <span className={`dot${active ? " active" : ""}`} />
            {active ? "swarm active" : "idle"}
          </span>
        </div>
      </nav>

      <main>
        <section className="hero">
          <motion.h1
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 3.4, ease: [0.22, 1, 0.36, 1] }}
          >
            Every trade argued on the record.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.9, delay: 3.8 }}
          >
            An agent swarm that reads the day&apos;s S&amp;P 500 news, debates
            bull against bear, and paper-trades the verdict — with the full
            reasoning chain published for every decision.
          </motion.p>
          <motion.div
            className="scroll-cue"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 4.3 }}
          >
            <motion.span
              className="line"
              animate={{ scaleY: [0, 1, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
            />
            Scroll
          </motion.div>
        </section>

        <div className="photo-wrap">
          <div className="photo-bg" aria-hidden>
            <img src="/wall-street.jpg" alt="" />
            <div className="shade" />
          </div>

        <motion.section className="section" {...reveal}>
          <div className="kicker">Track record</div>
          <div className="stats">
            <div className="stat glass">
              <div className="num">{state.trades.length}</div>
              <div className="label">Trades executed by the swarm</div>
              <div className="logos">
                {tickers.slice(0, 4).map((t) => (
                  <TickerLogo key={t} ticker={t} />
                ))}
              </div>
            </div>
            <div className="stat glass">
              <div className="num">{state.reasoning.length}</div>
              <div className="label">Decisions logged with full debate transcripts</div>
            </div>
            <div className="stat glass">
              <div className="num">
                {avgConfidence !== null ? `${Math.round(avgConfidence * 100)}%` : "—"}
              </div>
              <div className="label">Average decision confidence</div>
            </div>
            <div className="stat glass">
              <div className="num">
                {equityNow !== null
                  ? `$${Math.round(equityNow / 1000).toLocaleString()}k`
                  : "—"}
              </div>
              <div className="label">Paper account equity</div>
            </div>
          </div>
        </motion.section>

        <motion.section className="section" id="history" {...reveal}>
          <div className="kicker">Trading history — last 7 days</div>
          {state.days.length === 0 ? (
            <p className="empty">No trades in the last week.</p>
          ) : (
            <>
              <div className="day-chips">
                {state.days.map((d) => (
                  <button
                    key={d.date}
                    className={`day-chip${selectedDays.includes(d.date) ? " selected" : ""}`}
                    onClick={() => toggleDay(d.date)}
                  >
                    {dayLabel(d.date)}
                    <span className="count">{d.trades.length}</span>
                  </button>
                ))}
              </div>
              <div
                className="compare-grid"
                style={{
                  gridTemplateColumns: `repeat(${Math.max(compared.length, 1)}, 1fr)`,
                }}
              >
                {compared.map((d) => (
                  <motion.div
                    key={d.date}
                    className="day-col glass"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <div className="date">{dayLabel(d.date)}</div>
                    <div className="day-stats">
                      <div className="day-stat">
                        <div className="v">{d.trades.length}</div>
                        <div className="k">Trades</div>
                      </div>
                      <div className="day-stat">
                        <div className="v">
                          <span className="buy">{d.buys}</span>
                          {" / "}
                          <span className="sell">{d.sells}</span>
                        </div>
                        <div className="k">Buy / Sell</div>
                      </div>
                      <div className="day-stat">
                        <div className="v">
                          ${Math.round(d.notional / 1000).toLocaleString()}k
                        </div>
                        <div className="k">Notional</div>
                      </div>
                      <div className="day-stat">
                        <div className="v">
                          {d.avgConfidence !== null
                            ? `${Math.round(d.avgConfidence * 100)}%`
                            : "—"}
                        </div>
                        <div className="k">Confidence</div>
                      </div>
                    </div>
                    {d.trades.map((t) => (
                      <div className="day-trade" key={t.id}>
                        <TickerLogo ticker={t.ticker} />
                        {t.ticker}
                        <span className={t.side === "buy" ? "buy" : "sell"}>
                          {t.side}
                        </span>
                        <span className="amt">
                          ${t.notional.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    ))}
                  </motion.div>
                ))}
                {compared.length === 0 && (
                  <p className="empty">Select a day above to inspect it.</p>
                )}
              </div>
            </>
          )}
        </motion.section>

        <section className="section" id="reasoning">
          <motion.div className="kicker" {...reveal}>
            Reasoning chain
          </motion.div>
          {state.reasoning.length === 0 && (
            <p className="empty">No decisions logged yet — run the pipeline.</p>
          )}
          <div className="cards">
            {state.reasoning.map((r, i) => (
              <motion.article className="card glass" key={r.id} {...reveal}>
                <div className="index">{String(i + 1).padStart(2, "0")}</div>
                <div className="title">
                  <TickerLogo ticker={r.ticker} />
                  {r.ticker}
                  <span className={r.decision === "buy" ? "buy" : "sell"}>
                    {r.decision}
                  </span>
                </div>
                <div className="meta">
                  sentiment {r.sentiment_score.toFixed(2)} · confidence{" "}
                  {(r.confidence * 100).toFixed(0)}% · {r.created_at.slice(0, 16)}
                </div>
                {r.headlines[0] && (
                  <div className="headline">“{r.headlines[0]}”</div>
                )}
                {r.debate_transcript.bull && (
                  <p className="argument">
                    <b>Bull</b> — {r.debate_transcript.bull}
                  </p>
                )}
                {r.debate_transcript.bear && (
                  <p className="argument">
                    <b>Bear</b> — {r.debate_transcript.bear}
                  </p>
                )}
                {r.debate_transcript.risk && (
                  <p className="argument">
                    <b>Risk</b> — {r.debate_transcript.risk}
                  </p>
                )}
                <p className="argument">
                  <b>Sizing</b> — {r.size_rationale}
                </p>
              </motion.article>
            ))}
          </div>
        </section>

        <motion.section className="section" id="trades" {...reveal}>
          <div className="kicker">Trades</div>
          {state.trades.length === 0 ? (
            <p className="empty">No trades yet.</p>
          ) : (
            <div className="table-wrap glass">
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Side</th>
                    <th>Notional</th>
                    <th>Stop / Target</th>
                    <th>Mode</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {state.trades.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <span className="cell-ticker">
                          <TickerLogo ticker={t.ticker} />
                          {t.ticker}
                        </span>
                      </td>
                      <td className={t.side === "buy" ? "buy" : "sell"}>{t.side}</td>
                      <td>
                        ${t.notional.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td style={{ color: "var(--dim)" }}>
                        {t.stop_loss ? `$${t.stop_loss}` : "—"} /{" "}
                        {t.take_profit ? `$${t.take_profit}` : "—"}
                      </td>
                      <td style={{ color: "var(--dim)" }}>
                        {t.dry_run ? "dry run" : "paper"}
                      </td>
                      <td style={{ color: "var(--dim)" }}>{t.created_at.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.section>

        <motion.section className="section" id="performance" {...reveal}>
          <div className="kicker">Performance</div>
          <div className="equity-panel glass">
            {equityNow !== null && (
              <div className="equity-value">
                ${equityNow.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
            )}
            <EquityCurve points={state.equity} />
          </div>
        </motion.section>
        </div>
      </main>

      <footer>
        <div className="foot-grid">
          <div className="foot-col">
            <h3>Company</h3>
            <a href="#">Home</a>
            <a href="#reasoning">Reasoning</a>
            <a href="#trades">Trades</a>
          </div>
          <div className="foot-col">
            <h3>Work with us</h3>
            <a href="#">Careers</a>
          </div>
          <div className="foot-col">
            <h3>Social</h3>
            <a href="https://x.com" target="_blank" rel="noreferrer">
              X
            </a>
            <a href="https://linkedin.com" target="_blank" rel="noreferrer">
              LinkedIn
            </a>
          </div>
          <div className="foot-col">
            <h3>Contact</h3>
            <span>hello@newstotrade.com</span>
          </div>
        </div>

        <div className="foot-legal">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Use</a>
          <a href="#">Support</a>
        </div>

        <motion.div
          className="foot-wordmark"
          initial={{ y: 80, opacity: 0 }}
          whileInView={{ y: 0, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
        >
          NEWSTOTRADE
        </motion.div>

        <div className="foot-copyright">Copyright © 2026 NEWS-TO-TRADE.</div>
      </footer>
    </>
  );
}
