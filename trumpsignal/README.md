# TrumpSignal

事件驱动情报 Agent — 监听特朗普、白宫、美联储，产出机器可读的交易影响信号。  
通过 **x402 协议**（USDC on Base）按次付费，上架 **AgentVerse** 供量化 Agent 自动调用。

> **免责声明**：本 Agent 产出的信号仅供信息参考，不构成任何投资建议。

---

## 快速开始

### 1. 安装依赖

```bash
cd trumpsignal
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填写以下必填项：

| 变量 | 说明 |
|------|------|
| `OPENROUTER_API_KEY` | OpenRouter API Key（必填） |
| `PAYMENT_RECIPIENT_ADDRESS` | Trust Wallet 在 Base 网络上的收款地址（必填） |
| `USE_TESTNET` | `true` = Base Sepolia 测试网（开发阶段），`false` = 主网 |
| `TWITTERAPI_IO_KEY` | Twitterapi.io Key（可选，不填则只用 Truth Social RSS）|
| `AGENT_SEED_PHRASE` | uAgent 种子短语（随机填写，保持固定不变）|
| `AGENTVERSE_API_KEY` | AgentVerse API Key（上架时填写） |

### 3. 启动

```bash
cd trumpsignal
python main.py
```

服务启动后：
- **HTTP 网关**：`http://localhost:8000`
- **API 文档**：`http://localhost:8000/docs`
- **公开事件日志**：`http://localhost:8000/log`（无需付费）

---

## API 接口

### 公开接口（无需付费）

```
GET /             # 服务信息
GET /health       # 健康检查
GET /log          # 最近 7 天事件日志（摘要版）
```

### 付费接口（$0.01 USDC / 次，x402 Base）

#### 查询最近信号
```
GET /signals/recent?hours=1&source=trump&asset=BTC&limit=10
```

参数说明：
- `hours`：最近 N 小时（1–24，默认 1）
- `source`：`trump` / `whitehouse` / `fed`（可选）
- `asset`：`BTC` / `USD` / `auto_sector` / `energy_sector` 等（可选）
- `event_type`：`tariff_threat` / `monetary_policy` / `sanctions` 等（可选）
- `limit`：最多返回条数（1–100，默认 20）

#### 按 ID 查询单条信号
```
GET /signals/{event_id}
```

### 信号结构

```json
{
  "event_id": "a3f1b2c4d5e6f708",
  "detected_at": "2026-06-18T14:32:01Z",
  "source": "Truth Social",
  "actor": "Donald Trump",
  "event_type": "tariff_threat",
  "summary": "Trump threatens 50% tariff on EU automotive imports",
  "entities": ["auto sector", "EU", "USD"],
  "impacts": [
    {
      "symbol": "auto_sector",
      "market": "US equities",
      "direction": "bearish",
      "magnitude": "high",
      "confidence": 0.85
    },
    {
      "symbol": "USD",
      "market": "FX",
      "direction": "bullish",
      "magnitude": "medium",
      "confidence": 0.70
    }
  ],
  "sentiment": "aggressive",
  "novelty": "high",
  "urgency": "immediate",
  "expected_time_to_impact": "<3min",
  "rationale": "Tariff threats on EU autos historically correlate with bearish auto sector moves and USD strengthening.",
  "disclaimer": "This signal is for informational purposes only and does not constitute investment advice."
}
```

---

## Webhook 订阅（Push）

```bash
# 订阅特朗普频道
curl -X POST http://localhost:8000/subscriptions \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://your-agent.example.com/webhook", "channel": "trump"}'

# 频道选项：trump / whitehouse / fed / all

# 取消订阅
curl -X DELETE http://localhost:8000/subscriptions/{subscription_id}
```

事件触发时，服务端会向你的 `webhook_url` POST 完整信号 JSON。

---

## x402 支付说明

本服务使用 [x402 协议](https://x402.org)，调用方步骤：

1. 请求 `/signals/recent` → 服务器返回 HTTP 402 + 支付要求
2. 调用方用 USDC 在 Base 链完成支付
3. 携带支付证明重新请求 → 服务器验证后返回信号数据

**测试网**：设 `USE_TESTNET=true`，使用 Base Sepolia 测试网 USDC（无需真实资金）。  
**主网**：设 `USE_TESTNET=false`，收款地址为你的 Trust Wallet Base 地址。

---

## AgentVerse 上架

1. 启动服务并确认 `PUBLIC_BASE_URL` 已设置为公网地址
2. 登录 [AgentVerse](https://agentverse.ai)，创建新 Agent，填入：
   - Agent 地址（启动时控制台打印）
   - 关键词：`event signals`、`political catalyst`、`Fed alerts`、`Trump signal`、`macro event`
3. 其他量化 Agent 可通过 ASI:One 搜索并调用 `TrumpSignalProtocol`

---

## 目录结构

```
trumpsignal/
├── main.py              # 启动入口
├── config.py            # 配置（环境变量）
├── sources/             # L1 信源采集
│   ├── truth_social.py  # Trump Truth Social RSS
│   ├── twitter.py       # Trump X（Twitterapi.io）
│   ├── whitehouse.py    # 白宫 RSS
│   └── fed.py           # 美联储 RSS
├── pipeline/            # L2 分析流水线
│   ├── dedup.py         # 去重
│   ├── analyzer.py      # LLM 事件分析（OpenRouter）
│   ├── signal_store.py  # 信号存储
│   └── processor.py     # 端到端处理协调
├── gateway/             # L3 HTTP 网关
│   ├── app.py           # FastAPI + x402 中间件
│   ├── routes_pull.py   # Pull 查询接口
│   └── webhook.py       # Push 订阅管理
├── agent/
│   └── uagent.py        # uAgent（AgentVerse 注册）
├── logs/                # 信号日志（signals.ndjson）
├── requirements.txt
└── .env.example
```

---

## 本地测试

```bash
# 查看公开日志（不需要付费）
curl http://localhost:8000/log

# 测试 x402 支付流程（需要配置好 Base Sepolia 测试网）
# 建议使用 coinbase/x402 提供的 Python 客户端示例
# https://github.com/coinbase/x402/tree/main/examples/python/clients
```
