export interface Transaction {
  type: 'buy' | 'sell';
  date: string;
  order_id: string;
  price_vnd: number;
  vnd_amount: number;
  usdt_amount: number;
  counterparty: string;
  status: string;
}

export interface PortfolioSummary {
  totalBuyVnd: number;
  totalBuyUsdt: number;
  totalSellVnd: number;
  totalSellUsdt: number;
  netHoldingUsdt: number;
  netCostVnd: number;
  avgCost: number;
}