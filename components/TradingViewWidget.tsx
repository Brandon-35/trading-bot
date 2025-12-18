import React, { useEffect, useRef, useState } from 'react';
import { TradingViewWidgetProps } from '../types';

const TradingViewWidget: React.FC<TradingViewWidgetProps> = ({
  symbol,
  interval,
  containerId,
  theme = 'Light',
  hideToolbar = false,
  autosize = true,
}) => {
  const [isScriptLoaded, setIsScriptLoaded] = useState(false);
  const widgetRef = useRef<HTMLDivElement>(null);

  // Load the TradingView script once
  useEffect(() => {
    if (document.getElementById('tradingview-widget-loading-script')) {
      setIsScriptLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.id = 'tradingview-widget-loading-script';
    script.src = 'https://s3.tradingview.com/tv.js';
    script.type = 'text/javascript';
    script.onload = () => {
      setIsScriptLoaded(true);
    };
    document.head.appendChild(script);
  }, []);

  // Initialize or Update the Widget
  useEffect(() => {
    if (!isScriptLoaded || !window.TradingView) return;

    // Use a timeout to ensure the DOM element is ready and to prevent rapid re-renders
    const timer = setTimeout(() => {
        // We clean the container first to ensure a fresh mount when props change
        if (widgetRef.current) {
            widgetRef.current.innerHTML = '';
        }
        
        // Ensure the container div exists with the correct ID
        // The library looks for an element with the `container_id`
        
        new window.TradingView.widget({
            autosize: autosize,
            symbol: symbol,
            interval: interval,
            timezone: "Etc/UTC",
            theme: theme,
            style: "1",
            locale: "en",
            toolbar_bg: "#f1f3f6",
            enable_publishing: false,
            allow_symbol_change: true, // Allow local change, but global sync will overwrite on next global action
            container_id: containerId,
            hide_side_toolbar: hideToolbar,
            studies: [
                "MASimple@tv-basicstudies",
                "RSI@tv-basicstudies"
            ]
        });
    }, 100);

    return () => clearTimeout(timer);

  }, [isScriptLoaded, symbol, interval, theme, hideToolbar, containerId, autosize]);

  return (
    <div className="w-full h-full relative bg-white rounded-lg overflow-hidden">
      <div 
        id={containerId} 
        ref={widgetRef}
        className="w-full h-full"
      />
      {!isScriptLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div>
        </div>
      )}
    </div>
  );
};

export default TradingViewWidget;