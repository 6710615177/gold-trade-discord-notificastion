import React, { useState, useEffect, useRef } from "react";
import { Line } from "react-chartjs-2";
import Chart from "chart.js/auto";
import 'chartjs-adapter-date-fns';

export default function ThaiGoldChart({ onPriceUpdate }) {
  const chartRef = useRef();
  const [dataPoints, setDataPoints] = useState([]);

  useEffect(() => {
    const fetchChartData = async () => {
      try {
        // ดึงข้อมูลกราฟทั้งหมดที่ Backend เตรียมไว้ให้
        const res = await fetch(`http://127.0.0.1:8000/api/chart?t=${Date.now()}`);
        const json = await res.json();
        
        if (json && json.status === "success" && json.data.length > 0) {
          // แปลงวันที่ให้อ่านออกใน React
          const formattedData = json.data.map(d => ({
            timestamp: new Date(d.timestamp),
            price: parseFloat(d.price)
          }));
          
          setDataPoints(formattedData);
          
          // ดึงราคาจุดล่าสุดส่งกลับไปให้หน้า Dashboard โชว์ตัวเลข
          if (onPriceUpdate) {
            const latest = json.data[json.data.length - 1];
            onPriceUpdate({ buy: parseFloat(latest.buy), sell: parseFloat(latest.price) });
          }
        }
      } catch (err) { 
        console.error("Error fetching chart data from backend:", err); 
      }
    };

    fetchChartData(); // ดึงครั้งแรกทันที
    
    // ตั้งให้หน้าเว็บไปสะกิด Backend ทุกๆ 15 วินาที เพื่อเช็คว่ามีจุดกราฟใหม่ไหม
    const interval = setInterval(fetchChartData, 15000); 
    return () => clearInterval(interval);
  }, [onPriceUpdate]);

  const chartData = {
    labels: dataPoints.map(d => d.timestamp),
    datasets: [{
      data: dataPoints.map(d => d.price),
      borderColor: "#eab308",
      backgroundColor: "rgba(234,179,8,0.15)",
      fill: true, 
      tension: 0.2
    }]
  };

  const chartOptions = {
    responsive: true, 
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { x: { type: "time", time: { unit: 'minute' } } }
  };

  return (
    <div style={{ height: "300px", width: "100%", padding: "10px", boxSizing: "border-box" }}>
      <Line ref={chartRef} data={chartData} options={chartOptions} />
    </div>
  );
}