import React, { useEffect, useState, useRef } from "react";
import ThaiGoldChart from "./ThaiGoldChart";

function getSignalIcon(signal) {
  if (signal === "BUY") return "▲";
  if (signal === "SELL") return "▼";
  return "●";
}

function formatTime(sec) {
  if (sec < 0) sec = 0;
  let m = Math.floor(sec / 60);
  let s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function getSecondsToNextInterval() {
  const now = new Date();
  const nextMinute = Math.ceil(now.getMinutes() / 15) * 15;
  let target = new Date(now);
  target.setMinutes(nextMinute);
  target.setSeconds(0);
  if (nextMinute === 60) {
    target.setHours(now.getHours() + 1);
    target.setMinutes(0);
  }
  return Math.floor((target - now) / 1000);
}

const HISTORY_KEY = "gold_history_cache";

export default function App() {
  const [date, setDate] = useState("");
  const [timer, setTimer] = useState("5:00");
  const [dashboard, setDashboard] = useState(null);

  const [currentPrice, setCurrentPrice] = useState({ buy: 0, sell: 0 });
  const [news, setNews] = useState([]);

  const [aiData, setAiData] = useState(null);
  const [timeLeft, setTimeLeft] = useState(0);
  const [history, setHistory] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const [isEditingPortfolio, setIsEditingPortfolio] = useState(false);
  const [editCash, setEditCash] = useState("");
  const [editGold, setEditGold] = useState("");

  const lastSavedTime = useRef(null);
  const timerInterval = useRef(null);

  useEffect(() => {
    setDate(new Date().toLocaleDateString("th-TH"));
    loadHistory();
    getDashboard();
    fetchNews();
  }, []);

  async function fetchNews() {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/news");
      if (res.ok) {
        const data = await res.json();
        setNews(data.news || []);
      }
    } catch (e) { console.error("Error fetching news:", e); }
  }

  async function getDashboard() {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/status");
      if (res.ok) setDashboard(await res.json());
    } catch (err) { console.error("Error fetching dashboard", err); }
  }

  function saveHistory(signal, reason) {
    let historyArr = JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    const newTime = new Date().getTime();
    historyArr.push({ signal, reason, time: newTime });
    if (historyArr.length > 10) historyArr = historyArr.slice(-10);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(historyArr));
    setHistory(historyArr.sort((a, b) => b.time - a.time));
  }

  function loadHistory() {
    let historyArr = JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    setHistory(historyArr.sort((a, b) => b.time - a.time));
  }

  async function analyze() {
    if (isAnalyzing) return;
    const currentRound = Math.floor(new Date().getTime() / 60000);
    if (lastSavedTime.current === currentRound) return;
    lastSavedTime.current = currentRound;

    setIsAnalyzing(true);
    try {
      let res = await fetch("/api/analyze", { method: "POST" });
      let data = await res.json();
      if (!data || data.error) {
        setIsAnalyzing(false);
        return;
      }
      setAiData(data);
      setTimeLeft(15);
    } catch (error) {
      console.error(error);
    } finally {
      setIsAnalyzing(false);
    }
  }

  const submitDecision = async (userAction) => {
    if (!aiData) return;
    try {
      await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ai_action: aiData.ai_action,
          ai_reason: aiData.ai_reason,
          ai_amount_thb: aiData.ai_amount_thb,
          user_action: userAction,
        })
      });
      saveHistory(
        userAction === "TIMEOUT" ? aiData.ai_action : userAction,
        userAction === "TIMEOUT" ? "Auto-executed by system" : `User executed ${userAction}`
      );
      setAiData(null);
      setTimeLeft(0);
      await getDashboard();
    } catch (error) { console.error(error); }
  };

  const openEditPortfolio = () => {
    if (dashboard && dashboard.portfolio) {
      setEditCash(dashboard.portfolio.THB_Balance);
      setEditGold(dashboard.portfolio.Gold_Gram);
    }
    setIsEditingPortfolio(true);
  };

  const savePortfolio = async () => {
    try {
      await fetch("/api/portfolio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          THB_Balance: parseFloat(editCash) || 0,
          Gold_Gram: parseFloat(editGold) || 0
        })
      });
      setIsEditingPortfolio(false);
      await getDashboard();
    } catch (error) { console.error(error); }
  };

  useEffect(() => {
    if (dashboard && dashboard.period && !dashboard.period.is_active) {
      setTimer("ตลาดปิด");
      if (timerInterval.current) clearInterval(timerInterval.current);
      return;
    }

    setTimer(formatTime(getSecondsToNextInterval()));
    timerInterval.current = setInterval(() => {
      const timeLeftToNext = getSecondsToNextInterval();
      setTimer(formatTime(timeLeftToNext));

      if (timeLeftToNext % 300 === 0) fetchNews();

      if (timeLeftToNext <= 0) {
        if (dashboard && dashboard.period && dashboard.period.is_active) {
          analyze();
        }
      }
    }, 1000);
    return () => clearInterval(timerInterval.current);
  }, [dashboard]);

  useEffect(() => {
    if (timeLeft > 0 && aiData) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    } else if (timeLeft === 0 && aiData) {
      submitDecision("TIMEOUT");
    }
  }, [timeLeft, aiData]);

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px 30px", fontFamily: "sans-serif", background: "#FAF3E1", color: "#222", minHeight: "100vh", boxSizing: "border-box" }}>

      {/* Header */}
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "flex-start", gap: "15px", marginBottom: "20px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <h1 style={{ color: "#7B542F", margin: 0, lineHeight: "1.5"}}>
            เทรดทองพารวย (AI Agent)
          </h1>
          <p style={{ margin: 0, color: "#555", fontSize: "16px" }}>
            วันที่ {date}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ margin: 0, color: "#555" }}>เวลาที่วิเคราะห์ถัดไป</p>
          <h2 style={{ margin: "5px 0 0 0", fontSize: "32px", color: (dashboard && dashboard.period && !dashboard.period.is_active) ? "#d32f2f" : "#155fa0" }}>
            {timer}
          </h2>
          {dashboard && dashboard.period && (
            <small style={{ color: "#666", display: "block", marginTop: "5px" }}>
              รอบ: {dashboard.period.name}
            </small>
          )}
        </div>
      </div>

      {/* News Bar Section (Bangkok Post) */}
      {news.length > 0 && (
        <div style={{ background: "#1a365d", color: "#fff", padding: "10px 15px", borderRadius: "8px", marginBottom: "20px", display: "flex", alignItems: "center", overflow: "hidden" }}>
          <strong style={{ background: "#d32f2f", padding: "5px 10px", borderRadius: "4px", marginRight: "15px", whiteSpace: "nowrap" }}>📰 BKK Post</strong>
          <div style={{ display: "flex", gap: "20px", overflowX: "auto", whiteSpace: "nowrap", scrollbarWidth: "none" }}>
            {news.map((item, idx) => (
              <a key={idx} href={item.link} target="_blank" rel="noreferrer" style={{ color: "#e2e8f0", textDecoration: "none", borderRight: idx < news.length - 1 ? "1px solid #4a5568" : "none", paddingRight: "20px" }}>
                • {item.title}
              </a>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap" }}>

        {/* Left Column: Chart & History */}
        <div style={{ flex: "2", minWidth: "600px" }}>
          <div style={{ background: "#F5E7C6", borderRadius: "12px", padding: "15px", marginBottom: "20px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
              <h3 style={{ margin: 0, color: "#7B542F" }}>ราคาทองฮั่วเซ่งเฮง (Real-time)</h3>
              <div style={{ display: "flex", gap: "10px" }}>
                <div style={{ background: "#fff", padding: "8px 15px", borderRadius: "8px", border: "1px solid #ddd" }}>
                  <span style={{ color: "#666", fontSize: "14px", marginRight: "8px" }}>รับซื้อ:</span>
                  <strong style={{ color: "#00c853", fontSize: "18px" }}>{currentPrice.buy ? currentPrice.buy.toLocaleString() : "..."}</strong>
                </div>
                <div style={{ background: "#fff", padding: "8px 15px", borderRadius: "8px", border: "1px solid #ddd" }}>
                  <span style={{ color: "#666", fontSize: "14px", marginRight: "8px" }}>ขายออก:</span>
                  <strong style={{ color: "#d32f2f", fontSize: "18px" }}>{currentPrice.sell ? currentPrice.sell.toLocaleString() : "..."}</strong>
                </div>
              </div>
            </div>
            <ThaiGoldChart onPriceUpdate={setCurrentPrice} />
          </div>

          <div>
            <h2 style={{ color: "#7B542F", marginBottom: "15px" }}>ประวัติการทำรายการ (Local)</h2>
            <div style={{ maxHeight: "300px", overflowY: "auto", paddingRight: "5px" }}>
              {history.length === 0 ? <p style={{ color: "#888" }}>ยังไม่มีประวัติการทำรายการ</p> : null}
              {history.map((h, i) => {
                const dateObj = new Date(h.time);
                const color = h.signal === "BUY" ? "#00c853" : h.signal === "SELL" ? "#d32f2f" : "#777";
                return (
                  <div key={i} style={{ background: "rgba(255,255,255,0.6)", padding: "15px", marginBottom: "10px", borderRadius: "8px", borderLeft: `5px solid ${color}` }}>
                    <strong style={{ color, fontSize: "16px" }}>{getSignalIcon(h.signal)} {h.signal}</strong><br />
                    <span style={{ fontSize: "14px", color: "#555", display: "inline-block", marginTop: "5px" }}>{h.reason}</span><br />
                    <small style={{ color: "#888", display: "inline-block", marginTop: "5px" }}>เวลา {dateObj.toLocaleTimeString("th-TH")}</small>
                  </div>
                );
              })}
            </div>
            {dashboard?.performance && (
              <div style={{ marginTop: "30px" }}>
                <h2 style={{ color: "#7B542F", marginBottom: "15px" }}>Performance</h2>

                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, 1fr)",
                  gap: "14px"
                }}>
                  {[
                    ["Total Closed Trade", dashboard.performance.total_closed_trade, ""],
                    ["Win Rate", dashboard.performance.win_rate, "%"],
                    ["Total Profit", dashboard.performance.total_profit, " THB"],
                    ["Unrealized P/L", dashboard.performance.unrealized_pl, " THB"],

                    ["Average Win", dashboard.performance.avg_win, " THB"],
                    ["Average Loss", dashboard.performance.avg_loss, " THB"],
                    ["Expectancy", dashboard.performance.expectancy, " THB"],
                    ["Best Annualized", dashboard.performance.best_trade, "%"],

                    ["Worst Annualized", dashboard.performance.worst_trade, "%"],
                    ["Median Annualized", dashboard.performance.median_trade, "%"],
                    ["Top 10%", dashboard.performance.top10_trade, "%"],
                    ["Bottom 10%", dashboard.performance.bottom10_trade, "%"],

                    ["XIRR", dashboard.performance.xirr, "%"],
                    ["Avg Capital/Year", dashboard.performance.avg_capital_year, " THB/Year"],
                    ["Sharpe Ratio", dashboard.performance.sharpe_ratio, ""]
                  ].map(([label, value, suffix], i) => (
                    <div key={i} style={{
                      background: "#d5d9df",
                      borderRadius: "18px",
                      padding: "14px 10px",
                      textAlign: "center",
                      boxShadow: "0 8px 20px rgba(173, 170, 125, 0)",
                      minHeight: "70px"
                    }}>
                      <div style={{
                        fontSize: "11px",
                        color: "#9ca3af",
                        fontWeight: "bold",
                        marginBottom: "6px"
                      }}>
                        {label}
                      </div>

                      <div style={{
                        fontSize: "16px",
                        fontWeight: "bold",
                        color: label.includes("Loss") || label.includes("Worst") || label.includes("Bottom")
                          ? "#ef4444"
                          : label.includes("Profit") || label.includes("Win") || label.includes("XIRR")
                            ? "#f97316"
                            : label.includes("Top 10%") ? "#38b66c"
                              : "#7c3aed"
                      }}>
                        {typeof value === "number" ? value.toLocaleString() : value}
                        {suffix}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Portfolio & AI */}
        <div style={{ flex: "1", minWidth: "300px", display: "flex", flexDirection: "column", gap: "20px" }}>

          {dashboard && (
            <div style={{ background: "#fff", borderRadius: "12px", padding: "20px", boxShadow: "0 4px 6px rgba(0,0,0,0.05)", position: "relative" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                <h3 style={{ margin: 0, color: "#333" }}>Portfolio</h3>
                <button onClick={openEditPortfolio} style={{ background: "#f57c00", color: "#fff", border: "none", padding: "5px 12px", borderRadius: "5px", cursor: "pointer", fontWeight: "bold" }}>
                  ⚙️ แก้ไข
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ background: "#f8f9fa", padding: "15px", borderRadius: "8px", display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#666" }}>เงินสด (THB)</span>
                  <strong style={{ fontSize: "18px" }}>{dashboard.portfolio.THB_Balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                </div>
                <div style={{ background: "#f8f9fa", padding: "15px", borderRadius: "8px", display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#666" }}>ทองคำ (Grams)</span>
                  <strong style={{ fontSize: "18px" }}>{dashboard.portfolio.Gold_Gram.toFixed(4)}</strong>
                </div>
                <div style={{ background: "#e3f2fd", padding: "15px", borderRadius: "8px", display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#155fa0", fontWeight: "bold" }}>มูลค่ารวม (NAV)</span>
                  <strong style={{ fontSize: "20px", color: "#155fa0" }}>{dashboard.net_asset_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                </div>
              </div>
            </div>
          )}

          {isEditingPortfolio && (
            <div style={{ background: "#fff", padding: "20px", borderRadius: "12px", border: "2px solid #f57c00" }}>
              <h4 style={{ margin: "0 0 10px 0" }}>ตั้งค่า Portfolio</h4>
              <label style={{ display: "block", marginBottom: "5px", fontSize: "14px" }}>Cash Balance (THB):</label>
              <input type="number" value={editCash} onChange={(e) => setEditCash(e.target.value)} style={{ width: "100%", padding: "8px", marginBottom: "15px", boxSizing: "border-box" }} />
              <label style={{ display: "block", marginBottom: "5px", fontSize: "14px" }}>Gold Holdings (Grams):</label>
              <input type="number" value={editGold} onChange={(e) => setEditGold(e.target.value)} style={{ width: "100%", padding: "8px", marginBottom: "15px", boxSizing: "border-box" }} />
              <div style={{ display: "flex", gap: "10px" }}>
                <button onClick={savePortfolio} style={{ flex: 1, padding: "8px", background: "#f57c00", color: "#fff", border: "none", borderRadius: "5px", cursor: "pointer" }}>บันทึก</button>
                <button onClick={() => setIsEditingPortfolio(false)} style={{ flex: 1, padding: "8px", background: "#ddd", border: "none", borderRadius: "5px", cursor: "pointer" }}>ยกเลิก</button>
              </div>
            </div>
          )}

          {aiData && (
            <div style={{ background: "#fff", padding: "20px", borderRadius: "12px", border: "3px solid #d32f2f", boxShadow: "0 4px 12px rgba(211, 47, 47, 0.2)" }}>
              <h2 style={{ color: "#d32f2f", margin: "0 0 10px 0", textAlign: "center" }}>AI: {aiData.ai_action}</h2>
              <p style={{ textAlign: "center", margin: "0 0 15px 0" }}><strong>ขนาดไม้:</strong> {aiData.ai_amount_thb}</p>
              <div style={{ background: "#f9f9f9", padding: "15px", borderRadius: "8px", fontSize: "14px", lineHeight: "1.6", maxHeight: "300px", overflowY: "auto" }} dangerouslySetInnerHTML={{ __html: aiData.ai_reason }}></div>

              <p style={{ color: "#d32f2f", fontWeight: "bold", textAlign: "center", fontSize: "18px", marginTop: "20px" }}>
                ดำเนินการใน {timeLeft} วินาที
              </p>

              <div style={{ display: "flex", gap: "10px", marginTop: "15px" }}>
                <button onClick={() => submitDecision("BUY")} style={{ flex: 1, padding: "12px", background: "#00c853", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "bold", cursor: "pointer" }}>BUY</button>
                <button onClick={() => submitDecision("SELL")} style={{ flex: 1, padding: "12px", background: "#d32f2f", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "bold", cursor: "pointer" }}>SELL</button>
                <button onClick={() => submitDecision("HOLD")} style={{ flex: 1, padding: "12px", background: "#777", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "bold", cursor: "pointer" }}>HOLD</button>
              </div>
            </div>
          )}

          {!aiData && dashboard && dashboard.period && dashboard.period.is_active && (
            <button onClick={analyze} disabled={isAnalyzing} style={{ padding: "15px", background: "#155fa0", color: "#fff", border: "none", borderRadius: "8px", cursor: isAnalyzing ? "not-allowed" : "pointer", opacity: isAnalyzing ? 0.7 : 1, fontWeight: "bold", fontSize: "16px", width: "100%" }}>
              {isAnalyzing ? "กำลังวิเคราะห์ข้อมูล..." : "วิเคราะห์ AI ทันที"}
            </button>
          )}

        </div>
      </div>
    </div>
  );
}