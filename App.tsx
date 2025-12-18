import React, { useState, useCallback } from 'react';
import { ChartConfig } from './types';
import TradingViewWidget from './components/TradingViewWidget';
import GlobalControls from './components/GlobalControls';
import AddChartModal from './components/AddChartModal';
import { X, Maximize2, CheckCircle2, Settings, Moon, Sun, Eye, EyeOff } from 'lucide-react';

// Default charts to show on load
const DEFAULT_CHARTS: ChartConfig[] = [
  { id: 'chart_1', symbol: 'BINANCE:BTCUSDT', interval: '60', timezone: 'Etc/UTC', theme: 'Light', selected: false, hideToolbar: false },
  { id: 'chart_2', symbol: 'BINANCE:ETHUSDT', interval: '60', timezone: 'Etc/UTC', theme: 'Light', selected: false, hideToolbar: false },
  { id: 'chart_3', symbol: 'BINANCE:SOLUSDT', interval: '60', timezone: 'Etc/UTC', theme: 'Light', selected: false, hideToolbar: false },
  { id: 'chart_4', symbol: 'BINANCE:BNBUSDT', interval: '60', timezone: 'Etc/UTC', theme: 'Light', selected: false, hideToolbar: false },
];

const App: React.FC = () => {
  const [charts, setCharts] = useState<ChartConfig[]>(DEFAULT_CHARTS);
  const [lastId, setLastId] = useState(4);
  const [chartToRemove, setChartToRemove] = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [openSettingsId, setOpenSettingsId] = useState<string | null>(null);

  // --- Chart Management ---

  const handleAddChart = (symbol: string, interval: string) => {
    const newId = lastId + 1;
    setLastId(newId);
    
    const newChart: ChartConfig = {
      id: `chart_${newId}_${Date.now()}`,
      symbol: symbol || 'BINANCE:BTCUSDT',
      interval: interval || '60',
      timezone: 'Etc/UTC',
      theme: 'Light',
      selected: false,
      hideToolbar: false
    };
    
    setCharts(prev => [...prev, newChart]);
  };

  const initiateRemoveChart = (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selection when clicking delete
    setChartToRemove(id);
  };

  const confirmRemoveChart = () => {
    if (chartToRemove) {
      setCharts(prev => prev.filter(c => c.id !== chartToRemove));
      setChartToRemove(null);
    }
  };

  const cancelRemoveChart = () => {
    setChartToRemove(null);
  };

  const clearAllCharts = () => {
    if (window.confirm("Are you sure you want to remove ALL charts?")) {
        setCharts([]);
    }
  };

  const updateChartConfig = (id: string, updates: Partial<ChartConfig>) => {
    setCharts(prev => prev.map(c => 
      c.id === id ? { ...c, ...updates } : c
    ));
    // We don't close the menu automatically to allow multiple changes
  };

  // --- Selection Logic ---

  const handleChartClick = (id: string, e: React.MouseEvent) => {
    setOpenSettingsId(null); // Close settings when clicking a chart
    
    const isMultiSelect = e.ctrlKey || e.metaKey || e.shiftKey;

    setCharts(prev => prev.map(chart => {
      if (chart.id === id) {
        // If clicking the specific chart
        if (isMultiSelect) {
          // Toggle selection
          return { ...chart, selected: !chart.selected };
        }
        // Single select: Always select this one
        return { ...chart, selected: true };
      } else {
        // For other charts
        if (isMultiSelect) {
          // Keep their state
          return chart;
        }
        // Single select: Deselect others
        return { ...chart, selected: false };
      }
    }));
  };

  const selectAll = () => {
    setCharts(prev => prev.map(c => ({ ...c, selected: true })));
  };

  const deselectAll = () => {
    setCharts(prev => prev.map(c => ({ ...c, selected: false })));
  };

  // --- Smart Sync Logic ---

  const syncCharts = useCallback((globalSymbol: string, globalInterval: string) => {
    setCharts(prevCharts => {
      // 1. Check if ANY chart is selected
      const hasSelection = prevCharts.some(c => c.selected);

      return prevCharts.map(chart => {
        // 2. Determine if this chart should be updated
        const shouldUpdate = hasSelection ? chart.selected : true;

        if (!shouldUpdate) return chart;

        return {
          ...chart,
          interval: globalInterval,
          // Only update symbol if the user actually typed something non-empty
          symbol: globalSymbol.trim() === '' ? chart.symbol : globalSymbol
        };
      });
    });
  }, []);

  // --- Layout Helper ---
  const getGridClass = (count: number) => {
    if (count === 1) return 'grid-cols-1 h-full';
    if (count === 2) return 'grid-cols-1 md:grid-cols-2';
    if (count === 3) return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3';
    if (count === 4) return 'grid-cols-1 md:grid-cols-2'; // 2x2
    if (count >= 5 && count <= 6) return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3';
    return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4';
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <GlobalControls 
        onAddChart={() => setIsAddModalOpen(true)}
        onSync={syncCharts}
        onSelectAll={selectAll}
        onDeselectAll={deselectAll}
        onClearAll={clearAllCharts}
        activeCount={charts.length}
        selectedCount={charts.filter(c => c.selected).length}
      />

      <main className="flex-1 overflow-y-auto p-4 custom-scrollbar" onClick={(e) => {
          // Optional: Click background to deselect all?
          if (e.target === e.currentTarget) {
            deselectAll();
            setOpenSettingsId(null);
          }
      }}>
        <div className={`grid gap-4 w-full min-h-[500px] ${getGridClass(charts.length)} auto-rows-[400px] md:auto-rows-[500px]`}>
          {charts.map((chart) => (
            <div 
              key={chart.id}
              onClick={(e) => handleChartClick(chart.id, e)}
              className={`
                relative group bg-white rounded-2xl shadow-sm border overflow-hidden transition-all duration-200
                ${chart.selected 
                    ? 'ring-2 ring-brand-500 border-brand-500 shadow-md transform scale-[1.005] z-10' 
                    : 'border-slate-100 hover:border-slate-300 hover:shadow-md'
                }
              `}
            >
              {/* Header / Toolbar overlay */}
              <div 
                className={`
                    absolute top-0 left-0 right-0 h-10 z-20 flex items-center justify-between px-3
                    bg-gradient-to-b from-white via-white/90 to-transparent
                    transition-opacity duration-200
                    ${chart.selected || openSettingsId === chart.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}
                `}
              >
                {/* Left: Chart Info */}
                <div className="flex items-center gap-2">
                    {chart.selected && <CheckCircle2 className="w-4 h-4 text-brand-500" />}
                    <span className="text-xs font-bold text-slate-700 bg-slate-100/80 backdrop-blur px-2 py-1 rounded shadow-sm border border-slate-200">
                        {chart.symbol} <span className="text-slate-400">|</span> {chart.interval}
                    </span>
                </div>

                {/* Right: Actions */}
                <div className="flex gap-1">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenSettingsId(openSettingsId === chart.id ? null : chart.id);
                    }}
                    className={`p-1.5 rounded-md transition-colors ${openSettingsId === chart.id ? 'text-brand-500 bg-brand-50' : 'text-slate-400 hover:text-brand-500 hover:bg-brand-50'}`}
                    title="Settings"
                  >
                    <Settings className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={(e) => initiateRemoveChart(chart.id, e)}
                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                    title="Remove Chart"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Settings Menu Overlay */}
              {openSettingsId === chart.id && (
                <div 
                  className="absolute top-11 right-3 z-30 bg-white rounded-xl shadow-xl border border-slate-100 p-2 w-40 animate-in fade-in zoom-in-95 duration-200"
                  onClick={(e) => e.stopPropagation()} // Prevent clicking menu from selecting chart
                >
                  <div className="text-[10px] font-bold text-slate-400 mb-2 px-2 uppercase tracking-wider">Theme</div>
                  <div className="flex flex-col gap-1">
                    <button 
                      onClick={() => updateChartConfig(chart.id, { theme: 'Light' })}
                      className={`flex items-center gap-2 px-2 py-1.5 text-xs rounded-lg transition-colors w-full text-left ${chart.theme === 'Light' ? 'bg-brand-50 text-brand-600 font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                    >
                      <Sun className="w-3.5 h-3.5" /> Light
                    </button>
                    <button 
                      onClick={() => updateChartConfig(chart.id, { theme: 'Dark' })}
                      className={`flex items-center gap-2 px-2 py-1.5 text-xs rounded-lg transition-colors w-full text-left ${chart.theme === 'Dark' ? 'bg-slate-800 text-white font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                    >
                      <Moon className="w-3.5 h-3.5" /> Dark
                    </button>
                  </div>

                  <div className="text-[10px] font-bold text-slate-400 mb-2 px-2 uppercase tracking-wider mt-3">View</div>
                  <div className="flex flex-col gap-1">
                     <button 
                      onClick={() => updateChartConfig(chart.id, { hideToolbar: !chart.hideToolbar })}
                      className={`flex items-center gap-2 px-2 py-1.5 text-xs rounded-lg transition-colors w-full text-left text-slate-600 hover:bg-slate-50`}
                    >
                      {chart.hideToolbar ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                      {chart.hideToolbar ? 'Show Toolbar' : 'Hide Toolbar'}
                    </button>
                  </div>
                </div>
              )}

              {/* The Widget */}
              <div className="w-full h-full pt-4"> 
                <TradingViewWidget 
                  symbol={chart.symbol}
                  interval={chart.interval}
                  containerId={`tv_container_${chart.id}`}
                  theme={chart.theme}
                  hideToolbar={chart.hideToolbar}
                />
              </div>
            </div>
          ))}
          
          {charts.length === 0 && (
             <div className="col-span-full h-full flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
                <Maximize2 className="w-12 h-12 mb-4 opacity-20" />
                <p>No active charts.</p>
                <button 
                  onClick={() => setIsAddModalOpen(true)}
                  className="mt-4 text-brand-500 hover:underline font-medium"
                >
                  Add your first chart
                </button>
             </div>
          )}
        </div>
      </main>

      {/* Add Chart Modal */}
      <AddChartModal 
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddChart}
      />

      {/* Confirmation Modal for Delete */}
      {chartToRemove && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/20 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-100 p-6 max-w-sm w-full transform transition-all scale-100 animate-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-slate-800 mb-2">Remove Chart?</h3>
            <p className="text-slate-500 mb-6 text-sm leading-relaxed">
              Are you sure you want to remove this chart? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={cancelRemoveChart}
                className="px-4 py-2 text-slate-600 font-medium hover:bg-slate-50 rounded-xl transition-colors text-sm"
              >
                Cancel
              </button>
              <button 
                onClick={confirmRemoveChart}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-medium rounded-xl shadow-lg shadow-red-500/30 transition-all active:scale-95 text-sm"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;