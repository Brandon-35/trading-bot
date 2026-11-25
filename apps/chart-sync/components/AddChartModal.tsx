import React, { useState } from 'react';
import { X, Plus, ArrowRight } from 'lucide-react';

interface AddChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (symbol: string, interval: string) => void;
  theme?: 'Light' | 'Dark';
}

const AddChartModal: React.FC<AddChartModalProps> = ({ isOpen, onClose, onAdd, theme = 'Light' }) => {
  const [coin, setCoin] = useState('BNB');
  const [pair, setPair] = useState('USDT');
  const [interval, setInterval] = useState('60');

  if (!isOpen) return null;
  
  const isDark = theme === 'Dark';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!coin || !pair) return;
    
    // Construct symbol assuming Binance for simplicity, but user can edit later
    const fullSymbol = `BINANCE:${coin.toUpperCase()}${pair.toUpperCase()}`;
    onAdd(fullSymbol, interval);
    onClose();
  };

  const modalBg = isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-100';
  const textPrimary = isDark ? 'text-white' : 'text-slate-800';
  const textLabel = isDark ? 'text-slate-400' : 'text-slate-600';
  const inputClass = isDark 
    ? 'bg-slate-800 border-slate-700 text-white focus:ring-brand-500/50 placeholder-slate-500' 
    : 'bg-white border-slate-200 text-slate-800 focus:ring-brand-500/50 placeholder-slate-300';
  const previewBox = isDark ? 'bg-slate-800 border-slate-700 text-slate-400' : 'bg-slate-50 border-slate-100 text-slate-500';
  const previewText = isDark ? 'bg-slate-900 border-slate-700 text-slate-300' : 'bg-white border-slate-200 text-slate-600';

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className={`${modalBg} rounded-2xl shadow-2xl border p-6 max-w-sm w-full animate-in zoom-in-95 duration-200`}>
        <div className="flex justify-between items-center mb-4">
          <h3 className={`text-lg font-bold ${textPrimary}`}>Thêm Biểu Đồ Mới</h3>
          <button onClick={onClose} className={`text-slate-400 hover:${textPrimary}`}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-2">
            <div className="flex-1">
                <label className={`block text-sm font-medium mb-1 ${textLabel}`}>Đồng (Coin)</label>
                <input
                type="text"
                value={coin}
                onChange={(e) => setCoin(e.target.value.toUpperCase())}
                className={`w-full px-3 py-2 border rounded-xl focus:outline-none focus:ring-2 focus:border-brand-500 text-sm font-bold ${inputClass}`}
                placeholder="BTC"
                autoFocus
                />
            </div>
            <div className={`flex items-center pt-6 ${isDark ? 'text-slate-600' : 'text-slate-300'}`}>
                <ArrowRight className="w-4 h-4" />
            </div>
            <div className="w-24">
                <label className={`block text-sm font-medium mb-1 ${textLabel}`}>Cặp (Pair)</label>
                <input
                type="text"
                value={pair}
                onChange={(e) => setPair(e.target.value.toUpperCase())}
                className={`w-full px-3 py-2 border rounded-xl focus:outline-none focus:ring-2 focus:border-brand-500 text-sm font-bold ${inputClass}`}
                placeholder="USDT"
                />
            </div>
          </div>

          <div className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${previewBox}`}>
            <div className={`font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Xem trước:</div>
            <div className={`font-mono px-2 py-0.5 rounded border ${previewText}`}>
                BINANCE:{coin}{pair}
            </div>
          </div>

          <div>
            <label className={`block text-sm font-medium mb-1 ${textLabel}`}>Khung thời gian</label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className={`w-full px-3 py-2 border rounded-xl focus:outline-none focus:ring-2 focus:border-brand-500 text-sm font-medium ${inputClass}`}
            >
              <option value="1">1 Phút</option>
              <option value="3">3 Phút</option>
              <option value="5">5 Phút</option>
              <option value="15">15 Phút</option>
              <option value="30">30 Phút</option>
              <option value="60">1 Giờ</option>
              <option value="120">2 Giờ</option>
              <option value="240">4 Giờ</option>
              <option value="720">12 Giờ</option>
              <option value="D">1 Ngày</option>
              <option value="W">1 Tuần</option>
              <option value="M">1 Tháng</option>
            </select>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white font-medium rounded-xl shadow-lg shadow-brand-500/30 transition-all active:scale-95"
            >
              <Plus className="w-4 h-4" />
              Thêm Biểu Đồ
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddChartModal;