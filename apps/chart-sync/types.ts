export interface ChartConfig {
  id: string;
  symbol: string;
  interval: string;
  timezone: string;
  theme: 'Light' | 'Dark';
  hideToolbar?: boolean;
  selected?: boolean;
}

export interface TradingViewWidgetProps {
  symbol: string;
  interval: string;
  containerId: string;
  theme?: 'Light' | 'Dark';
  hideToolbar?: boolean;
  autosize?: boolean;
}

// Extend Window interface to include TradingView
declare global {
  interface Window {
    TradingView: any;
  }
}