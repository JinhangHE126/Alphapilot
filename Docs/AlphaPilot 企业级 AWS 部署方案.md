# AlphaPilot 企业级 AWS 部署方案

**项目名称**：AlphaPilot 多智能体金融投研系统  
**方案版本**：v1.0  
**编制日期**：2026年6月4日  
**适用阶段**：MVP 云端部署、作品集展示、后续企业级生产演进  

---

## 一、执行摘要

AlphaPilot 当前已经具备基于 AWS EC2 GPU 实例部署大模型推理服务的基础条件，现有方案以 `g4dn.2xlarge + vLLM + Qwen2.5-7B-Instruct + FastAPI + LangGraph + RAG` 为核心，适合快速跑通 MVP。

从企业级部署角度看，当前单机方案仍需要补齐以下能力：

- 网络隔离与安全边界
- HTTPS 与统一公网入口
- 密钥与权限治理
- 日志、监控、审计与告警
- 自动化部署与基础设施即代码
- 数据备份与灾难恢复
- 成本控制与资源生命周期管理
- 后续向托管推理服务和多环境架构演进的路径

本方案建议采用“分阶段企业级演进”路线：先加固现有 EC2 MVP，再逐步拆分应用层、推理层、数据层和运维治理层，最终形成可生产化、可审计、可扩展的 AWS 云端架构。

---

## 二、当前部署基础

根据现有项目文档，当前 AWS 部署基础如下：

| 项目 | 当前配置 |
|---|---|
| 区域 | Asia Pacific Singapore `ap-southeast-1` |
| GPU 实例 | `g4dn.2xlarge` |
| GPU | NVIDIA T4 16GB |
| CPU/内存 | 8 vCPU / 32GB RAM |
| 存储 | 120GB EBS gp3 |
| 模型方案 | `Qwen/Qwen2.5-7B-Instruct` |
| 推理服务 | vLLM OpenAI-compatible API |
| 应用服务 | FastAPI + LangGraph |
| RAG | 本地向量库 / 后续可迁移至托管向量数据库 |
| 成本策略 | 定时开关机、后续申请 Spot 配额 |

当前方案适合 MVP 和作品集展示，但如果要达到企业级标准，需要避免将模型服务、Jupyter、SSH 等端口直接暴露到公网，并补齐监控、审计、备份、CI/CD 与安全治理。

---

## 三、企业级部署目标

企业级部署不只是“能跑起来”，而是需要满足以下目标：

1. **安全可控**
   - 所有公网流量统一通过 HTTPS 入口。
   - 模型推理服务不直接暴露公网。
   - 使用 IAM Role、Secrets Manager 和 KMS 管理权限与密钥。

2. **稳定可靠**
   - 应用服务与推理服务解耦。
   - 日志、指标、告警完整接入 CloudWatch。
   - 关键数据具备备份和恢复能力。

3. **可扩展**
   - 应用层支持容器化和水平扩展。
   - 推理层可从 GPU EC2 平滑迁移到 SageMaker Endpoint。
   - RAG 数据层可从本地向量库迁移到托管向量检索服务。

4. **可运维**
   - 部署流程自动化。
   - 基础设施可通过 Terraform 或 AWS CDK 重建。
   - 具备成本告警、资源标签和预算控制。

5. **可展示**
   - 架构清晰，适合写入简历、作品集和面试讲解。
   - 能体现 LLMOps、云原生、RAG、多 Agent 和成本治理能力。

---

## 四、推荐总体架构

### 4.1 架构分层

| 架构层 | 推荐 AWS 服务 | 职责 |
|---|---|---|
| DNS 与入口层 | Route 53、CloudFront、ACM、AWS WAF | 域名解析、HTTPS、CDN、安全过滤 |
| 负载均衡层 | Application Load Balancer | 对外暴露统一 API 入口 |
| 网络层 | VPC、Public Subnet、Private Subnet、NAT Gateway、Security Group、VPC Endpoint | 网络隔离与私有访问 |
| 应用层 | ECS Fargate 或 EC2 Auto Scaling | 运行 FastAPI、LangGraph、多 Agent 编排服务 |
| 推理层 | 短期 GPU EC2 + vLLM，长期 SageMaker Endpoint | 运行 Qwen2.5、FinGPT 或其他金融模型 |
| 数据层 | S3、EBS/EFS、OpenSearch Serverless、Aurora PostgreSQL pgvector | 文档、向量索引、RAG 数据、业务数据 |
| 密钥与权限层 | IAM、Secrets Manager、KMS、SSM Parameter Store | 权限控制、密钥管理、配置管理 |
| 可观测性层 | CloudWatch、X-Ray、CloudTrail | 日志、指标、链路追踪、审计 |
| 安全治理层 | GuardDuty、AWS Config、Security Hub | 威胁检测、配置合规、安全态势 |
| 成本治理层 | AWS Budgets、Cost Explorer、Resource Tags | 预算告警、成本分析、资源归因 |
| CI/CD 层 | GitHub Actions、ECR、CodeDeploy、Terraform/CDK | 镜像构建、自动部署、基础设施管理 |

### 4.2 目标访问路径

推荐公网访问路径：

```text
User
  -> Route 53
  -> CloudFront / AWS WAF
  -> Application Load Balancer HTTPS 443
  -> FastAPI / LangGraph Service
  -> Private vLLM Endpoint
  -> RAG Data Layer
```

关键原则：

- 公网只开放 `443`。
- `vLLM` 的 `8000` 端口不对公网开放。
- `FastAPI` 可以对外提供业务 API，但必须经过 ALB、HTTPS 和 WAF。
- 运维访问优先使用 SSM Session Manager，而不是长期开放 SSH。

---

## 五、分阶段实施路线

### Phase 1：加固当前 EC2 MVP

**目标**：在不推倒现有部署的前提下，把当前单机环境升级为可安全展示的生产风格 MVP。

预计耗时：1-3 天

主要任务：

1. 关闭不必要公网端口
   - 关闭公网 `8000`、`8888`。
   - `vLLM` 仅允许本机或私网访问。
   - SSH 限制为个人 IP，后续迁移到 SSM。

2. 配置 HTTPS 入口
   - 使用 ACM 申请证书。
   - 使用 ALB 对外暴露 `443`。
   - ALB 转发到 FastAPI 服务。

3. 增加基础安全控制
   - 使用 IAM Role 绑定 EC2。
   - 不在服务器上保存长期 AWS Access Key。
   - API Key、数据库密码、Hugging Face Token 放入 Secrets Manager。

4. 接入监控与日志
   - 安装 CloudWatch Agent。
   - 收集 FastAPI 日志、vLLM 日志、系统资源指标。
   - 配置 CPU、内存、磁盘、GPU 使用率告警。

5. 成本控制
   - 设置 AWS Budgets 月度预算。
   - 配置 EventBridge + Lambda 定时开关机。
   - 为所有资源打成本标签。

6. 备份恢复
   - 配置 EBS Snapshot。
   - 关键模型与 RAG 文档同步到 S3。
   - 开启 S3 Versioning。

推荐完成标准：

- 用户只能通过 HTTPS 访问 API。
- 模型端口不暴露公网。
- 日志和告警可在 CloudWatch 查看。
- AWS 预算超限会触发邮件告警。
- EC2 停止或重启后服务可恢复。

---

### Phase 2：应用层容器化

**目标**：将 FastAPI、LangGraph 和多 Agent 编排从 GPU EC2 中拆出，形成独立应用层。

预计耗时：3-7 天

推荐架构：

```text
ALB
  -> ECS Fargate Service
      -> FastAPI
      -> LangGraph Supervisor
      -> Research / Market / Risk / Report Agents
      -> Private vLLM Service
```

主要任务：

1. 编写 Dockerfile
   - 将 FastAPI 应用容器化。
   - 将 LangGraph Agent 依赖纳入镜像。

2. 建立 ECR 镜像仓库
   - GitHub Actions 构建镜像。
   - 镜像推送到 ECR。

3. 使用 ECS Fargate 运行应用服务
   - Service 放入 Private Subnet。
   - 通过 ALB Target Group 对外提供服务。

4. 让应用层调用私有推理服务
   - 应用层通过私网访问 vLLM。
   - 后续可将 vLLM 替换为 SageMaker Endpoint，应用层不用大改。

收益：

- 应用部署不再依赖 GPU 实例。
- GPU 实例可以专注模型推理。
- FastAPI 可独立扩容、重启和发布。
- 更符合企业微服务部署模式。

---

### Phase 3：企业级 RAG 数据层

**目标**：将本地 RAG 数据迁移到更可靠、可扩展、可备份的数据层。

预计耗时：1-2 周

推荐选项：

| 方案 | 适用场景 | 优点 | 注意事项 |
|---|---|---|---|
| S3 + FAISS 文件 | MVP、低成本展示 | 简单便宜，迁移成本低 | 并发和检索治理较弱 |
| OpenSearch Serverless Vector Engine | 企业检索、规模化 RAG | 托管服务，适合搜索和向量检索 | 成本高于本地方案 |
| Aurora PostgreSQL + pgvector | 结构化数据 + 向量检索 | SQL 能力强，适合业务数据结合 | 需要数据库运维经验 |

推荐路径：

1. 短期继续使用本地 Chroma/FAISS。
2. 将原始文档统一存入 S3。
3. 为每批文档和 embedding 建立版本号。
4. 中期迁移到 OpenSearch Serverless 或 Aurora pgvector。
5. 建立 RAG 评测集，监控回答准确率和引用质量。

企业级要求：

- 文档入库流程可重复执行。
- Embedding 模型和参数需要版本化。
- 检索结果需要保留引用来源。
- 对金融数据、用户数据和私有文档启用加密。

---

### Phase 4：推理层升级到 SageMaker

**目标**：将模型推理从自管 GPU EC2 迁移到托管推理平台，提升运维能力。

预计耗时：2-4 周

适合迁移的条件：

- 项目需要长期对外服务。
- 访问量开始不稳定或增长。
- 需要模型版本管理、灰度发布、自动扩缩容。
- 需要更标准的 MLOps 展示能力。

推荐架构：

```text
FastAPI / LangGraph
  -> SageMaker Runtime
  -> SageMaker Endpoint
  -> Model Artifact in S3
  -> CloudWatch Metrics / Logs
```

迁移收益：

- 模型部署、监控和伸缩更标准。
- 可以保留多个模型版本。
- 更容易展示企业级 MLOps 能力。
- 应用层只需替换推理 endpoint 配置。

注意事项：

- SageMaker 成本可能高于低频 EC2 MVP。
- 需要准备模型打包、推理镜像和 endpoint 配置。
- 对于作品集阶段，不建议第一天就上 SageMaker。

---

### Phase 5：多环境与治理体系

**目标**：形成接近企业生产环境的工程治理能力。

建议拆分环境：

| 环境 | 用途 | 特点 |
|---|---|---|
| Dev | 日常开发与调试 | 成本优先，可使用 Spot、定时关机 |
| Staging | 发布前验证 | 模拟生产配置，数据脱敏 |
| Prod | 生产或公开展示 | 稳定性、安全性、审计优先 |

推荐治理措施：

1. 基础设施即代码
   - 使用 Terraform 或 AWS CDK 管理 VPC、ALB、ECS、IAM、S3、CloudWatch。
   - 所有环境通过代码重建。

2. CI/CD
   - Pull Request 触发测试。
   - Merge 后构建 Docker 镜像。
   - 自动推送 ECR。
   - 部署到 ECS 或 SageMaker。

3. 安全审计
   - CloudTrail 记录所有 API 调用。
   - GuardDuty 检测异常行为。
   - AWS Config 检查资源配置合规。

4. 数据保护
   - S3、EBS、数据库启用 KMS 加密。
   - S3 开启版本控制。
   - 定期做恢复演练。

5. 成本治理
   - 所有资源打标签。
   - 每月预算告警。
   - 定期查看 Cost Explorer。

---

## 六、安全设计

### 6.1 网络安全

推荐安全组策略：

| 服务 | 入站规则 | 来源 |
|---|---|---|
| ALB | TCP 443 | Internet |
| FastAPI Service | App Port | ALB Security Group |
| vLLM Service | TCP 8000 | FastAPI Security Group 或 localhost |
| EC2 Admin | SSM | 不开放 SSH 或仅临时限制 My IP |
| RDS/OpenSearch | DB/Search Port | App Security Group |

不建议：

- 将 `8000` 直接暴露公网。
- 将 Jupyter 的 `8888` 长期开给公网。
- 在服务器保存明文 `.env` 且无权限控制。
- 使用 root 用户或长期 IAM User Access Key。

### 6.2 IAM 与密钥管理

推荐做法：

- EC2、ECS、Lambda 均使用 IAM Role。
- 密钥存 Secrets Manager。
- 配置存 SSM Parameter Store。
- KMS 管理 S3、EBS、Secrets 的加密密钥。
- IAM 权限按最小权限原则设计。

需要管理的敏感信息：

- Hugging Face Token
- OpenAI 或其他 API Key
- 数据库密码
- 第三方金融数据 API Key
- JWT Secret
- 内部服务调用 Token

---

## 七、可观测性设计

### 7.1 日志

需要采集：

- FastAPI access log
- FastAPI error log
- LangGraph agent execution log
- vLLM request log
- vLLM error log
- 系统日志
- 部署日志

### 7.2 指标

核心指标：

| 类型 | 指标 |
|---|---|
| API | 请求量、错误率、P50/P95/P99 延迟 |
| Agent | 每个 Agent 调用次数、失败率、平均耗时 |
| LLM | tokens/s、首 token 延迟、生成耗时、上下文长度 |
| GPU | GPU 利用率、显存使用、温度 |
| RAG | 检索耗时、Top-K 命中、引用覆盖率 |
| 成本 | 每日成本、月度预测成本、GPU 运行小时 |

### 7.3 告警

建议配置：

- API 5xx 错误率超过阈值
- P95 延迟超过阈值
- EC2 磁盘使用率超过 80%
- GPU 显存持续接近满载
- vLLM 进程退出
- 月度成本超过预算 50%、80%、100%

---

## 八、成本控制方案

### 8.1 当前 MVP 成本策略

当前阶段建议继续使用：

- `g4dn.2xlarge` On-Demand 或 Spot
- EventBridge + Lambda 定时开关机
- EBS gp3
- S3 存储模型与文档备份
- AWS Budgets 告警

### 8.2 成本优化优先级

| 优先级 | 措施 | 说明 |
|---|---|---|
| 高 | 定时开关机 | 对低频使用最有效 |
| 高 | 关闭公网无用服务 | 降低安全风险，也减少误用 |
| 高 | 设置 Budgets | 防止意外成本失控 |
| 中 | Spot 实例 | 适合开发和展示，不适合强生产 SLA |
| 中 | 模型量化 | 降低显存压力，可能减少实例规格 |
| 中 | 数据生命周期策略 | S3 日志、备份分层存储 |
| 低 | Reserved Instances / Savings Plans | 只有长期稳定运行后再考虑 |

### 8.3 成本建议

作品集和开发阶段：

- 优先使用定时开关机。
- 可以尝试 Spot，但要接受中断。
- 月成本目标控制在 80-130 USD。

企业演示或小规模生产阶段：

- 应用层使用 ECS Fargate。
- 推理层可以继续使用 On-Demand GPU EC2。
- 月成本可能上升，但稳定性更强。

正式生产阶段：

- 推理层考虑 SageMaker Endpoint。
- 根据流量配置 autoscaling。
- 成本以稳定性、审计和 SLA 为优先。

---

## 九、CI/CD 与 IaC 方案

### 9.1 推荐仓库流程

```text
Developer Push
  -> GitHub Pull Request
  -> Unit Test / Lint / Security Scan
  -> Build Docker Image
  -> Push to Amazon ECR
  -> Deploy to ECS Fargate
  -> Smoke Test
  -> Notify
```

### 9.2 基础设施管理

推荐使用 Terraform 或 AWS CDK 管理：

- VPC
- Subnets
- Security Groups
- ALB
- ECS Cluster
- ECR Repository
- IAM Roles
- S3 Buckets
- CloudWatch Log Groups
- Budgets
- EventBridge Rules
- Lambda 定时开关机函数

### 9.3 发布策略

MVP 阶段：

- 手动部署可以接受。
- 但要保留部署脚本和配置说明。

企业级阶段：

- 应用层自动部署。
- 生产环境需要审批。
- 模型发布需要版本号和回滚方案。

---

## 十、风险与应对措施

| 风险 | 影响 | 应对措施 |
|---|---|---|
| 模型服务公网暴露 | 高 | vLLM 只允许私网访问，公网只开放 ALB 443 |
| GPU 成本失控 | 高 | Budgets、定时开关机、Spot、成本标签 |
| 密钥泄漏 | 高 | Secrets Manager、IAM Role、禁止长期 Access Key |
| Spot 中断 | 中 | 仅用于开发展示，生产使用 On-Demand 或 SageMaker |
| 单机故障 | 中 | EBS Snapshot、S3 备份、IaC 快速重建 |
| RAG 数据不一致 | 中 | 文档、embedding、prompt、评测集版本化 |
| 模型效果不足 | 中 | RAG 增强、金融 prompt、后续 LoRA 或金融模型替换 |
| 缺少审计 | 中 | CloudTrail、AWS Config、GuardDuty |

---

## 十一、推荐立即执行清单

### 11.1 今天可以做

1. 关闭公网 `8000` 和 `8888`。
2. 确认 Security Group 只保留必要端口。
3. 配置 AWS Budgets 月度预算告警。
4. 配置 EBS Snapshot。
5. 将模型文件、RAG 文档、部署脚本备份到 S3。

### 11.2 接下来 1-3 天

1. 配置 ALB + ACM HTTPS。
2. FastAPI 通过 HTTPS 对外服务。
3. vLLM 仅内网或本机访问。
4. 安装 CloudWatch Agent。
5. 使用 IAM Role 替代 Access Key。
6. 配置 EventBridge + Lambda 定时开关机。

### 11.3 接下来 1-2 周

1. FastAPI 和 LangGraph 容器化。
2. 建立 ECR。
3. 使用 ECS Fargate 部署应用层。
4. RAG 原始文档统一进入 S3。
5. 评估 OpenSearch Serverless 或 Aurora pgvector。
6. 编写 Terraform/CDK 基础设施代码。

---

## 十二、最终建议

AlphaPilot 当前最优策略不是立即上 SageMaker 或复杂多账号架构，而是采用“生产风格 MVP -> 容器化应用层 -> 托管数据层 -> 托管推理层”的演进路线。

推荐优先级如下：

1. **先把现有 EC2 MVP 加固到可安全展示**
   - HTTPS
   - ALB
   - 私有 vLLM
   - CloudWatch
   - Budgets
   - EBS/S3 备份

2. **再把 FastAPI 和 LangGraph 从 GPU 机器中拆出来**
   - Docker
   - ECR
   - ECS Fargate

3. **然后升级 RAG 和推理服务**
   - S3 管理文档
   - OpenSearch Serverless 或 pgvector 管理向量
   - SageMaker 管理模型推理

这样既能保持当前项目快速推进，又能体现企业级云架构、LLMOps、多 Agent 工程化、成本控制和安全治理能力。

---

**文档结束**
