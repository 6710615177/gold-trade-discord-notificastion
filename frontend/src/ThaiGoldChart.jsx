import React, { useState, useEffect } from "react";
import { Line } from "react-chartjs-2";
import Chart from "chart.js/auto";
import 'chartjs-adapter-date-fns';

const API = import.meta.env.VITE_API_BASE_URL;

export default function ThaiGoldChart({ onPriceUpdate }) {
  const [dataPoints, setDataPoints] = useState([]);

  useEffect(() => {
    const fetchChartData = async () => {
      try {
        const res = await fetch(`${API}/api/chart?t=${Date.now()}`);
        const json = await res.json();

        if (json && json.status === "success") {
          // 🎯 กรองเอาเฉพาะข้อมูลของ "วันนี้"
          const today = new Date().toDateString();
          const filtered = json.data.filter(d => new Date(d.timestamp).toDateString() === today);

          // ถ้าเป็นเช้าวันใหม่ยังไม่มีข้อมูล ให้ดึง 10 อันล่าสุดแทน
          const finalData = filtered.length > 5 ? filtered : json.data.slice(-10);

          setDataPoints(finalData.map(d => ({
            x: new Date(d.timestamp),
            y: parseFloat(d.price)
          })));

          if (onPriceUpdate && json.data.length > 0) {
            const latest = json.data[json.data.length - 1];
            onPriceUpdate({ buy: latest.buy, sell: latest.price });
          }
        }
      } catch (err) { console.error(err); }
    };

    fetchChartData();
    const interval = setInterval(fetchChartData, 20000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ height: "300px" }}>
      <Line
        data={{
          datasets: [{
            label: 'Gold Price',
            data: dataPoints,
            borderColor: "#eab308",
            backgroundColor: "rgba(234,179,8,0.1)",
            fill: true,
            tension: 0.3
          }]
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { type: 'time', time: { unit: 'hour', displayFormats: { hour: 'HH:mm' } } }
          },
          plugins: { legend: { display: false } }
        }}
      />
    </div>
  );
}