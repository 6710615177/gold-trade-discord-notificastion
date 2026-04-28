raF
farxaway
Invisible

sxjsbdjsbsjs — 16:23
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

// ใช้แสดงเวลาคร่าวๆ ให้ User รู้ว่าระบบหลังบ้านจะทำงานเมื่อไหร่
function getSecondsToNextInterval() {
  const now = new Date();
  const currentMin = now.getMinutes();
  const nextMin = currentMin + (2 - (currentMin % 2));
  let target = new Date(now);
  target.setMinutes(nextMin, 0, 0);
  return Math.floor((target.getTime() - now.getTime()) / 1000);
}

export default function App() {
  const [date, setDate] = useState("");
  const [timer, setTimer] = useState("2:00");
  const [dashboard, setDashboard] = useState(null);

  const [currentPrice, setCurrentPrice] = useState({ buy: 0, sell: 0 });
  const [news, setNews] = useState([]);

  const [aiData, setAiData] = useState(null);
  const [timeLeft, setTimeLeft] = useState(0);
  const [history, setHistory] = useState([]);
  const [showAllHistory, setShowAllHistory] = useState(false);

  const [isEditingPortfolio, setIsEditingPortfolio] = useState(false);
  const [editCash, setEditCash] = useState("");
  const [editGold, setEditGold] = useState("");

  const timerInterval = useRef(null);

  useEffect(() => {
    setDate(new Date().toLocaleDateString("th-TH"));
    loadHistory();
    getDashboard();
    fetchNews();

    // 🎯 เพิ่มระบบ Auto-Sync ดึงข้อมูล Performance และประวัติใหม่ทุกๆ 10 วินาที
    const autoSyncInterval = setInterval(() => {
      getDashboard();
      loadHistory();
    }, 10000);

    return () => clearInterval(autoSyncInterval);
  }, []);

  async function fetchNews() {
    try {
      const res = await fetch("/api/news");
      if (res.ok) {
        const data = await res.json();
        setNews(data.news || []);
      }
    } catch (e) { console.error("Error fetching news:", e); }
  }

  async function getDashboard() {
    try {
      // 🎯 ใส่ Cache Buster ?t=Date.now() เพื่อบังคับให้ดึงข้อมูลใหม่เสมอ ไม่จำของเก่า
      const res = await fetch(`/api/status?t=${Date.now()}`);
      if (res.ok) setDashboard(await res.json());
    } catch (err) { console.error("Error fetching dashboard", err); }
  }

  async function loadHistory() {
    try {
      // 🎯 ใส่ Cache Buster เช่นเดียวกัน
      const res = await fetch(`/api/history?t=${Date.now()}`);
      const data = await res.json();
      if (data.status === "success") {
        setHistory(data.history);
      }
    } catch (e) {
      console.error("Error loading history from server:", e);
    }
  }

  // 🎯 Polling: ถาม Backend ทุกๆ 5 วินาทีว่ามี AI วิเคราะห์ทิ้งไว้ไหม
  useEffect(() => {
    const checkPendingSignal = async () => {
      // ถ้ากำลังโชว์กล่องตัดสินใจอยู่ หรือตลาดปิด ไม่ต้องดึงกวน
      if (aiData || (dashboard && dashboard.period && !dashboard.period.is_active)) return;
      try {
        const res = await fetch(`/api/pending-signal?t=${Date.now()}`);
        const data = await res.json();
        if (data && data.signal) {
... (275 lines left)

App.jsx
21 KB
﻿
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

// ใช้แสดงเวลาคร่าวๆ ให้ User รู้ว่าระบบหลังบ้านจะทำงานเมื่อไหร่
function getSecondsToNextInterval() {
  const now = new Date();
  const currentMin = now.getMinutes();
  const nextMin = currentMin + (2 - (currentMin % 2));
  let target = new Date(now);
  target.setMinutes(nextMin, 0, 0);
  return Math.floor((target.getTime() - now.getTime()) / 1000);
}

export default function App() {
  const [date, setDate] = useState("");
  const [timer, setTimer] = useState("2:00");
  const [dashboard, setDashboard] = useState(null);

  const [currentPrice, setCurrentPrice] = useState({ buy: 0, sell: 0 });
  const [news, setNews] = useState([]);

  const [aiData, setAiData] = useState(null);
  const [timeLeft, setTimeLeft] = useState(0);
  const [history, setHistory] = useState([]);
  const [showAllHistory, setShowAllHistory] = useState(false);

  const [isEditingPortfolio, setIsEditingPortfolio] = useState(false);
  const [editCash, setEditCash] = useState("");
  const [editGold, setEditGold] = useState("");

  const timerInterval = useRef(null);

  useEffect(() => {
    setDate(new Date().toLocaleDateString("th-TH"));
    loadHistory();
    getDashboard();
    fetchNews();

    // 🎯 เพิ่มระบบ Auto-Sync ดึงข้อมูล Performance และประวัติใหม่ทุกๆ 10 วินาที
    const autoSyncInterval = setInterval(() => {
      getDashboard();
      loadHistory();
    }, 10000);

    return () => clearInterval(autoSyncInterval);
  }, []);

  async function fetchNews() {
    try {
      const res = await fetch("/api/news");
      if (res.ok) {
        const data = await res.json();
        setNews(data.news || []);
      }
    } catch (e) { console.error("Error fetching news:", e); }
  }

  async function getDashboard() {
    try {
      // 🎯 ใส่ Cache Buster ?t=Date.now() เพื่อบังคับให้ดึงข้อมูลใหม่เสมอ ไม่จำของเก่า
      const res = await fetch(`/api/status?t=${Date.now()}`);
      if (res.ok) setDashboard(await res.json());
    } catch (err) { console.error("Error fetching dashboard", err); }
  }

  async function loadHistory() {
    try {
      // 🎯 ใส่ Cache Buster เช่นเดียวกัน
      const res = await fetch(`/api/history?t=${Date.now()}`);
      const data = await res.json();
      if (data.status === "success") {
        setHistory(data.history);
      }
    } catch (e) {
      console.error("Error loading history from server:", e);
    }
  }

  // 🎯 Polling: ถาม Backend ทุกๆ 5 วินาทีว่ามี AI วิเคราะห์ทิ้งไว้ไหม
  useEffect(() => {
    const checkPendingSignal = async () => {
      // ถ้ากำลังโชว์กล่องตัดสินใจอยู่ หรือตลาดปิด ไม่ต้องดึงกวน
      if (aiData || (dashboard && dashboard.period && !dashboard.period.is_active)) return;
      try {
        const res = await fetch(`/api/pending-signal?t=${Date.now()}`);
        const data = await res.json();
        if (data && data.signal) {
          setAiData(data.signal);
          setTimeLeft(15); // เริ่มนับถอยหลัง 15 วิ ทันทีที่รับสัญญาณ
        }
      } catch (error) { console.error("Polling error:", error); }
    };

    const pollInterval = setInterval(checkPendingSignal, 5000);
    return () => clearInterval(pollInterval);
  }, [aiData, dashboard]);

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

      setAiData(null);
      setTimeLeft(0);

      // 🎯 ดึงข้อมูลใหม่ทั้งหมดหลังจากบันทึกสำเร็จ (ตอนนี้จะไม่ติด Cache แล้ว)
      await getDashboard();
      await loadHistory();
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

  // แสดงเวลาถอยหลัง 2 นาทีเพื่อความสวยงาม
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
      if (timeLeftToNext === 60) fetchNews();
    }, 1000);
    return () => clearInterval(timerInterval.current);
  }, [dashboard]);

  // ระบบนับถอยหลัง 15 วินาทีของกล่องตัดสินใจ
  useEffect(() => {
    if (timeLeft > 0 && aiData) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    } else if (timeLeft === 0 && aiData) {
      submitDecision("TIMEOUT");
    }
  }, [timeLeft, aiData]);

  const visibleHistory = showAllHistory ? history : history.slice(0, 5);

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px 15px", fontFamily: "sans-serif", background: "#FAF3E1", color: "#222", minHeight: "100vh", boxSizing: "border-box" }}>

      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "flex-start", gap: "15px", marginBottom: "20px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <h1 style={{ color: "#7B542F", margin: 0, lineHeight: "1.5", fontSize: "clamp(24px, 4vw, 36px)" }}>
            เทรดทองพารวย
          </h1>
          <p style={{ margin: 0, color: "#555", fontSize: "16px" }}>
            วันที่ {date}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ margin: 0, color: "#555" }}>เวลาที่ระบบจะตรวจสอบรอบถัดไป</p>
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

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", flexDirection: "row" }}>
        <div style={{ flex: "2 1 60%", minWidth: "300px" }}>

          <div style={{ background: "#F5E7C6", borderRadius: "12px", padding: "15px", marginBottom: "20px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", marginBottom: "15px", gap: "10px" }}>
              <h3 style={{ margin: 0, color: "#7B542F", fontSize: "1.1rem" }}>ราคาทองฮั่วเซ่งเฮง (Real-time)</h3>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <div style={{ background: "#fff", padding: "8px 15px", borderRadius: "8px", border: "1px solid #ddd", flex: "1" }}>
                  <span style={{ color: "#666", fontSize: "14px", marginRight: "8px" }}>รับซื้อ:</span>
                  <strong style={{ color: "#00c853", fontSize: "18px" }}>{currentPrice.buy ? currentPrice.buy.toLocaleString() : "..."}</strong>
                </div>
                <div style={{ background: "#fff", padding: "8px 15px", borderRadius: "8px", border: "1px solid #ddd", flex: "1" }}>
                  <span style={{ color: "#666", fontSize: "14px", marginRight: "8px" }}>ขายออก:</span>
                  <strong style={{ color: "#d32f2f", fontSize: "18px" }}>{currentPrice.sell ? currentPrice.sell.toLocaleString() : "..."}</strong>
                </div>
              </div>
            </div>
            <ThaiGoldChart onPriceUpdate={setCurrentPrice} />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
              <h2 style={{ color: "#7B542F", margin: 0 }}>ประวัติการทำรายการ (Local)</h2>
              {history.length > 5 && (
                <button
                  onClick={() => setShowAllHistory(!showAllHistory)}
                  style={{ background: "transparent", color: "#155fa0", border: "1px solid #155fa0", padding: "5px 12px", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}
                >
                  {showAllHistory ? "ซ่อนรายการ" : `ดูทั้งหมด (${history.length})`}
                </button>
              )}
            </div>

            <div style={{ maxHeight: showAllHistory ? "600px" : "auto", overflowY: "auto", paddingRight: "5px" }}>
              {history.length === 0 ? <p style={{ color: "#888" }}>ยังไม่มีประวัติการทำรายการ</p> : null}
              {visibleHistory.map((h, i) => {
                const dateObj = new Date(h.time);
                const color = h.signal === "BUY" ? "#00c853" : h.signal === "SELL" ? "#d32f2f" : "#777";
                return (
                  <div key={i} style={{ background: "rgba(255,255,255,0.6)", padding: "15px", marginBottom: "10px", borderRadius: "8px", borderLeft: `5px solid ${color}` }}>
                    <strong style={{ color, fontSize: "16px" }}>{getSignalIcon(h.signal)} {h.signal}</strong><br />
                    <span style={{ fontSize: "14px", color: "#555", display: "inline-block", marginTop: "5px", lineHeight: "1.5" }} dangerouslySetInnerHTML={{ __html: h.reason }}></span><br />
                    <small style={{ color: "#888", display: "inline-block", marginTop: "8px" }}>เวลา {dateObj.toLocaleTimeString("th-TH")}</small>
                  </div>
                );
              })}
            </div>

            {dashboard?.performance && (
              <div style={{ marginTop: "30px" }}>
                <h2 style={{ color: "#7B542F", marginBottom: "15px" }}>Performance</h2>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "14px" }}>
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
                    ["Avg Capital/Year", dashboard.performance.avg_capital_year, " /Y"],
                    ["Sharpe Ratio", dashboard.performance.sharpe_ratio, ""]
                  ].map(([label, value, suffix], i) => (
                    <div key={i} style={{ background: "#d5d9df", borderRadius: "18px", padding: "14px 10px", textAlign: "center", minHeight: "70px" }}>
                      <div style={{ fontSize: "11px", color: "#6b7280", fontWeight: "bold", marginBottom: "6px" }}>{label}</div>
                      <div style={{ fontSize: "15px", fontWeight: "bold", color: label.includes("Loss") || label.includes("Worst") || label.includes("Bottom") ? "#ef4444" : label.includes("Profit") || label.includes("Win") || label.includes("XIRR") ? "#f97316" : label.includes("Top 10%") ? "#38b66c" : "#7c3aed" }}>
                        {typeof value === "number" ? value.toLocaleString() : value}{suffix}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div style={{ flex: "1 1 30%", minWidth: "300px", display: "flex", flexDirection: "column", gap: "20px" }}>

          {dashboard && (
            <div style={{ background: "#fff", borderRadius: "12px", padding: "20px", boxShadow: "0 4px 6px rgba(0,0,0,0.05)" }}>
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
              <h2 style={{ color: "#d32f2f", margin: "0 0 10px 0", textAlign: "center" }}>AI แนะนำ: {aiData.ai_action}</h2>
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
            <div style={{ padding: "15px", background: "transparent", color: "#888", border: "2px dashed #ccc", borderRadius: "8px", textAlign: "center", fontSize: "14px" }}>
              ระบบกำลังรอสัญญาณจาก AI...
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
