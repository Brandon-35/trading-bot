import React from 'react';
import { Transaction } from '../types';
import { ArrowDownCircle, ArrowUpCircle } from 'lucide-react';

interface TransactionTableProps {
  data: Transaction[];
}

export const TransactionTable: React.FC<TransactionTableProps> = ({ data }) => {
  const formatCurrency = (val: number, currency: 'VND' | 'USDT') => {
    if (currency === 'VND') {
      return new Intl.NumberFormat('vi-VN', {
        style: 'decimal',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(val);
    }
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(val);
  };

  return (
    <div className="w-full bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
      <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-white">
        <h2 className="text-lg font-bold text-slate-800">Lịch sử Giao dịch</h2>
        <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1 rounded-full border border-slate-200">
          {data.length} bản ghi
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider font-semibold">
              <th className="p-4 border-b border-slate-100">Loại</th>
              <th className="p-4 border-b border-slate-100">Ngày & Giờ</th>
              <th className="p-4 border-b border-slate-100">Đối tác</th>
              <th className="p-4 border-b border-slate-100 text-right">Giá (VND)</th>
              <th className="p-4 border-b border-slate-100 text-right">VNĐ</th>
              <th className="p-4 border-b border-slate-100 text-right">USDT</th>
              <th className="p-4 border-b border-slate-100 text-center">Trạng thái</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((tx) => (
              <tr key={tx.order_id} className="hover:bg-slate-50/80 transition-colors group">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-full ${tx.type === 'buy' ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                        {tx.type === 'buy' ? (
                        <ArrowDownCircle className="w-4 h-4" />
                        ) : (
                        <ArrowUpCircle className="w-4 h-4" />
                        )}
                    </div>
                    <span className={`font-semibold capitalize text-sm ${tx.type === 'buy' ? 'text-emerald-700' : 'text-rose-700'}`}>
                      {tx.type === 'buy' ? 'Mua' : 'Bán'}
                    </span>
                  </div>
                </td>
                <td className="p-4">
                  <div className="text-sm font-medium text-slate-700">{tx.date.split(' ')[0]}</div>
                  <div className="text-xs text-slate-400">{tx.date.split(' ')[1]}</div>
                </td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700">{tx.counterparty}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono truncate max-w-[80px] group-hover:max-w-none transition-all">
                    #{tx.order_id.slice(-6)}
                  </div>
                </td>
                <td className="p-4 text-right font-mono text-sm text-slate-600">
                  {formatCurrency(tx.price_vnd, 'VND')}
                </td>
                <td className="p-4 text-right font-mono text-sm font-medium text-slate-700">
                  {formatCurrency(tx.vnd_amount, 'VND')} ₫
                </td>
                <td className="p-4 text-right font-mono text-sm font-bold text-slate-800">
                  {formatCurrency(tx.usdt_amount, 'USDT')} ₮
                </td>
                <td className="p-4 text-center">
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">
                    {tx.status === 'completed' ? 'Hoàn tất' : tx.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};