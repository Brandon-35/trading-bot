import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend
} from 'recharts';
import { Transaction } from '../types';

interface ChartsProps {
  data: Transaction[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-lg">
        <p className="text-slate-500 text-xs font-semibold mb-2 uppercase tracking-wide">{label}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-3 text-sm py-0.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-slate-600 font-medium capitalize">{entry.name}:</span>
            <span className="text-slate-900 font-mono font-bold">
              {entry.value.toLocaleString('vi-VN')}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export const PriceChart: React.FC<ChartsProps> = ({ data }) => {
  const chartData = data.map(tx => ({
    date: tx.date.split(' ')[0].slice(5), // MM-DD
    price: tx.price_vnd,
    type: tx.type
  }));

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm h-[400px]">
      <div className="mb-6">
        <h3 className="text-slate-800 font-bold text-lg">Xu hướng Giá (VND/USDT)</h3>
        <p className="text-sm text-slate-500">Biến động tỷ giá mua bán theo thời gian</p>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis 
            dataKey="date" 
            stroke="#94a3b8" 
            fontSize={12} 
            tickMargin={10}
            axisLine={false}
            tickLine={false}
          />
          <YAxis 
            stroke="#94a3b8" 
            fontSize={12} 
            domain={['auto', 'auto']}
            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#cbd5e1', strokeWidth: 1, strokeDasharray: '4 4' }} />
          <Line 
            type="monotone" 
            dataKey="price" 
            stroke="#3b82f6" 
            strokeWidth={3}
            dot={{ r: 4, fill: '#fff', stroke: '#3b82f6', strokeWidth: 2 }}
            activeDot={{ r: 6, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }}
            name="Giá (VND)"
            animationDuration={1500}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export const VolumeChart: React.FC<ChartsProps> = ({ data }) => {
  const volumeByDate = data.reduce((acc, curr) => {
    const date = curr.date.split(' ')[0].slice(5); // MM-DD
    if (!acc[date]) acc[date] = { date, buy: 0, sell: 0 };
    
    if (curr.type === 'buy') acc[date].buy += curr.usdt_amount;
    else acc[date].sell += curr.usdt_amount;
    
    return acc;
  }, {} as Record<string, { date: string, buy: number, sell: number }>);

  const chartData = Object.values(volumeByDate);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm h-[400px]">
      <div className="mb-6">
        <h3 className="text-slate-800 font-bold text-lg">Khối lượng Giao dịch (USDT)</h3>
        <p className="text-sm text-slate-500">Tổng khối lượng mua và bán theo ngày</p>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis 
            dataKey="date" 
            stroke="#94a3b8" 
            fontSize={12}
            tickMargin={10} 
            axisLine={false}
            tickLine={false}
          />
          <YAxis 
            stroke="#94a3b8" 
            fontSize={12} 
            axisLine={false}
            tickLine={false}
          />
          <Tooltip cursor={{fill: '#f1f5f9'}} content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }} iconType="circle" />
          <Bar dataKey="buy" name="Mua (Buy)" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={40} animationDuration={1500} />
          <Bar dataKey="sell" name="Bán (Sell)" fill="#f43f5e" radius={[4, 4, 0, 0]} maxBarSize={40} animationDuration={1500} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};