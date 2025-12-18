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
    <div className="sticky top-0 z-50 w-full glass-panel border-b border-slate-200/60 px-4 py-3 shadow-sm mb-4">
      <div className="max-w-7xl mx-auto flex flex-col xl:flex-row items-center justify-between gap-4">
        
        {/* Logo & Title */}
        <div className="flex items-center gap-2 min-w-max self-start xl:self-center">
          <div className="p-2 bg-brand-500 rounded-lg shadow-lg shadow-brand-500/30">
            <LayoutGrid className="w-5 h-5 text-white" />
          </div>
          <div className="hidden sm:block">
            <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-800 to-slate-600 leading-tight">
              CryptoSync
            </h1>
            <p className="text-[10px] font-medium text-slate-400 leading-none">Pro Dashboard</p>
          </div>
        </div>

        {/* Master Controls (Center) */}
        <div className="flex-1 w-full xl:w-auto flex flex-col md:flex-row items-center justify-center gap-3">
          
          {/* Symbol Input */}
          <form onSubmit={handleSymbolSubmit} className="relative group w-full md:w-60">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-4 w-4 text-slate-400 group-focus-within:text-brand-500 transition-colors" />
            </div>
            <input
              type="text"
              value={globalSymbol}
              onChange={(e) => setGlobalSymbol(e.target.value.toUpperCase())}
              placeholder={selectedCount > 0 ? `Sync ${selectedCount} selected...` : "Sync all symbols..."}
              className={`block w-full pl-10 pr-3 py-2 border rounded-xl leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/50 transition-all text-sm font-medium shadow-sm ${
                selectedCount > 0 ? 'border-brand-300 focus:border-brand-500' : 'border-slate-200 focus:border-brand-500'
              }`}
            />
          </form>

          {/* Interval Toggles */}
          <div className="flex bg-slate-100/80 p-1 rounded-xl gap-1 overflow-x-auto w-full md:w-auto no-scrollbar">
            {INTERVALS.map((int) => (
              <button
                key={int.value}
                onClick={() => handleIntervalChange(int.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                  globalInterval === int.value
                    ? 'bg-white text-brand-600 shadow-sm ring-1 ring-slate-200'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'
                }`}
              >
                {int.label}
              </button>
            ))}
          </div>
        </div>

        {/* Action Tools (Right) */}
        <div className="flex items-center gap-2 min-w-max w-full xl:w-auto justify-end border-t xl:border-t-0 border-slate-100 pt-3 xl:pt-0">
            
            {/* Selection Tools */}
            <div className="flex items-center gap-1 mr-2 bg-slate-100/50 p-1 rounded-lg">
              <button 
                onClick={onSelectAll}
                className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-white rounded-md transition-all"
                title="Select All"
              >
                <CheckSquare className="w-4 h-4" />
              </button>
              <button 
                onClick={onDeselectAll}
                className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-white rounded-md transition-all"
                title="Deselect All"
              >
                <Square className="w-4 h-4" />
              </button>
            </div>

            <div className="h-6 w-px bg-slate-200 mx-1"></div>

            <button
                onClick={onClearAll}
                className="flex items-center gap-2 px-3 py-2 text-slate-500 hover:text-red-500 hover:bg-red-50 text-sm font-medium rounded-xl transition-all"
            >
                <Trash2 className="w-4 h-4" />
                <span className="hidden lg:inline">Clear</span>
            </button>

            <button
                onClick={onAddChart}
                className="flex items-center gap-2 px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-xl hover:bg-brand-600 active:scale-95 transition-all shadow-lg shadow-brand-500/30 ml-2"
            >
                <Plus className="w-4 h-4" />
                Add
            </button>
        </div>
      </div>
      
      <style>{`
        .glass-panel {
          background: rgba(255, 255, 255, 0.85);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
        }
      `}</style>
    </div>
  );
};

export default GlobalControls;