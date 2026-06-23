# CLAUDE.md · BitSignal

> 给 Claude Code 的项目上下文。开始任何编码前先读本文件，再读对应 Agent 子目录里的 `REQUIREMENTS.md`。

## 这是什么

**BitSignal** 是一个面向量化交易场景的 **Agent 网络**：监听金融/政经领域的信源，产出可付费的**交易数据与信号**，通过 **x402 协议**（USDC on Base）按次/订阅收款，并上架到 **AgentVerse** 让其他量化 Agent 自动发现和调用。

整体产品设计见 `docs/产品设计蓝图.md`。当前聚焦事件驱动情报方向（把高影响力言论/事件实时翻译成"受影响标的 + 方向 + 强度 + 置信度"信号）。

## 协作方式（重要）

- **产品设计在 Cowork 完成**，以 Markdown 需求文档形式交付，放在各 Agent 子目录的 `REQUIREMENTS.md`。
- **编码由 Claude Code 完成**：需求文档只描述"做什么"（功能 + 验收标准）。**技术选型、目录结构、接口/Schema、模块拆分、任务顺序由你（Claude Code）决定**，但必须对齐需求文档的功能与验收标准。
- 如需求有歧义或缺失，先提出来确认，不要擅自扩大范围。

## 目录约定

```
BitSignal/                  顶层项目（一个项目一个顶层目录）
├── CLAUDE.md               本文件（项目级上下文）
├── docs/
│   └── 产品设计蓝图.md      整体设计背景
└── <agent-name>/           每个 Agent 一个子目录，Claude Code 在此编码
    ├── REQUIREMENTS.md      该 Agent 的产品需求（产品设计产出，勿改）
    └── ...                  代码、测试、配置等由你创建
```

- 每个 Agent **自包含**在自己的子目录里，独立开发、独立部署，互不耦合。
- **不要修改 `REQUIREMENTS.md` 和 `docs/`** —— 那是产品设计的产出。

## 当前 Agent

- **`trumpsignal/`** —— TrumpSignal：以特朗普发帖为核心信源的事件驱动情报 Agent（MVP）。需求见 `trumpsignal/REQUIREMENTS.md`。

## 技术基线（全项目通用）

- AgentVerse 部署用 **uAgents** 框架（Python 3.10–3.13），通过 Agent Chat Protocol 接入 ASI:One。
- 支付结算用 **x402 协议**，**USDC on Base**，按次/订阅计费。
- 涉及 x402、uAgents、AgentVerse、各信源 API 时，**先查最新官方文档确认接口细节**（这些 API 变动较快，勿凭记忆）。
- 每个 Agent 要有：可观测的运行日志、信源接入的冗余/降级、合规免责声明（"非投资建议"）。

## 编码原则

- 先跑通最小可用链路（end-to-end），再扩功能。
- 对外只暴露必要接口；密钥/钱包私钥等敏感信息走环境变量或密钥管理，**绝不硬编码、绝不提交进仓库**。
- 写清楚 README 与运行说明，让单人即可本地启动验证。
