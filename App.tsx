import React, { useState, useCallback, useRef } from 'react';
import { ChartConfig } from './types';
import TradingViewWidget from './components/TradingViewWidget';
import GlobalControls from './components/GlobalControls';
import AddChartModal from './components/AddChartModal';
import { X, Maximize2, CheckCircle2, Settings, Moon, Sun, Eye, EyeOff, GripVertical } from 'lucide-react';

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
  
  // Drag and Drop State
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

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
        return { ...chart, selected: !chart.selected }; // Toggle on single click too for better UX
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
        // IF selected exists: Only update selected.
        // IF NO selected: Update ALL.
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

  // --- Drag and Drop Logic ---

  const handleDragStart = (e: React.DragEvent<HTMLDivElement>, position: number) => {
    dragItem.current = position;
    e.dataTransfer.effectAllowed = "move";
    // Add a ghost image or styling if needed, usually browser handles it
    e.currentTarget.classList.add('opacity-50');
  };

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>, position: number) => {
    e.preventDefault();
    dragOverItem.current = position;
  };

  const handleDragEnd = (e: React.DragEvent<HTMLDivElement>) => {
    e.currentTarget.classList.remove('opacity-50');
    
    if (dragItem.current === null || dragOverItem.current === null) return;
    if (dragItem.current === dragOverItem.current) return;

    const copyListItems = [...charts];
    const dragItemContent = copyListItems[dragItem.current];
    
    // Remove from old pos
    copyListItems.splice(dragItem.current, 1);
    // Insert at new pos
    copyListItems.splice(dragOverItem.current, 0, dragItemContent);
    
    dragItem.current = null;
    dragOverItem.current = null;
    setCharts(copyListItems);
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

      <main 
        className="flex-1 overflow-y-auto p-4 custom-scrollbar" 
        onClick={(e) => {
          // Deselect if clicking the background grid area
          if (e.target === e.currentTarget) {
            deselectAll();
            setOpenSettingsId(null);
          }
        }}
      >
        <div className={`auto-grid w-full min-h-[500px] auto-rows-[450px]`}>
          {charts.map((chart, index) => (
            <div 
              key={chart.id}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragEnter={(e) => handleDragEnter(e, index)}
              onDragEnd={handleDragEnd}
              onDragOver={(e) => e.preventDefault()}
              onClick={(e) => handleChartClick(chart.id, e)}
              className={`
                relative group bg-white rounded-xl shadow-sm border overflow-hidden transition-all duration-200
                flex flex-col h-[450px]
                ${chart.selected 
                    ? 'ring-2 ring-brand-500 ring-offset-2 border-brand-500 shadow-md z-10' 
                    : 'border-slate-200 hover:border-slate-300 hover:shadow-lg'
                }
              `}
            >
              {/* Toolbar */}
              <div 
                className={`
                    flex items-center justify-between px-3 py-2
                    bg-white border-b border-slate-100 h-12 shrink-0 select-none
                    ${chart.selected ? 'bg-brand-50/30' : ''}
                `}
              >
                {/* Left: Drag Handle & Info */}
                <div className="flex items-center gap-2 overflow-hidden">
                    <div className="cursor-grab active:cursor-grabbing text-slate-300 hover:text-slate-500 p-1">
                        <GripVertical className="w-4 h-4" />
                    </div>
                    
                    <div className="flex flex-col leading-tight">
                        <span className="text-xs font-bold text-slate-700 truncate max-w-[120px]">
                            {chart.symbol}
                        </span>
                        <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 rounded">
                                {chart.interval}
                            </span>
                            {chart.selected && (
                                <span className="flex items-center gap-1 text-[10px] font-bold text-brand-600 bg-brand-50 px-1.5 rounded border border-brand-100">
                                    <CheckCircle2 className="w-3 h-3" /> Selected
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-1">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenSettingsId(openSettingsId === chart.id ? null : chart.id);
                    }}
                    className={`p-1.5 rounded-lg transition-colors ${openSettingsId === chart.id ? 'text-brand-500 bg-brand-50' : 'text-slate-400 hover:text-brand-600 hover:bg-slate-100'}`}
                    title="Settings"
                  >
                    <Settings className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={(e) => initiateRemoveChart(chart.id, e)}
                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Remove Chart"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Settings Menu Dropdown */}
              {openSettingsId === chart.id && (
                <div 
                  className="absolute top-12 right-2 z-30 bg-white rounded-xl shadow-xl border border-slate-100 p-2 w-48 animate-in fade-in zoom-in-95 duration-200"
                  onClick={(e) => e.stopPropagation()} 
                >
                  <div className="text-[10px] font-bold text-slate-400 mb-2 px-2 uppercase tracking-wider">Appearance</div>
                  <div className="space-y-1">
                    <button 
                      onClick={() => updateChartConfig(chart.id, { theme: chart.theme === 'Light' ? 'Dark' : 'Light' })}
                      className={`flex items-center justify-between px-2 py-1.5 text-xs rounded-lg transition-colors w-full text-left hover:bg-slate-50 text-slate-600`}
                    >
                      <div className="flex items-center gap-2">
                        {chart.theme === 'Light' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
                        <span>Theme</span>
                      </div>
                      <span className={`text-[10px] px-1.5 rounded font-medium ${chart.theme === 'Light' ? 'bg-slate-100 text-slate-500' : 'bg-slate-800 text-white'}`}>
                        {chart.theme}
                      </span>
                    </button>
                  </div>

                  <div className="h-px bg-slate-100 my-2"></div>

                  <div className="text-[10px] font-bold text-slate-400 mb-2 px-2 uppercase tracking-wider">Widget Controls</div>
                  <div className="space-y-1">
                     <button 
                      onClick={() => updateChartConfig(chart.id, { hideToolbar: !chart.hideToolbar })}
                      className={`flex items-center gap-2 px-2 py-1.5 text-xs rounded-lg transition-colors w-full text-left ${chart.hideToolbar ? 'text-brand-600 bg-brand-50 font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                    >
                      {chart.hideToolbar ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      {chart.hideToolbar ? 'Toolbar Hidden' : 'Toolbar Visible'}
                    </button>
                  </div>
                </div>
              )}

              {/* The Widget */}
              <div className="flex-1 w-full h-full relative bg-slate-50"> 
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
             <div className="col-span-full min-h-[400px] flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 rounded-2xl bg-white/50">
                <Maximize2 className="w-16 h-16 mb-4 text-slate-300" />
                <h3 className="text-lg font-semibold text-slate-600">Your dashboard is empty</h3>
                <p className="text-sm text-slate-400 max-w-xs text-center mt-2">Add charts to monitor multiple pairs simultaneously with real-time synchronization.</p>
                <button 
                  onClick={() => setIsAddModalOpen(true)}
                  className="mt-6 px-6 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-full font-medium shadow-lg shadow-brand-500/20 transition-all active:scale-95"
                >
                  Create New Chart
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
              Are you sure you want to remove this chart?
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