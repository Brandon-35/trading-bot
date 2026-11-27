---
section: design
updated: 2026-11-27
verified_commit: 1728129
---

## Tokens
| Token | Value | Use |
|---|---|---|
| bg | #0b1220 | nền dashboard |
| panel | #111a2e | thẻ KPI |
| accent | #3b82f6 | đường vốn |
| muted | #94a3b8 | chữ phụ |

## Type
- system-ui 14px, KPI 20px.

## Components
| Component | States | Notes |
|---|---|---|
| KPI card | normal | vốn, trạng thái, số lệnh, PnL, drawdown, chi phí LLM |
| Equity sparkline | empty, data | SVG inline, 500 điểm gần nhất |
| Table | empty, data | lệnh, vị thế, 30 quyết định LLM |

## Pages
| Id | Page | File or path | Notes |
|---|---|---|---|
| P1 | Dashboard | bot/trader/dashboard.py | / , tự làm mới 60 s, CSP chặt |
