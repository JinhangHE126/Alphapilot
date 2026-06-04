**AlphaPilot 项目 FinGPT 模型 AWS SageMaker Endpoint 部署方案 —— 基于 LoRA + Inference Components 的高效部署与成本优化设计**

**文档版本**：v1.2
**编制日期**：2026年6月4日
**编制人**：何金航（Jinhang He，MSc Data Science & Artificial Intelligence @ HSUHK）
**用途**：领导评审 / 项目部署规划 / 作品集核心部分

---

### 一、背景与部署目标

**项目概述**
AlphaPilot 是一个面向香港股票市场的多智能体股权研究系统，基于 LangGraph 框架构建，核心依赖 **FinGPT**（基于 Llama-3-8B 的金融领域 LoRA 微调模型）进行投研分析、情绪判断与策略生成。目前本地开发已完成多 Agent 框架与 RAG 集成，但受限于 AWS EC2 GPU 配额（新加坡区域 G 实例 vCPU 为 0），无法直接在 EC2 上部署大模型推理。

**部署核心目标**

- 成功将 FinGPT LoRA 模型部署为高可用、低延迟的 SageMaker Real-time Endpoint，支持 streaming 与批量推理；
- 实现 Inference Components 动态加载多个 LoRA Adapter，显著降低多任务部署成本；
- 建立可复制的 MLOps 流程（模型版本管理、自动扩缩容、监控），符合香港 fintech/AI 岗位对云端 AI 工程能力的要求；
- 将月成本控制在学生/个人项目可承受范围内（通过定时开关机与 Auto Scaling 实现 50%+ 成本节省）。

---

### 二、技术选型与理由

选择 **Amazon SageMaker Real-time Endpoint + Inference Components** 架构，而非自建 EC2 或纯 Bedrock，主要原因如下：

- **配额独立**：SageMaker GPU 配额（ml.g5.*）与 EC2 G 实例配额分离，新账号更容易获得批准；
- **LoRA 原生支持**：Inference Components 可动态加载多个 LoRA Adapter，无需为每个 Adapter 单独部署 Endpoint，大幅降低成本；
- **MLOps 成熟度高**：内置模型注册、A/B 测试、自动扩缩容、Model Monitor，与 LangGraph 集成顺畅；
- **求职价值高**：香港 AI/Fintech 岗位高度认可 SageMaker + Agentic AI + RAG 的组合经验。

---

### 三、部署架构

采用 SageMaker Inference Components 架构：一个 Endpoint 承载 Base Model + 多个 LoRA Adapter，按需动态加载，极大提升资源利用率。

| 层级 | 组件 | 说明 |
| --- | --- | --- |
| 模型层 | Llama-3-8B-Instruct + FinGPT LoRA | Base 模型 + 金融领域 LoRA adapter，打包上传 S3 |
| 推理层 | SageMaker LMI Container + Inference Component | 支持高效 LoRA serving、动态 Adapter 加载、自动扩缩容 |
| 编排层 | LangGraph（后续部署于 ECS Fargate） | Supervisor + 专业 Agent，通过 langchain-aws 调用 Endpoint |
| 数据层 | S3 +（后期 OpenSearch Serverless / pgvector） | 模型文件、LoRA adapter、RAG 文档存储 |

**ECS Fargate → SageMaker 网络与权限要求（前置标注）**：

- **IAM 权限**：ECS Task Role 需附加 `sagemaker:InvokeEndpoint` 策略，对目标 Endpoint ARN 授权。
- **网络路径**：ECS Fargate 与 SageMaker Endpoint 同属 AWS 内网（非公网），延迟远低于公网调用，无需额外 VPC Endpoint。
- **认证方式**：通过 AWS SigV4 签名（`langchain-aws` 的 `ChatSageMakerEndpoint` 自动处理），无需 API Key 轮换。

```text
┌──────────────────────────────────────────────────────────┐
│                    AWS Cloud (ap-southeast-1)             │
│                                                          │
│  ┌────────────────────┐      ┌────────────────────────┐  │
│  │  ECS Fargate       │      │  SageMaker Endpoint    │  │
│  │  (LangGraph 编排)   │─────►│  ml.g5.2xlarge        │  │
│  │                    │SigV4 │                        │  │
│  │  Task Role:        │ 内网  │  LMI Container         │  │
│  │  InvokeEndpoint    │      │  ├── Base: Llama-3-8B  │  │
│  │                    │      │  ├── LoRA: FinGPT-News  │  │
│  └────────────────────┘      │  └── LoRA: FinGPT-Fund  │  │
│                              └────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  S3: alphapilot-artifacts/                       │    │
│  │  ├── models/fingpt-llama3-8b/model.tar.gz        │    │
│  │  └── adapters/{news,fundamental}/adapter.tar.gz   │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```


---

### 四、详细部署步骤（预计 3.5–4.5 天完成）

### Step 1: 模型准备与上传（0.5 天）

- 在本地或 SageMaker Studio 完成 FinGPT LoRA 训练/合并；
- 将 base_model + adapter 目录打包为 model.tar.gz；
- 上传至 S3 Bucket（建议路径：alphapilot-artifacts/models/fingpt-llama3-8b/）。

### Step 2: 创建 SageMaker Model（0.5 天）

- 推荐使用 **Amazon SageMaker LMI (Large Model Inference) Container**；
- 关键环境变量示例：

```bash
HF_MODEL_ID=s3://alphapilot-artifacts/models/fingpt-llama3-8b/model.tar.gz
SAGEMAKER_CONTAINER_LOG_LEVEL=20
ENABLE_LORA=true
```

### Step 3: 创建 Endpoint Configuration + Inference Component（核心，1–1.5 天）

- 创建 Endpoint Configuration（实例类型：ml.g5.2xlarge）；
- 创建 **Inference Component**，指定 Base Model + LoRA Adapter 路径；
- 支持动态加载多个 LoRA Adapter（例如不同风险偏好、不同市场风格的 Adapter），无需重复部署 Endpoint。

> ⚠️ **实施建议——分两步走**：
> Multi-LoRA 动态加载需 LMI Container **v0.31+**，且该功能 2024 Q4 才趋于稳定。建议先以 **单个 LoRA Adapter**（如 FinGPT-Sentiment for News Agent）验证全链路通顺，确认 Endpoint InService + 调用正常后，再扩展第二个 Adapter（FinGPT-FinMA for Fundamental Agent）。避免同时调试多个变量导致排障困难。

### Step 4: 配置 Auto Scaling 与成本控制（0.5 天）

- 启用 Target Tracking Scaling（基于 InvocationsPerInstance）；
- 配置 **Scheduled Scaling**：
  - **工作日 8:50** 自动 scale-out（提前 10 分钟预热，避免冷启动）；
  - **非工作时间 / 周末** scale-in to 0；
- 在 AWS Budgets 设置每月预算告警（建议初始 150 USD）。

> ⚠️ **冷启动延迟警告**：SageMaker Endpoint 从 0 → InService 的冷启动约需 **5-10 分钟**（加载 8B 模型 + LoRA adapter 到 GPU）。项目设计阶段应接受冷启动，关键 Demo 日可保持 `min_instance=1` 热备（当日额外 ~$42，仅当天启用）。建议 Scheduled Scaling 的 scale-out 时间设为使用时间前 10 分钟（如 8:50），确保 9:00 就绪。

**开发阶段本地推理方案**：
在 Endpoint 不可用时（非工作时间 / 配额审批中），使用本地推理作为降级方案：
- 通过 **Ollama** 或 **llama.cpp** 在 Mac 上运行 4-bit 量化的 Llama-3-8B + FinGPT LoRA merged model；
- `llm.py` 中通过环境变量 `FINGPT_LOCAL_FALLBACK=true` 切换 `base_url` 指向 `http://localhost:11434/v1`；
- 本地推理仅用于开发和调试，Demo / 正式评估启用 SageMaker Endpoint。

### Step 5: 集成测试与 LangGraph 对接（1 天）

#### 5.1 调用链路总览



```
LangGraph Agent (ECS Fargate / 本地)
│
│  get_llm("news")  或  get_llm("fundamental")
│
▼
config/llm.py  ── provider: "sagemaker"
│
│  boto3 invoke_endpoint (AWS SigV4 签名)
│
▼
SageMaker Endpoint (ml.g5.2xlarge)
├── LMI Container
├── Llama-3-8B Base Model
└── FinGPT LoRA Adapter
```



#### 5.2 `llm.py` 接入设计——新增 `sagemaker` provider

现有 `get_llm()` 已支持 `gemini` 和 `openai_compatible` 两种 provider。新增 `sagemaker` provider，仅在 `get_llm()` 中添加一个 `elif` 分支，不对现有代码做任何破坏性修改。

**LLM_PROFILES 新增配置项**：

```python
# config/llm.py —— LLM_PROFILES 新增
"fingpt_sagemaker": {
    "provider": "sagemaker",
    "endpoint_name": os.getenv("FINGPT_SAGEMAKER_ENDPOINT", "fingpt-llama3-8b-endpoint"),
    "region": os.getenv("AWS_REGION", "ap-southeast-1"),
    "model": "fingpt-llama3-8b-lora",
},
```

**get_llm() 新增分支**：

```python
# config/llm.py —— get_llm() 中新增 elif
if provider == "sagemaker":
    from langchain_aws import ChatSageMakerEndpoint

    return ChatSageMakerEndpoint(
        endpoint_name=profile["endpoint_name"],
        region_name=profile.get("region", "ap-southeast-1"),
        model=profile.get("model", "default"),
        temperature=route["temperature"],
        max_retries=route["max_retries"],
        content_handler=FinancialContentHandler(),  # 自定义序列化
    )
```

**AGENT_LLM_ROUTES 切换示例**（通过环境变量一键切换）：

```python
# Agent 路由中，news 和 fundamental 支持 sagemaker 切换
"news": {
    "profile": os.getenv("FINGPT_NEWS_BACKEND", "deepseek_fast"),  # 默认 deepseek_fast
    # 测试时设置: export FINGPT_NEWS_BACKEND=fingpt_sagemaker
    "temperature": 0.1,
    "max_retries": 5,
    "timeout": 60,
},
```

#### 5.3 依赖清单

requirements.txt 新增
    langchain-aws>=0.2.0
    boto3>=1.34.0


#### 5.4 测试验收项

- [ ] `get_llm("news")` 在 `FINGPT_NEWS_BACKEND=fingpt_sagemaker` 时返回 `ChatSageMakerEndpoint` 实例
- [ ] 非 streaming 调用：单次 invoke 返回完整结果
- [ ] streaming 调用：`model.astream()` 逐 token 返回（LangGraph `astream_events` 兼容）
- [ ] 降级测试：`FINGPT_NEWS_BACKEND=deepseek_fast` 一键回退到 DeepSeek API
- [ ] RAG 增强流程：News Agent 调用 FinGPT Endpoint 进行分析，结果注入 Evidence Packet

**本阶段交付物**：

- 可稳定调用的 SageMaker Endpoint
- `config/llm.py` 中 `sagemaker` provider 完整实现
- 环境变量切换示例与测试报告
- 性能基准与成本优化报告

---

### 五、成本估算（FinGPT Endpoint 阶段）

**ml.g5.2xlarge** 在新加坡区域 On-Demand 约 **$1.75–1.90 / 小时**。

采用 **定时开关机 + Auto Scaling** 策略后：

- **低使用量场景**（每天 4–6 小时）：**80–150 USD / 月**
- **中度使用场景**（每天 8 小时+）：**180–280 USD / 月**

**必须实施的成本优化措施**：

- 使用 Lambda + EventBridge 实现工作日自动开启 Endpoint，非工作时间自动 scale to 0；
- Endpoint 最小实例数设为 0 或 1；
- **开发阶段**：优先使用 **本地推理**（Ollama / llama.cpp，Mac 上跑 4-bit 量化版），关键 demo / 联调时再启动 SageMaker Endpoint；
- 在 AWS Budgets 设置 150 USD 月预算 + 80%/100% 告警。

---

### 六、风险与应对

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| SageMaker GPU 配额申请被拒或延迟 | 高 | 同步申请 g5.xlarge；准备本地推理降级方案（Ollama + 4-bit 量化 Llama-3-8B）；向支持案例补充详细教育用途说明 |
| Endpoint 冷启动延迟（5-10 分钟） | 中 | Scheduled Scaling 提前 10 分钟预热（8:50 scale-out）；非实时场景接受冷启动；Demo 日保持 min_instance=1 |
| 月成本超出预期 | 中 | 严格实施定时开关机 + 预算告警 + 开发阶段用本地推理 |
| 多 Agent 协作稳定性 | 中 | 增加 Supervisor 重试机制、状态持久化（DynamoDB）、超时控制 |
| `langchain-aws` 与 SageMaker Endpoint 兼容性 | 中 | Step 5 优先验证 `ChatSageMakerEndpoint` 的 streaming 兼容性；若不稳定，降级为自封装 `boto3.invoke_endpoint` Adapter |

---

### 七、实施时间线（FinGPT 部署阶段）

| 阶段 | 天数 | 关键交付物 |
| --- | --- | --- |
| 模型准备 + S3 上传 | 0.5 天 | model.tar.gz 已上传 |
| SageMaker Model 创建 | 0.5 天 | Model 注册成功 |
| Endpoint + Inference Component | 1–1.5 天 | **先单 Adapter** Endpoint InService，验证通过后再加第二个 |
| Auto Scaling + 成本配置 | 0.5 天 | 定时开关机（8:50 预热）+ 告警生效 |
| LangGraph 集成测试 | 1 天 | Agent 通过 `sagemaker` provider 成功调用 Endpoint + RAG 增强 |
| **合计** | **3.5–4.5 天** | 可稳定运行的 FinGPT SageMaker Endpoint |