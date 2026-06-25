# BitSignal Agent 部署手册

> 从零到上架 AgentVerse 的完整步骤，含踩坑记录。适用于所有 BitSignal 子 Agent。

---

## 一、整体流程图

```
本地开发 → GitHub Push → Railway 自动部署 → AgentVerse 注册脚本 → ASI:One 可发现
```

---

## 二、本地开发准备

### 目录结构
```
BitSignal/
└── <agent-name>/
    ├── main.py              # 入口（uvicorn + scheduler + uAgent）
    ├── config.py            # Pydantic-settings，所有配置从 .env 读取
    ├── requirements.txt
    ├── Procfile             # web: python main.py
    ├── register_agent.py    # 一次性注册到 AgentVerse（本地运行）
    └── .env                 # 本地密钥，绝不提交 git
```

### .env 必填项
```env
# LLM
OPENROUTER_API_KEY=sk-or-...

# 支付（Trust Wallet Base 网络地址）
PAYMENT_RECIPIENT_ADDRESS=0x...
USE_TESTNET=true           # 测试阶段 true，上线改 false

# AgentVerse 注册
AGENTVERSE_KEY=...         # 从 agentverse.ai 注册流程页面复制
AGENT_SEED_PHRASE=...      # 自己生成的助记词，妥善保存

# 端口（Railway 会注入 PORT，本地留空即可）
GATEWAY_PORT=8080
AGENT_PORT=8001
```

> ⚠️ `.env` 加入 `.gitignore`，助记词绝不上传任何服务器。

---

## 三、Railway 部署

### 3.1 仓库连接
1. Railway → New Project → Deploy from GitHub repo
2. 选对仓库和分支

### 3.2 关键设置（踩坑最多的地方）

**Root Directory（必须设置）**
- Settings → Source → Root Directory：填 `<agent-name>`（如 `trumpsignal`）
- 不设置会导致 railpack/nixpacks 检测不到 Python 项目

**不要放 runtime.txt**
- 曾经用 `runtime.txt` 指定 `python-3.11.9`，导致 attestation 校验失败
- 直接删掉，让 Railway 自动检测 Python 版本

**Procfile**
```
web: python main.py
```

### 3.3 环境变量（Railway Variables）
在 Railway Settings → Variables 里添加（与本地 .env 一一对应）：

| 变量名 | 说明 |
|--------|------|
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `PAYMENT_RECIPIENT_ADDRESS` | 收款钱包地址（Base 网络） |
| `USE_TESTNET` | `true` 或 `false` |
| `AGENT_SEED_PHRASE` | uAgent 助记词 |
| `PUBLIC_BASE_URL` | Railway 分配的域名，如 `https://xxx.up.railway.app` |

> ⚠️ **不需要**手动设置 `PORT`——Railway 会自动注入，代码里处理好端口冲突即可（见下方端口坑）。

### 3.4 域名与端口

Railway 会注入 `PORT` 环境变量，但同时你的 uAgent 也要绑定一个端口（默认 8001）。两者可能冲突。

**解决方案（config.py）**：
```python
gateway_port: int = 8080
port: int = 0        # Railway 注入的 PORT
agent_port: int = 8001

@property
def effective_port(self) -> int:
    # 若 Railway 注入的 PORT 与 agent_port 相同，就用 gateway_port 避免冲突
    if self.port and self.port != self.agent_port:
        return self.port
    return self.gateway_port
```

Railway 域名的端口（Networking → Public Networking）设置为 **8080**（和 `gateway_port` 一致）。

---

## 四、踩坑速查

| 坑 | 原因 | 解法 |
|----|------|------|
| railpack 检测不到 Python | 仓库根目录是 monorepo，`requirements.txt` 在子目录 | Railway Settings → Root Directory 填子目录名 |
| `python@3.11.9` attestation 失败 | `runtime.txt` 指定了旧版本 | 删掉 `runtime.txt` |
| `pip: command not found` | 旧版 nixpacks 用 pip3 | 不需要手动处理，设置 Root Directory 后自动解决 |
| 502 Bad Gateway | uvicorn 监听 8080，但 Railway 域名端口指向了别的端口 | Railway Networking 页面改域名目标端口为 8080 |
| 端口冲突 8001 | Railway TCP Proxy 把 `PORT=8001` 注入，与 uAgent `agent_port=8001` 冲突 | `effective_port` 逻辑跳过冲突端口；或直接删掉 TCP Proxy |
| LLM 返回空 JSON | OpenRouter/Claude 把 JSON 包在 markdown 代码块里 | analyzer.py 里先剥掉 ` ```json ... ``` ` 再解析 |
| `FastAPI has no attribute 'add_event_handler'` | 新版 FastAPI 移除了该 API | 改用 `@asynccontextmanager lifespan` + `create_app(lifespan=lifespan)` 工厂模式 |
| `Object of type 'FieldInfo' is not JSON serializable` | uAgents `Model` 里用了 `Field(description=...)` | uAgents Model 字段用 Python 原生默认值，不加 `Field()` |
| `ModuleNotFoundError: No module named 'eth_abi'` | x402 需要 EVM 扩展 | `requirements.txt` 改为 `x402[evm]>=0.3.0` |
| White House RSS 404 | WhiteHouse.gov 改了 feed URL | 更新为 `https://www.whitehouse.gov/news/feed/` 等当前 URL |
| AgentVerse mailbox 找不到 | 旧 `mailbox=True` 方式已过时；需要先运行注册脚本 | 见下方第五节 |

---

## 五、AgentVerse 注册（新流程，2025年后）

> ⚠️ 旧的 `Inspector → Create Mailbox` 界面已不存在。新流程是一次性脚本注册。

### 5.1 在 AgentVerse 网站获取 KEY

1. 登录 [https://agentverse.ai](https://agentverse.ai)
2. 点 **"Launch an Agent"** 或 **"+ New Agent"**
3. 选 **Agent Chat Protocol**（uAgents 框架对应的协议）
4. 依次填写：名称、Endpoint URL（`https://your-railway-domain.up.railway.app`）、描述、标签等
5. 到最后 **Launch** 页面，点 **"Copy"** 复制 `AGENTVERSE_KEY`
6. 把这个 key 存入本地 `.env`：`AGENTVERSE_KEY=...`

### 5.2 本地运行注册脚本

```bash
cd <agent-name>
python register_agent.py
```

脚本调用 `uagents_core.utils.registration.register_chat_agent()`，输出：
```
successfully registered to Agentverse.
successfully set agent to active.
✅ 注册完成！
```

### 5.3 回到 AgentVerse 验证

点页面上的 **"Evaluate my Agents registration"** 按钮，通过后 Agent 正式上线，可在 ASI:One 搜索中被发现。

### 注册脚本模板（register_agent.py）

```python
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv
load_dotenv()

from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

register_chat_agent(
    "YourAgentName",
    "https://your-railway-domain.up.railway.app",
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=os.environ["AGENTVERSE_KEY"],
        agent_seed_phrase=os.environ["AGENT_SEED_PHRASE"],
    ),
)
print("✅ 注册完成！")
```

---

## 六、x402 支付配置

### 钱包
- 推荐用 **Trust Wallet** 新建专用钱包
- 网络：**Base**（mainnet 或 Sepolia testnet）
- 获取地址：App → 资产页 → 右上角"接收" → 选 Base 网络 → 复制地址（`0x...`）

### 代码配置
```python
# config.py
@property
def evm_network(self) -> str:
    return "eip155:84532" if self.use_testnet else "eip155:8453"

@property
def signal_price(self) -> str:
    return "$0.01"
```

```python
# config.py — facilitator 从环境变量读取，切环境只改 .env
facilitator_url: str = "https://x402.org/facilitator"  # 默认测试网

# gateway/app.py — 使用 config 里的 facilitator_url
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
```

| 阶段 | `USE_TESTNET` | `FACILITATOR_URL` | 网络 |
|------|--------------|-------------------|------|
| 开发/测试 | `true` | `https://x402.org/facilitator`（默认，免费） | Base Sepolia |
| 生产上线 | `false` | `https://api.cdp.coinbase.com/platform/v2/x402` | Base 主网 |

> x402.org/facilitator 是官方免费测试网 facilitator，只支持 Base Sepolia。  
> 上线时换 Coinbase CDP facilitator（需注册账号，1000 笔/月免费，之后 $0.001/笔），接口完全一致，只改配置。

### x402 付款踩坑（务必注意）

1. **反向代理 scheme**：Railway/任何在 TLS 终止代理后运行的服务，uvicorn 必须开
   `proxy_headers=True, forwarded_allow_ips="*"`。否则 ASGI scope 里 URL 是 `http://`，
   x402 签名 URL 与实际 HTTPS 不匹配，facilitator 验证失败（表现为带付款后仍返回 402）。

2. **付款 header 名是 `PAYMENT-SIGNATURE`**（x402 v2），不是 `X-PAYMENT`。
   服务端 `_extract_payment` 只读 `PAYMENT-SIGNATURE`。

3. **客户端编码用 SDK 函数**，别手写 base64：
   ```python
   from x402.http.utils import encode_payment_signature_header
   header = encode_payment_signature_header(payload)  # PAYMENT-SIGNATURE 的值
   ```
   手写 `base64(model_dump_json())` 会因 `by_alias`/`exclude_none` 不一致导致解析失败。

4. **客户端付款流程**：GET → 收 402 → 解 `payment-required` header（base64 JSON）→
   `x402Client.create_payment_payload()` 签名 → 带 `PAYMENT-SIGNATURE` 重发 → 200。
   完整可用示例见 `trumpsignal/test_payment.py`。

5. **测试钱包**：Base Sepolia 需要测试 USDC（[faucet.circle.com](https://faucet.circle.com)）。
   注意 facilitator 走 EIP-3009 `transferWithAuthorization`，是离线签名，
   **付款钱包不需要 ETH gas**（gas 由 facilitator 代付）。

### 主网上线（CDP facilitator）—— 实测通过

主网必须换生产 facilitator，CDP 需要 JWT 鉴权，比测试网多几步：

**1. 注册 Coinbase CDP，创建 Secret API Key**
- [portal.cdp.coinbase.com](https://portal.cdp.coinbase.com) → Settings → API Keys → **Secret API Keys** → Create
- 个人账号即可，不需要 Business
- 拿到 `CDP_API_KEY_ID`（UUID）和 `CDP_API_KEY_SECRET`（base64 Ed25519，88位以 `==` 结尾）

**2. 依赖加 `cdp-sdk`**，用它生成三端点 JWT：
```python
# gateway/facilitator.py 核心逻辑
from cdp.auth.utils.http import GetAuthHeadersOptions, get_auth_headers
from x402.http.facilitator_client_base import CreateHeadersAuthProvider

def create_headers():  # verify/settle/supported 各签一个 JWT
    def h(method, ep):
        return get_auth_headers(GetAuthHeadersOptions(
            api_key_id=key_id, api_key_secret=key_secret,
            request_method=method, request_host="api.cdp.coinbase.com",
            request_path=f"/platform/v2/x402/{ep}"))
    return {"verify": h("POST","verify"), "settle": h("POST","settle"),
            "supported": h("GET","supported")}

client = HTTPFacilitatorClient(FacilitatorConfig(
    url=cdp_url, auth_provider=CreateHeadersAuthProvider(create_headers)))
```

**3. Railway 改 4 个环境变量：**
| 变量 | 值 |
|------|-----|
| `USE_TESTNET` | `false` |
| `FACILITATOR_URL` | `https://api.cdp.coinbase.com/platform/v2/x402` |
| `CDP_API_KEY_ID` | UUID |
| `CDP_API_KEY_SECRET` | base64 Ed25519 |

**主网踩坑：**
- **CDP 凭证必须 `.strip()`**：Railway 粘贴常带入尾部换行/空格，key_id 末尾多一个换行
  CDP 就找不到 key → `get_supported failed (401)`。代码里读取后务必
  `settings.cdp_api_key_id.strip()`、`.cdp_api_key_secret.strip()`。
- **facilitator_url 也要 `.rstrip("/")`**：尾斜杠会让 client 请求 `//supported`，
  与 JWT 签名的 path 不匹配 → 401。
- **启动探测**：构造 facilitator 后立即 `client.get_supported()` 并 log，
  把真实鉴权错误暴露到日志，而不是首次付费请求时才报 500。
- 调试用 `trumpsignal/test_cdp.py`（本地验证 CDP key 是否有效）。

---

## 七、上线检查清单

- [ ] `.env` 已加入 `.gitignore`，git log 中无敏感信息
- [ ] Railway Root Directory 设置为 agent 子目录
- [ ] Railway Variables 填写完整（尤其 `AGENT_SEED_PHRASE` 和 `PUBLIC_BASE_URL`）
- [ ] 域名端口对准 8080
- [ ] `python register_agent.py` 运行成功
- [ ] AgentVerse 页面点击 Evaluate 通过
- [ ] `GET /health` 返回 200
- [ ] `GET /signals/recent` 返回 402（x402 生效）
- [ ] `GET /` 免费接口返回正常
- [ ] Railway 日志有信源轮询成功记录
