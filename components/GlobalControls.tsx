import React, { useState } from 'react';
import { LayoutGrid, Plus, Search, CheckSquare, Square, Trash2, Moon, Sun, Columns, Grid2X2, RectangleHorizontal, LayoutPanelLeft } from 'lucide-react';

interface GlobalControlsProps {
  onAddChart: () => void;
  onSync: (symbol: string, interval: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onClearAll: () => void;
  onToggleTheme: () => void;
  globalTheme: 'Light' | 'Dark';
  activeCount: number;
  selectedCount: number;
  layoutCols: number;
  onSetLayoutCols: (cols: number) => void;
}

const INTERVALS = [
  { label: '1p', value: '1' },
  { label: '3p', value: '3' },
  { label: '5p', value: '5' },
  { label: '15p', value: '15' },
  { label: '30p', value: '30' },
  { label: '1g', value: '60' },
  { label: '2g', value: '120' },
  { label: '4g', value: '240' },
  { label: '12g', value: '720' },
  { label: '1N', value: 'D' },
  { label: '1T', value: 'W' },
  { label: '1Th', value: 'M' },
];

const GlobalControls: React.FC<GlobalControlsProps> = ({ 
  onAddChart, 
  onSync, 
  onSelectAll,
  onDeselectAll,
  onClearAll,
  onToggleTheme,
  globalTheme,
  activeCount,
  selectedCount,
  layoutCols,
  onSetLayoutCols
}) => {
  const [globalSymbol, setGlobalSymbol] = useState('');
  const [globalInterval, setGlobalInterval] = useState('60');
  const isDark = globalTheme === 'Dark';

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

  const LayoutIcon = ({ cols }: { cols: number }) => {
    switch(cols) {
        case 1: return <RectangleHorizontal className="w-4 h-4" />;
        case 2: return <Grid2X2 className="w-4 h-4" />;
        case 3: return <LayoutPanelLeft className="w-4 h-4" />; // Approximate for 3
        case 4: return <Columns className="w-4 h-4" />;
        default: return <Grid2X2 className="w-4 h-4" />;
    }
  };

  // Theme-based styling constants
  const containerClass = isDark 
    ? "bg-slate-900/80 border-slate-800" 
    : "bg-white/80 border-slate-200";
  
  const textPrimary = isDark ? "text-slate-100" : "text-slate-800";
  const textSecondary = isDark ? "text-slate-400" : "text-slate-400";
  
  const inputClass = isDark
    ? "bg-slate-800 border-slate-700 text-white placeholder-slate-500 focus:ring-brand-500/50"
    : "bg-slate-50 border-slate-200 text-slate-800 placeholder-slate-400 focus:ring-brand-500/30";

  const buttonBase = isDark
    ? "text-slate-300 hover:bg-slate-800 hover:text-white"
    : "text-slate-600 hover:bg-slate-50 hover:text-brand-600";
  
  const intervalContainer = isDark 
    ? "bg-slate-800 border-slate-700" 
    : "bg-slate-100 border-slate-200";

  const intervalActive = isDark
    ? "bg-slate-700 text-brand-400 shadow-sm ring-1 ring-slate-600"
    : "bg-white text-brand-600 shadow-sm ring-1 ring-slate-200";

  const intervalInactive = isDark
    ? "text-slate-400 hover:text-white hover:bg-slate-700/50"
    : "text-slate-500 hover:text-slate-800 hover:bg-slate-200/50";

  const divider = isDark ? "bg-slate-700" : "bg-slate-200";
  const groupContainer = isDark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200";

  return (
    <div className={`sticky top-0 z-50 w-full backdrop-blur-md border-b px-4 py-3 shadow-sm mb-4 transition-colors duration-300 ${containerClass}`}>
      <div className="max-w-[1920px] mx-auto flex flex-col xl:flex-row items-center justify-between gap-4">
        
        {/* Logo & Title */}
        <div className="flex items-center gap-3 min-w-max self-start xl:self-center">
          <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl shadow-lg shadow-brand-500/20 text-white">
            <LayoutGrid className="w-6 h-6" />
          </div>
          <div>
            <h1 className={`text-lg font-bold leading-tight tracking-tight ${textPrimary}`}>
              CryptoSync <span className="text-brand-600">Pro</span>
            </h1>
            <p className={`text-[11px] font-semibold uppercase tracking-wider ${textSecondary}`}>Terminal Đa Biểu Đồ</p>
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
                placeholder={selectedCount > 0 ? `Đồng bộ ${selectedCount} mục chọn...` : "Đồng bộ tất cả..."}
                className={`block w-full pl-10 pr-3 py-2.5 border rounded-xl leading-5 focus:outline-none focus:ring-2 transition-all text-sm font-semibold shadow-inner ${inputClass}`}
                />
            </form>
          </div>

          {/* Interval Toggles */}
          <div className={`flex p-1 rounded-xl gap-0.5 overflow-x-auto w-full md:w-auto no-scrollbar border ${intervalContainer}`}>
            {INTERVALS.map((int) => (
              <button
                key={int.value}
                onClick={() => handleIntervalChange(int.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                  globalInterval === int.value ? intervalActive : intervalInactive
                }`}
              >
                {int.label}
              </button>
            ))}
          </div>
        </div>

        {/* Action Tools (Right) */}
        <div className={`flex items-center gap-3 min-w-max w-full xl:w-auto justify-end border-t xl:border-t-0 pt-3 xl:pt-0 ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
            
             {/* Layout Select */}
             <div className={`flex items-center border rounded-xl p-1 shadow-sm ${groupContainer}`}>
                {[1, 2, 3, 4].map(cols => (
                    <button
                        key={cols}
                        onClick={() => onSetLayoutCols(cols)}
                        className={`p-1.5 rounded-lg transition-all ${
                            layoutCols === cols 
                                ? 'bg-brand-500 text-white shadow-sm' 
                                : buttonBase
                        }`}
                        title={`${cols} Cột`}
                    >
                        <LayoutIcon cols={cols} />
                    </button>
                ))}
             </div>

            {/* Global Theme Toggle */}
             <button
                onClick={onToggleTheme}
                className={`p-2.5 rounded-xl transition-all border ${
                    globalTheme === 'Dark' 
                    ? 'bg-slate-800 text-yellow-400 border-slate-700 hover:bg-slate-700' 
                    : 'bg-amber-100 text-amber-600 border-amber-200 hover:bg-amber-200'
                }`}
                title={`Chuyển sang chế độ ${globalTheme === 'Light' ? 'Tối' : 'Sáng'}`}
            >
                {globalTheme === 'Light' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            {/* Selection Tools */}
            <div className={`flex items-center border rounded-xl p-1 shadow-sm ${groupContainer}`}>
              <button 
                onClick={onSelectAll}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${buttonBase}`}
                title="Chọn tất cả"
              >
                <CheckSquare className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Tất cả</span>
              </button>
              <div className={`w-px h-4 mx-1 ${divider}`}></div>
              <button 
                onClick={onDeselectAll}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${buttonBase}`}
                title="Bỏ chọn tất cả"
              >
                <Square className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Bỏ chọn</span>
              </button>
            </div>

            <button
                onClick={onClearAll}
                className={`p-2.5 rounded-xl transition-all border border-transparent ${isDark ? 'text-slate-500 hover:text-red-400 hover:bg-red-900/20' : 'text-slate-400 hover:text-red-500 hover:bg-red-50 hover:border-red-100'}`}
                title="Xóa tất cả biểu đồ"
            >
                <Trash2 className="w-5 h-5" />
            </button>

            <button
                onClick={onAddChart}
                className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-xl active:scale-95 transition-all shadow-lg shadow-brand-500/20"
            >
                <Plus className="w-4 h-4" />
                <span>Thêm Mới</span>
            </button>
        </div>
      </div>
    </div>
  );
};

export default GlobalControls;