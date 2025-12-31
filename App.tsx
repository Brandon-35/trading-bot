import React, { useMemo, useState } from 'react';
import { RAW_DATA } from './constants';
import { PortfolioSummary, Transaction } from './types';
import { MetricsCard } from './components/MetricsCard';
import { TransactionTable } from './components/TransactionTable';
import { PriceChart, VolumeChart } from './components/Charts';
import { LayoutDashboard, Download, Wallet, TrendingUp, TrendingDown } from 'lucide-react';

const App: React.FC = () => {
  const transactions = RAW_DATA.transactions;
  const [manualBalance, setManualBalance] = useState<string>('');

  // Calculate summary statistics
  const summary: PortfolioSummary = useMemo(() => {
    const stats = transactions.reduce(
      (acc, tx) => {
        if (tx.type === 'buy') {
          acc.totalBuyVnd += tx.vnd_amount;
          acc.totalBuyUsdt += tx.usdt_amount;
        } else {
          acc.totalSellVnd += tx.vnd_amount;
          acc.totalSellUsdt += tx.usdt_amount;
        }
        return acc;
      },
      {
        totalBuyVnd: 0,
        totalBuyUsdt: 0,
        totalSellVnd: 0,
        totalSellUsdt: 0,
        netHoldingUsdt: 0,
        netCostVnd: 0,
        avgCost: 0,
      }
    );

    stats.netHoldingUsdt = stats.totalBuyUsdt - stats.totalSellUsdt;
    stats.netCostVnd = stats.totalBuyVnd - stats.totalSellVnd;
    stats.avgCost = stats.netHoldingUsdt > 0 ? stats.netCostVnd / stats.netHoldingUsdt : 0;

    return stats;
  }, [transactions]);

  const formatVND = (val: number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
  const formatUSDT = (val: number) => new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val) + ' USDT';

  // Calculate Profit/Loss if manual balance is entered
  const pnlUsdt = manualBalance ? parseFloat(manualBalance) - summary.netHoldingUsdt : null;
  const pnlStatus = pnlUsdt !== null ? (pnlUsdt >= 0 ? 'profit' : 'loss') : 'neutral';

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-indigo-100 selection:text-indigo-900 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-2.5 bg-indigo-600 rounded-xl shadow-lg shadow-indigo-200">
              <LayoutDashboard className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800 leading-none">Phân Tích P2P</h1>
              <p className="text-xs font-medium text-slate-500 mt-1.5 uppercase tracking-wide">T10/2025 - T12/2025</p>
            </div>
          </div>
          <button 
            className="flex items-center gap-2 px-5 py-2.5 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-all shadow-sm hover:shadow-md active:scale-95"
            onClick={() => alert("Chức năng xuất báo cáo CSV mô phỏng")}
          >
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Xuất Báo Cáo</span>
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
        
        {/* PnL Calculation Section (New) */}
        <section className="bg-white rounded-3xl p-1 shadow-sm border border-slate-100">
            <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-[20px] p-8 text-white relative overflow-hidden">
                <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-white opacity-10 rounded-full blur-3xl"></div>
                <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-64 h-64 bg-black opacity-10 rounded-full blur-3xl"></div>
                
                <div className="relative z-10 flex flex-col md:flex-row gap-8 items-center justify-between">
                    <div className="w-full md:w-auto space-y-4">
                        <div className="flex items-center gap-3 mb-2">
                             <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
                                <Wallet className="w-5 h-5 text-white" />
                             </div>
                             <h2 className="text-lg font-semibold text-indigo-50">Tính Lãi / Lỗ Thực Tế</h2>
                        </div>
                        <div className="flex flex-col gap-2">
                            <label className="text-sm font-medium text-indigo-100 ml-1">Nhập số dư USDT hiện tại trên sàn:</label>
                            <div className="relative group">
                                <input 
                                    type="number" 
                                    placeholder="Ví dụ: 5000"
                                    value={manualBalance}
                                    onChange={(e) => setManualBalance(e.target.value)}
                                    className="w-full md:w-80 bg-white border-0 rounded-xl px-4 py-3 pl-10 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-400/30 shadow-xl shadow-indigo-900/10 transition-all font-mono text-lg"
                                />
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold">$</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 w-full md:w-auto flex flex-col md:items-end gap-2">
                         {manualBalance ? (
                             <div className="text-right bg-white/10 rounded-2xl p-6 backdrop-blur-sm border border-white/10 min-w-[280px]">
                                <p className="text-indigo-100 text-sm font-medium mb-1">Ước tính Lãi / Lỗ</p>
                                <div className="flex items-center justify-end gap-2">
                                    {pnlStatus === 'profit' ? <TrendingUp className="w-6 h-6 text-emerald-300"/> : <TrendingDown className="w-6 h-6 text-rose-300"/>}
                                    <span className={`text-3xl font-bold font-mono tracking-tight ${pnlStatus === 'profit' ? 'text-emerald-300' : 'text-rose-300'}`}>
                                        {pnlUsdt && pnlUsdt > 0 ? '+' : ''}{formatUSDT(pnlUsdt || 0)}
                                    </span>
                                </div>
                                <p className="text-xs text-indigo-200 mt-2 opacity-80">
                                    {pnlStatus === 'profit' ? 'Bạn đang có lãi so với vốn P2P' : 'Bạn đang lỗ so với vốn P2P'}
                                </p>
                             </div>
                         ) : (
                             <div className="text-right opacity-60">
                                 <p className="text-2xl font-bold">--- USDT</p>
                                 <p className="text-sm">Nhập số dư để xem lãi lỗ</p>
                             </div>
                         )}
                    </div>
                </div>
            </div>
        </section>

        {/* Summary Grid */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricsCard 
            title="Số Dư P2P (Net)" 
            value={formatUSDT(summary.netHoldingUsdt)}
            subValue={`Vốn thực bỏ ra: ${formatVND(summary.netCostVnd)}`}
            type="balance"
          />
           <MetricsCard 
            title="Giá Vốn Trung Bình" 
            value={`${new Intl.NumberFormat('vi-VN').format(Math.round(summary.avgCost))} VND`}
            subValue="Cho 1 USDT"
            type="neutral"
          />
          <MetricsCard 
            title="Tổng Đã Mua" 
            value={formatUSDT(summary.totalBuyUsdt)}
            subValue={formatVND(summary.totalBuyVnd)}
            type="buy"
          />
          <MetricsCard 
            title="Tổng Đã Bán" 
            value={formatUSDT(summary.totalSellUsdt)}
            subValue={formatVND(summary.totalSellVnd)}
            type="sell"
          />
        </section>

        {/* Charts Section */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <PriceChart data={transactions} />
          <VolumeChart data={transactions} />
        </section>

        {/* Transaction Table */}
        <section>
          <TransactionTable data={transactions} />
        </section>

      </main>

      <footer className="border-t border-slate-200 bg-white py-10 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center">
            <p className="text-slate-800 font-semibold mb-2">P2P Analytics Dashboard</p>
            <p className="text-slate-500 text-sm">Dữ liệu được cập nhật tự động • Thiết kế tối ưu cho trải nghiệm người dùng</p>
        </div>
      </footer>
    </div>
  );
};

export default App;