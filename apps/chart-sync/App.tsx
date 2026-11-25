import React, { useState, useCallback, useRef, useEffect } from 'react';
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
  const [globalTheme, setGlobalTheme] = useState<'Light' | 'Dark'>('Light');
  const [layoutCols, setLayoutCols] = useState<number>(2); // Default to 2 columns
  
  // Drag and Drop State
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  // Apply body background based on theme
  useEffect(() => {
    if (globalTheme === 'Dark') {
        document.body.classList.add('bg-slate-950');
        document.body.classList.remove('bg-slate-50');
    } else {
        document.body.classList.add('bg-slate-50');
        document.body.classList.remove('bg-slate-950');
    }
  }, [globalTheme]);

  // --- Chart Management ---

  const handleAddChart = (symbol: string, interval: string) => {
    const isDuplicate = charts.some(c => c.symbol === symbol);
    if (isDuplicate) return;

    const newId = lastId + 1;
    setLastId(newId);
    
    const newChart: ChartConfig = {
      id: `chart_${newId}_${Date.now()}`,
      symbol: symbol || 'BINANCE:BTCUSDT',
      interval: interval || '60',
      timezone: 'Etc/UTC',
      theme: globalTheme, 
      selected: false,
      hideToolbar: false
    };
    
    setCharts(prev => [...prev, newChart]);
  };

  const initiateRemoveChart = (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); 
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
    if (window.confirm("Bạn có chắc chắn muốn xóa TẤT CẢ biểu đồ không?")) {
        setCharts([]);
    }
  };

  const updateChartConfig = (id: string, updates: Partial<ChartConfig>) => {
    setCharts(prev => prev.map(c => 
      c.id === id ? { ...c, ...updates } : c
    ));
  };

  const toggleGlobalTheme = () => {
    const newTheme = globalTheme === 'Light' ? 'Dark' : 'Light';
    setGlobalTheme(newTheme);
    setCharts(prev => prev.map(c => ({ ...c, theme: newTheme })));
  };

  const getCoinLogoSymbol = (fullSymbol: string) => {
    try {
        const pair = fullSymbol.split(':')[1] || fullSymbol;
        return pair.replace(/(USDT|BUSD|USD|ETH|BTC|USDC)$/, '').toLowerCase();
    } catch (e) {
        return 'btc'; 
    }
  };

  // --- Selection Logic ---

  const handleChartClick = (id: string, e: React.MouseEvent) => {
    setOpenSettingsId(null); 
    
    const isMultiSelect = e.ctrlKey || e.metaKey || e.shiftKey;

    setCharts(prev => prev.map(chart => {
      if (chart.id === id) {
        if (isMultiSelect) {
          return { ...chart, selected: !chart.selected };
        }
        return { ...chart, selected: !chart.selected }; 
      } else {
        if (isMultiSelect) {
          return chart;
        }
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

  const syncCharts = useCallback((globalSymbol: string, globalInterval: string) => {
    setCharts(prevCharts => {
      const hasSelection = prevCharts.some(c => c.selected);
      return prevCharts.map(chart => {
        const shouldUpdate = hasSelection ? chart.selected : true;
        if (!shouldUpdate) return chart;
        return {
          ...chart,
          interval: globalInterval,
          symbol: globalSymbol.trim() === '' ? chart.symbol : globalSymbol
        };
      });
    });
  }, []);

  // --- Drag and Drop Logic ---

  const handleDragStart = (e: React.DragEvent<HTMLDivElement>, position: number) => {
    dragItem.current = position;
    e.dataTransfer.effectAllowed = "move";
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
    
    copyListItems.splice(dragItem.current, 1);
    copyListItems.splice(dragOverItem.current, 0, dragItemContent);
    
    dragItem.current = null;
    dragOverItem.current = null;
    setCharts(copyListItems);
  };

  // --- Styles based on Theme ---
  const isDark = globalTheme === 'Dark';
  const bgClass = isDark ? 'bg-slate-950' : 'bg-slate-50';
  const cardClass = isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200';
  const textPrimary = isDark ? 'text-slate-100' : 'text-slate-800';
  const textSecondary = isDark ? 'text-slate-400' : 'text-slate-500';
  const headerBorder = isDark ? 'border-slate-800' : 'border-slate-100';
  const hoverBorder = isDark ? 'hover:border-slate-700' : 'hover:border-slate-300';

  // Grid classes
  const gridColsClass = {
      1: 'grid-cols-1',
      2: 'grid-cols-1 md:grid-cols-2',
      3: 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3',
      4: 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4',
  }[layoutCols];

  return (
    <div className={`flex flex-col h-screen ${bgClass} transition-colors duration-300`}>
      <GlobalControls 
        onAddChart={() => setIsAddModalOpen(true)}
        onSync={syncCharts}
        onSelectAll={selectAll}
        onDeselectAll={deselectAll}
        onClearAll={clearAllCharts}
        onToggleTheme={toggleGlobalTheme}
        globalTheme={globalTheme}
        activeCount={charts.length}
        selectedCount={charts.filter(c => c.selected).length}
        layoutCols={layoutCols}
        onSetLayoutCols={setLayoutCols}
      />

      <main 
        className="flex-1 overflow-y-auto p-4 custom-scrollbar" 
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            deselectAll();
            setOpenSettingsId(null);
          }
        }}
      >
        <div className={`grid gap-4 w-full pb-20 ${gridColsClass}`}>
          {charts.map((chart, index) => {
            const coinSymbol = getCoinLogoSymbol(chart.symbol);
            const logoUrl = `https://assets.coincap.io/assets/icons/${coinSymbol}@2x.png`;
            
            return (
            <div 
              key={chart.id}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragEnter={(e) => handleDragEnter(e, index)}
              onDragEnd={handleDragEnd}
              onDragOver={(e) => e.preventDefault()}
              onClick={(e) => handleChartClick(chart.id, e)}
              className={`
                relative group rounded-xl shadow-sm border overflow-hidden transition-shadow duration-200
                flex flex-col min-h-[300px] h-[450px] resize
                ${cardClass}
                ${chart.selected 
                    ? 'ring-2 ring-brand-500 ring-offset-2 border-brand-500 shadow-md z-10' 
                    : `${hoverBorder} hover:shadow-lg`
                }
              `}
            >
              {/* Toolbar */}
              <div 
                className={`
                    flex items-center justify-between px-3 py-2
                    ${headerBorder} border-b h-14 shrink-0 select-none
                    ${isDark ? 'bg-slate-900' : 'bg-white'}
                    ${chart.selected ? (isDark ? 'bg-brand-900/20' : 'bg-brand-50/30') : ''}
                `}
              >
                {/* Left: Drag Handle & Info */}
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className={`cursor-grab active:cursor-grabbing p-1 ${isDark ? 'text-slate-600 hover:text-slate-400' : 'text-slate-300 hover:text-slate-500'}`}>
                        <GripVertical className="w-5 h-5" />
                    </div>
                    
                    {/* Coin Logo */}
                    <div className={`w-8 h-8 rounded-full p-0.5 shrink-0 ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
                        <img 
                            src={logoUrl} 
                            alt={coinSymbol} 
                            className="w-full h-full object-contain rounded-full"
                            onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none';
                            }}
                        />
                    </div>

                    <div className="flex flex-col leading-tight">
                        <span className={`text-xl font-black truncate max-w-[160px] tracking-tight ${textPrimary}`}>
                            {chart.symbol.split(':')[1] || chart.symbol}
                        </span>
                        <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-bold uppercase text-slate-400">
                                {chart.symbol.split(':')[0]}
                            </span>
                            <span className={`text-[10px] font-bold px-1.5 rounded ${isDark ? 'bg-slate-800 text-slate-400' : 'text-slate-600 bg-slate-100'}`}>
                                {chart.interval}
                            </span>
                            {chart.selected && (
                                <span className={`flex items-center gap-1 text-[10px] font-bold px-1.5 rounded border ${isDark ? 'text-brand-400 bg-brand-900/30 border-brand-800' : 'text-brand-600 bg-brand-50 border-brand-100'}`}>
                                    <CheckCircle2 className="w-3 h-3" /> Đã chọn
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
                    className={`p-1.5 rounded-lg transition-colors ${openSettingsId === chart.id ? 'text-brand-500 bg-brand-50' : `${isDark ? 'text-slate-500 hover:text-brand-400 hover:bg-slate-800' : 'text-slate-400 hover:text-brand-600 hover:bg-slate-100'}`}`}
                    title="Cài đặt"
                  >
                    <Settings className="w-5 h-5" />
                  </button>
                  <button 
                    onClick={(e) => initiateRemoveChart(chart.id, e)}
                    className={`p-1.5 rounded-lg transition-colors ${isDark ? 'text-slate-500 hover:text-red-400 hover:bg-red-900/20' : 'text-slate-400 hover:text-red-500 hover:bg-red-50'}`}
                    title="Xóa biểu đồ"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Settings Menu Dropdown */}
              {openSettingsId === chart.id && (
                <div 
                  className={`absolute top-14 right-2 z-30 rounded-xl shadow-xl border p-2 w-48 animate-in fade-in zoom-in-95 duration-200 ${isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-100'}`}
                  onClick={(e) => e.stopPropagation()} 
                >
                  <div className="text-[10px] font-bold text-slate-400 mb-2 px-2 uppercase tracking-wider">Giao diện</div>
                  <div className="space-y-1">
                    <button 
                      onClick={() => updateChartConfig(chart.id, { theme: chart.theme === 'Light' ? 'Dark' : 'Light' })}
                      className={`flex items-center justify-between px-2 py-2 text-xs rounded-lg transition-colors w-full text-left group ${isDark ? 'hover:bg-slate-700 text-slate-300' : 'hover:bg-slate-50 text-slate-600'}`}
                    >
                      <div className="flex items-center gap-2">
                        {chart.theme === 'Light' ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-indigo-500" />}
                        <span className="font-medium">Chủ đề</span>
                      </div>
                      
                      {/* Visual Toggle Switch */}
                      <div className={`relative w-9 h-5 transition-colors rounded-full ${chart.theme === 'Dark' ? 'bg-slate-600' : 'bg-slate-200'}`}>
                          <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow-sm transition-transform duration-200 ${chart.theme === 'Dark' ? 'translate-x-4.5 left-[1px]' : 'translate-x-0.5 left-0'}`}></div>
                      </div>
                    </button>
                  </div>

                  <div className={`h-px my-2 ${isDark ? 'bg-slate-700' : 'bg-slate-100'}`}></div>

                  <div className="text-[10px] font-bold text-slate-400 mb-2 px-2 uppercase tracking-wider">Điều khiển</div>
                  <div className="space-y-1">
                     <button 
                      onClick={() => updateChartConfig(chart.id, { hideToolbar: !chart.hideToolbar })}
                      className={`flex items-center gap-2 px-2 py-2 text-xs rounded-lg transition-colors w-full text-left ${chart.hideToolbar ? 'text-brand-600 bg-brand-50 font-medium' : `${isDark ? 'text-slate-300 hover:bg-slate-700' : 'text-slate-600 hover:bg-slate-50'}`}`}
                    >
                      {chart.hideToolbar ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      {chart.hideToolbar ? 'Hiện thanh công cụ' : 'Ẩn thanh công cụ'}
                    </button>
                  </div>
                </div>
              )}

              {/* The Widget */}
              <div className={`flex-1 w-full h-full relative ${isDark ? 'bg-slate-900' : 'bg-slate-50'}`}> 
                <TradingViewWidget 
                  symbol={chart.symbol}
                  interval={chart.interval}
                  containerId={`tv_container_${chart.id}`}
                  theme={chart.theme}
                  hideToolbar={chart.hideToolbar}
                />
              </div>
            </div>
            );
          })}
          
          {charts.length === 0 && (
             <div className={`col-span-full min-h-[400px] flex flex-col items-center justify-center border-2 border-dashed rounded-2xl ${isDark ? 'border-slate-800 bg-slate-900/50 text-slate-500' : 'border-slate-300 bg-white/50 text-slate-400'}`}>
                <Maximize2 className={`w-16 h-16 mb-4 ${isDark ? 'text-slate-700' : 'text-slate-300'}`} />
                <h3 className={`text-lg font-semibold ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>Bảng điều khiển trống</h3>
                <p className="text-sm max-w-xs text-center mt-2 opacity-70">Thêm biểu đồ để theo dõi nhiều cặp tiền cùng lúc với tính năng đồng bộ thời gian thực.</p>
                <button 
                  onClick={() => setIsAddModalOpen(true)}
                  className="mt-6 px-6 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-full font-medium shadow-lg shadow-brand-500/20 transition-all active:scale-95"
                >
                  Tạo Biểu Đồ Mới
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
        theme={globalTheme}
      />

      {/* Confirmation Modal for Delete */}
      {chartToRemove && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/20 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className={`rounded-2xl shadow-2xl border p-6 max-w-sm w-full transform transition-all scale-100 animate-in zoom-in-95 duration-200 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-100'}`}>
            <h3 className={`text-lg font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-800'}`}>Xóa Biểu Đồ?</h3>
            <p className={`mb-6 text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Bạn có chắc chắn muốn xóa biểu đồ này không?
            </p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={cancelRemoveChart}
                className={`px-4 py-2 font-medium rounded-xl transition-colors text-sm ${isDark ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                Hủy
              </button>
              <button 
                onClick={confirmRemoveChart}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-medium rounded-xl shadow-lg shadow-red-500/30 transition-all active:scale-95 text-sm"
              >
                Xóa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;