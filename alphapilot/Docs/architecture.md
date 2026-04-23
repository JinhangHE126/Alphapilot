# Alphapilot Architecture

## 1. System Overview



```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryTextColor": "#1e293b",
    "lineColor": "#475569",
    "background": "transparent"
  },
  "flowchart": {
    "htmlLabels": false,
    "curve": "basis",
    "nodeSpacing": 60,
    "rankSpacing": 80,
    "padding": 20
  }
}}%%

flowchart TB
    %% 节点定义
    A["  Input  "]
    B["  Supervisor  "]
    C["  Market  "]
    D["  Fundamental  "]
    E["  News  "]
    F["  Strategy  "]
    G["  Risk  "]
    H["  Decision  "]

    %% 层级连接
    A --> B
    
    subgraph W1["  Current Phase  "]
        C
    end

    subgraph W2["  Planned W2+  "]
        D
        E
    end

    subgraph W3["  Planned W3+  "]
        F
        G
    end

    %% 连接关系
    B --- C
    C --- B
    B --- D
    B --- E
    B --- F
    B --- G
    B --> H

    subgraph GS["  Shared Global State  "]
        S1["  symbol  "]
        S2["  mkt_data  "]
        S3["  fund_data  "]
        S4["  sentiment  "]
        S5["  strategy  "]
        S6["  risk  "]
        S7["  msgs  "]
        S8["  memory  "]
    end

    %% 状态反馈连线
    C -.-> S2
    D -.-> S3
    E -.-> S4
    F -.-> S5
    G -.-> S6
    B -.-> GS

    %% 样式美化与加粗
    linkStyle default stroke:#64748b,stroke-width:2.5px;
    linkStyle 7 stroke:#d97706,stroke-width:4px;

    classDef core fill:#1e40af,stroke:#1e3a8a,color:#ffffff,stroke-width:3px,font-weight:bold;
    classDef output fill:#fef3c7,stroke:#d97706,color:#92400e,stroke-width:3px,font-weight:bold;
    classDef current fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e,stroke-width:2.5px,font-weight:bold;
    classDef planned fill:#f0fdf4,stroke:#166534,color:#14532d,stroke-width:2px,font-weight:bold;
    
    %% 重点修改：加深了 state 的文字颜色并改为加粗
    classDef state fill:#f8fafc,stroke:#94a3b8,color:#1e293b,stroke-width:1.5px,font-weight:bold;

    class B core;
    class H output;
    class C current;
    class D,E,F,G planned;
    class S1,S2,S3,S4,S5,S6,S7,S8 state;
```



**Overview notes**

- `User Input`: 用户输入股票代码与分析需求。
- `Supervisor`: 负责路由、协调各个 agent，并聚合结果。
- `Market Data Agent`: 当前已实现，负责技术面与市场数据分析。
- `Fundamental Agent`: 计划接入，负责基本面分析与财报 RAG。
- `News & Sentiment Agent`: 计划接入，负责新闻、舆情与事件提取。
- `Strategy Agent`: 计划接入，负责综合推理与评分。
- `Risk Agent`: 计划接入，负责风险评估与止损建议。
- `Final Output`: 输出 `Buy / Hold / Sell` 及可解释报告。
- `Shared State`: 图中使用简写字段名，分别对应 `stock_symbol`、`market_data`、`fundamental_data`、`news_sentiment`、`strategy_recommendation`、`risk_assessment`、`messages`、`memory`。

## 2. Execution Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Arial, Helvetica, sans-serif",
    "fontSize": "13px",
    "primaryTextColor": "#1f2937",
    "lineColor": "#8fa1b3",
    "background": "transparent"
  },
  "flowchart": {
    "htmlLabels": false,
    "curve": "linear",
    "nodeSpacing": 70,
    "rankSpacing": 80,
    "padding": 20,
    "useMaxWidth": false
  }
}}%%
flowchart LR
    U[User Request] --> ST[START]
    ST --> SV[Supervisor]
    SV --> Q{Tech-analysis request?}
    Q -->|Yes| MK[Market Node]
    MK --> EN[END]
    Q -->|No| EN

    SV -. future .-> FD[Fundamental]
    SV -. future .-> NS[News]
    SV -. future .-> SG[Strategy]
    SV -. future .-> RK[Risk]

    linkStyle default stroke:#9fb0c2,stroke-width:2px,opacity:1;
    classDef core fill:#d7ebf7,stroke:#2f6c99,color:#1f2937,stroke-width:2.0px,font-weight:bold;
    classDef planned fill:#edf2f7,stroke:#8ea3b7,color:#334155,stroke-width:1.6px;
    classDef endpoint fill:#f1f5f9,stroke:#9aa6b2,color:#374151,stroke-width:1.4px;

    class SV,MK core;
    class FD,NS,SG,RK planned;
    class ST,EN endpoint;
```

**Execution notes**

- 当前 `workflow.py` 的真实执行路径是：`START -> Supervisor Node -> Market Node -> END`。
- `Supervisor Node` 会读取用户最后一条消息，并判断是否属于技术分析请求。
- 若命中技术分析相关关键词，则路由到 `Market Node`。
- 若未命中，则直接结束流程。
- `Fundamental / News / Strategy / Risk` 目前仍属于后续扩展节点，尚未接入实际执行链路。
