import React, { useState, useEffect } from "react";
import { Line } from "react-chartjs-2";
import Chart from "chart.js/auto";
import "chartjs-adapter-date-fns";

const API = import.meta.env.VITE_API_BASE_URL;

export default function ThaiGoldChart({ onPriceUpdate }) {
  const [dataPoints, setDataPoints] = useState([]);

  useEffect(() => {
    const fetchChartData = async () => {
      try {
        const res = await fetch(`${API}/api/chart?t=${Date.now()}`);
        const json = await res.json();

        if (json && json.status === "success" && Array.isArray(json.data)) {
          const today = new Date().toDateString();

          const cleaned = json.data
            .map((d) => ({
              x: new Date(d.timestamp),
              y: Number(d.price),
              buy: d.buy,
              sell: d.price,
            }))
            .filter((d) => !isNaN(d.x.getTime()) && !isNaN(d.y));

          const filtered = cleaned.filter(
            (d) => d.x.toDateString() === today
          );

          const finalData = filtered.length >= 2 ? filtered : cleaned.slice(-10);

          console.log("cleaned:", cleaned.length);
          console.log("filtered today:", filtered.length);
          console.log("finalData:", finalData);

          setDataPoints(finalData);

          if (onPriceUpdate && cleaned.length > 0) {
            const latest = cleaned[cleaned.length - 1];
            onPriceUpdate({ buy: latest.buy, sell: latest.sell });
          }
        }
      } catch (err) {
        console.error(err);
      }
    };

    fetchChartData();
    const interval = setInterval(fetchChartData, 20000);
    return () => clearInterval(interval);
  }, [onPriceUpdate]);

  return (
    <div style={{ height: "300px" }}>
      <Line
        data={{
          datasets: [
            {
              label: "Gold Price",
              data: dataPoints,
              borderColor: "#eab308",
              backgroundColor: "rgba(234,179,8,0.1)",
              fill: true,
              tension: 0.3,
            },
          ],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              type: "time",
              time: {
                unit: "hour",
                displayFormats: { hour: "HH:mm" },
              },
            },
          },
          plugins: { legend: { display: false } },
        }}
      />
    </div>
  );
}