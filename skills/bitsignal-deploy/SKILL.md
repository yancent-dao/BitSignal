---
name: bitsignal-deploy
description: >
  Guides deployment of BitSignal Agents — FastAPI + uAgents services that use x402 payments and register on AgentVerse/ASI:One.
  Use this skill whenever the user is deploying a new BitSignal agent, setting up Railway for a uAgents project,
  registering an agent on AgentVerse, configuring x402 USDC payments, or testing agent-to-agent calls.
---

# BitSignal Agent 部署 Skill

整个流程三个阶段，按顺序完成：

**阶段一：Railway 部署 → 阶段二：AgentVerse 注册 → 阶段三：验证上线（含 x402 付费）**

先确认用户在哪个阶段，再针对性指导。

---

## 阶段一：Railway 部署

### 项目文件

每个 Agent 子目录需有：

```
<agent-name>/
├── main.py          # uvicorn + APScheduler + uAgent 入口
├── config.py        # Pydantic-settings，所有密钥从环境变量读取
├── requirements.txt # 包含 x402[evm]>=0.3.0
└── Procfile         # 内容：web: python main.py
```

### Railway 项目创建

1. New Project → Deploy from GitHub → 选仓库和分支
2. **Settings → Source → Root Directory**：填 `<agent-name>`（如 `trumpsignal`）
3. **Settings → Networking → 域名目标端口**：设为 `8080`

### 端口配置（config.py）

Railway 会注入 `PORT` 环境变量，可能与 uAgent 端口冲突，用以下逻辑规避：

```python
gateway_port: int = 8080
port: int = 0        # Railway 注入
agent_port: int = 8001

@property
def effective_port(self) -> int:
    if self.port and self.port != self.agent_port:
        return self.port
    return self.gateway_port
```

### 反向代理 scheme（x402 必需！）

Railway 在外层终止 TLS，uvicorn 必须开启 proxy_headers，否则请求 URL 在 ASGI scope 里是
`http://`，导致 x402 付款签名 URL 不匹配、facilitator 验证失败：

```python
uvicorn.run(app, host="0.0.0.0", port=settings.effective_port,
            proxy_headers=True, forwarded_allow_ips="*")
```

### Railway 环境变量

| 变量名 | 说明 |
|--------|------|
| `OPENROUTER_API_KEY` | LLM API key |
| `PAYMENT_RECIPIENT_ADDRESS` | Trust Wallet Base 地址（`0x...`） |
| `USE_TESTNET` | 测试 `true`，上线 `false` |
| `FACILITATOR_URL` | 测试默认 x402.org，上线换 CDP（见阶段三） |
| `AGENT_SEED_PHRASE` | uAgent 助记词 |
| `PUBLIC_BASE_URL` | Railway 域名，如 `https://xxx.up.railway.app` |

部署验证：`GET /health`→200；`GET /signals/recent`→402。

---

## 阶段二：AgentVerse 注册

> ⚠️ 旧的 `mailbox=True` + Inspector 流程已废弃。现在用一次性脚本注册，
> 且把端点设为 `PUBLIC_BASE_URL/submit`（不要用 mailbox），消息直达 Railway。

### uAgent 端点配置

```python
agent = Agent(
    name="YourAgent",
    port=settings.agent_port,
    seed=settings.agent_seed_phrase,
    endpoint=[f"{settings.public_base_url}/submit"],  # 直连，不用 mailbox
)
```

### FastAPI 加 ACP 代理路由

uAgent 的 `/submit` 只监听本地 8001，需要 FastAPI(8080) 转发，并**转发全部 header**
（`x-uagents-connection: sync` 必须保留，否则同步查询拿不到响应）：

```python
@app.api_route("/submit", methods=["POST", "HEAD"])
async def acp_submit(request: Request):
    body = await request.body()
    fwd = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    async with httpx.AsyncClient() as c:
        r = await c.request(request.method, f"http://127.0.0.1:{AGENT_PORT}/submit",
                            content=body, headers=fwd, timeout=30)
    return Response(r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))

@app.get("/agent_info")
async def acp_agent_info():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{AGENT_PORT}/agent_info", timeout=5)
    return Response(r.content, status_code=r.status_code, media_type="application/json")
```

### 注册步骤

1. agentverse.ai → **Launch an Agent** → 选 **Agent Chat Protocol** → 填名称/Endpoint URL/描述 → 到 Launch 页点 **Copy** 复制 `AGENTVERSE_KEY`，存入 `.env`
2. 本地运行 `register_agent.py`：

```python
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv; load_dotenv()
from uagents_core.utils.registration import register_chat_agent, RegistrationRequestCredentials

register_chat_agent(
    "YourAgentName",
    "https://your-railway-domain.up.railway.app",
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=os.environ["AGENTVERSE_KEY"],
        agent_seed_phrase=os.environ["AGENT_SEED_PHRASE"],
    ),
)
```

3. 回网站点 **Evaluate my Agents registration** 验证。

---

## 阶段三：验证上线

### Agent-to-Agent 调用测试

写一个测试 client agent，用 `send_sync_message` 一次性查询（无需注册）：

```python
from uagents.communication import send_sync_message
result = await send_sync_message(
    destination="agent1q...",      # 目标 Agent 地址
    message=SignalQueryRequest(hours=1, asset="BTC"),
    response_type=SignalQueryResponse,
    timeout=30,
)
```

### x402 付费配置与测试

```python
# config.py — facilitator 从环境变量读取
facilitator_url: str = "https://x402.org/facilitator"  # 默认测试网

@property
def evm_network(self) -> str:
    return "eip155:84532" if self.use_testnet else "eip155:8453"
```

| 阶段 | `USE_TESTNET` | `FACILITATOR_URL` | 网络 |
|------|--------------|-------------------|------|
| 开发/测试 | `true` | `https://x402.org/facilitator`（免费） | Base Sepolia |
| 生产上线 | `false` | `https://api.cdp.coinbase.com/platform/v2/x402` | Base 主网 |

> x402.org facilitator 故意只支持测试网。上线换 Coinbase CDP（1000笔/月免费，
> 之后 $0.001/笔），或 x402.rs / OpenX402。接口一致，只改两个环境变量。

**付费客户端流程（关键细节，照做避免踩坑）：**

1. GET 请求 → 收 402，从 `payment-required` header（base64 JSON）解出金额/收款/网络
2. 客户端网络必须与服务端 `evm_network` 一致（测试网 `eip155:84532`）
3. 用 `x402Client.create_payment_payload()` 签名（钱包私钥）
4. **付款 header 名是 `PAYMENT-SIGNATURE`**（x402 v2），不是 `X-PAYMENT`
5. **用 SDK 编码，别手写 base64**：
   ```python
   from x402.http.utils import encode_payment_signature_header
   header_value = encode_payment_signature_header(payload)
   r = await http.get(url, headers={"PAYMENT-SIGNATURE": header_value})
   ```
6. 测试钱包：Base Sepolia USDC 从 faucet.circle.com 领。EIP-3009 离线签名，
   **gas 由 facilitator 代付，测试钱包不需要 ETH**。

完整可用示例参考 `trumpsignal/test_payment.py`。

---

## 上线检查清单

- [ ] `.env` 在 `.gitignore` 中，git 历史无敏感信息
- [ ] Railway Root Directory 设为 agent 子目录名
- [ ] uvicorn 开 `proxy_headers=True`（x402 必需）
- [ ] Railway Variables 全部填写（`AGENT_SEED_PHRASE`、`PUBLIC_BASE_URL`、`FACILITATOR_URL`）
- [ ] 域名目标端口 = 8080
- [ ] FastAPI `/submit` 和 `/agent_info` 代理路由就位，转发全部 header
- [ ] `register_agent.py` 注册成功，AgentVerse Evaluate 通过
- [ ] Agent-to-Agent `send_sync_message` 测试返回数据
- [ ] x402 付费测试：402 → PAYMENT-SIGNATURE → 200 全流程通过
- [ ] `GET /health` → 200
