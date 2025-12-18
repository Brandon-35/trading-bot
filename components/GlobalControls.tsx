import React, { useState } from 'react';
import { LayoutGrid, RefreshCw, Plus, Search, CheckSquare, Square, Trash2 } from 'lucide-react';

interface GlobalControlsProps {
  onAddChart: () => void;
  onSync: (symbol: string, interval: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onClearAll: () => void;
  activeCount: number;
  selectedCount: number;
}

const INTERVALS = [
  { label: '1m', value: '1' },
  { label: '5m', value: '5' },
  { label: '15m', value: '15' },
  { label: '1h', value: '60' },
  { label: '4h', value: '240' },
  { label: '1D', value: 'D' },
];

const GlobalControls: React.FC<GlobalControlsProps> = ({ 
  onAddChart, 
  onSync, 
  onSelectAll,
  onDeselectAll,
  onClearAll,
  activeCount,
  selectedCount
}) => {
  const [globalSymbol, setGlobalSymbol] = useState('');
  const [globalInterval, setGlobalInterval] = useState('60');

  const handleSync = () => {
    onSync(globalSymbol, globalInterval);
  };

  const handleIntervalChange = (val: string) => {
    setGlobalInterval(val);
    onSync(globalSymbol, val); 
  };

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSync();
  };

  return (
    <div className="sticky top-0 z-50 w-full bg-white/80 backdrop-blur-md border-b border-slate-200 px-4 py-3 shadow-sm mb-4">
      <div className="max-w-[1920px] mx-auto flex flex-col xl:flex-row items-center justify-between gap-4">
        
        {/* Logo & Title */}
        <div className="flex items-center gap-3 min-w-max self-start xl:self-center">
          <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl shadow-lg shadow-brand-500/20 text-white">
            <LayoutGrid className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-800 leading-tight tracking-tight">
              CryptoSync <span className="text-brand-600">Pro</span>
            </h1>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Multi-Chart Terminal</p>
          </div>
        </div>

        {/* Master Controls (Center) */}
        <div className="flex-1 w-full xl:w-auto flex flex-col md:flex-row items-center justify-center gap-3">
          
          <div className="flex items-center gap-2 w-full md:w-auto">
             {/* Symbol Input */}
            <form onSubmit={handleSymbolSubmit} className="relative group w-full md:w-64">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-4 w-4 text-slate-400 group-focus-within:text-brand-500 transition-colors" />
                </div>
                <input
                type="text"
                value={globalSymbol}
                onChange={(e) => setGlobalSymbol(e.target.value.toUpperCase())}
                placeholder={selectedCount > 0 ? `Sync ${selectedCount} selected charts...` : "Sync all charts..."}
                className={`block w-full pl-10 pr-3 py-2.5 border rounded-xl leading-5 bg-slate-50 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-all text-sm font-semibold shadow-inner ${
                    selectedCount > 0 ? 'border-brand-300 focus:border-brand-500 bg-brand-50/30' : 'border-slate-200 focus:border-brand-500'
                }`}
                />
            </form>
          </div>

          {/* Interval Toggles */}
          <div className="flex bg-slate-100 p-1 rounded-xl gap-0.5 overflow-x-auto w-full md:w-auto no-scrollbar border border-slate-200">
            {INTERVALS.map((int) => (
              <button
                key={int.value}
                onClick={() => handleIntervalChange(int.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                  globalInterval === int.value
                    ? 'bg-white text-brand-600 shadow-sm ring-1 ring-slate-200'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/50'
                }`}
              >
                {int.label}
              </button>
            ))}
          </div>
        </div>

        {/* Action Tools (Right) */}
        <div className="flex items-center gap-3 min-w-max w-full xl:w-auto justify-end border-t xl:border-t-0 border-slate-100 pt-3 xl:pt-0">
            
            {/* Selection Tools */}
            <div className="flex items-center bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
              <button 
                onClick={onSelectAll}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-brand-600 hover:bg-slate-50 rounded-lg transition-all"
                title="Select All"
              >
                <CheckSquare className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">All</span>
              </button>
              <div className="w-px h-4 bg-slate-200 mx-1"></div>
              <button 
                onClick={onDeselectAll}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-50 rounded-lg transition-all"
                title="Deselect All"
              >
                <Square className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">None</span>
              </button>
            </div>

            <button
                onClick={onClearAll}
                className="p-2.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all border border-transparent hover:border-red-100"
                title="Clear All Charts"
            >
                <Trash2 className="w-5 h-5" />
            </button>

            <button
                onClick={onAddChart}
                className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-xl active:scale-95 transition-all shadow-lg shadow-brand-500/20"
            >
                <Plus className="w-4 h-4" />
                <span>New Chart</span>
            </button>
        </div>
      </div>
    </div>
  );
};

export default GlobalControls;