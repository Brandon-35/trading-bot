import React from 'react';
import { ArrowUpRight, ArrowDownRight, DollarSign, Wallet, Activity } from 'lucide-react';

interface MetricsCardProps {
  title: string;
  value: string;
  subValue?: string;
  type: 'buy' | 'sell' | 'neutral' | 'balance' | 'profit' | 'loss';
  icon?: React.ReactNode;
}

export const MetricsCard: React.FC<MetricsCardProps> = ({ title, value, subValue, type, icon }) => {
  const getStyles = () => {
    switch (type) {
      case 'buy':
        return {
          container: 'bg-white border-slate-100 hover:border-emerald-200',
          text: 'text-slate-900',
          subText: 'text-slate-500',
          iconBg: 'bg-emerald-50',
          iconColor: 'text-emerald-600'
        };
      case 'sell':
        return {
          container: 'bg-white border-slate-100 hover:border-rose-200',
          text: 'text-slate-900',
          subText: 'text-slate-500',
          iconBg: 'bg-rose-50',
          iconColor: 'text-rose-600'
        };
      case 'balance':
        return {
          container: 'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-100',
          text: 'text-blue-900',
          subText: 'text-blue-600',
          iconBg: 'bg-white',
          iconColor: 'text-blue-600'
        };
      case 'profit':
        return {
          container: 'bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-100',
          text: 'text-emerald-900',
          subText: 'text-emerald-600',
          iconBg: 'bg-white',
          iconColor: 'text-emerald-600'
        };
      case 'loss':
        return {
          container: 'bg-gradient-to-br from-rose-50 to-orange-50 border-rose-100',
          text: 'text-rose-900',
          subText: 'text-rose-600',
          iconBg: 'bg-white',
          iconColor: 'text-rose-600'
        };
      default:
        return {
          container: 'bg-white border-slate-100',
          text: 'text-slate-900',
          subText: 'text-slate-500',
          iconBg: 'bg-slate-50',
          iconColor: 'text-slate-600'
        };
    }
  };

  const styles = getStyles();

  const getIcon = () => {
    if (icon) return icon;
    switch (type) {
      case 'buy': return <ArrowDownRight className={`w-5 h-5 ${styles.iconColor}`} />;
      case 'sell': return <ArrowUpRight className={`w-5 h-5 ${styles.iconColor}`} />;
      case 'balance': return <Wallet className={`w-5 h-5 ${styles.iconColor}`} />;
      case 'profit': return <Activity className={`w-5 h-5 ${styles.iconColor}`} />;
      case 'loss': return <Activity className={`w-5 h-5 ${styles.iconColor}`} />;
      default: return <DollarSign className={`w-5 h-5 ${styles.iconColor}`} />;
    }
  };

  return (
    <div className={`p-6 rounded-2xl border shadow-sm transition-all hover:shadow-md hover:scale-[1.01] ${styles.container}`}>
      <div className="flex justify-between items-start">
        <div>
          <p className={`text-sm font-medium mb-1 opacity-80 ${type === 'balance' || type === 'profit' || type === 'loss' ? styles.text : 'text-slate-500'}`}>{title}</p>
          <h3 className={`text-2xl font-bold tracking-tight ${styles.text}`}>{value}</h3>
          {subValue && (
            <p className={`text-xs font-medium mt-2 ${styles.subText}`}>{subValue}</p>
          )}
        </div>
        <div className={`p-3 rounded-xl ${styles.iconBg} shadow-sm`}>
          {getIcon()}
        </div>
      </div>
    </div>
  );
};