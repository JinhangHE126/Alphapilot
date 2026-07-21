EC2 g4dn.2xlarge 最优成本部署方案
（含 Spot 实例 + 定时开关机 + vLLM + LangGraph）
文档版本：v1.0
编制日期：2026年6月4日
编制人：何金航（Jinhang He）
所属项目：AlphaPilot 多智能体香港股权研究系统
用途：项目部署执行规划 / 领导评审

一、执行摘要
本方案针对 AlphaPilot 项目当前阶段（学生/作品集开发、低使用量）设计，目标是以最低成本、最快速度将整个系统部署到 AWS。
由于 EC2 G and VT 实例配额已获批（新加坡区域 8 vCPU），我们选择 g4dn.2xlarge Spot 实例 作为主要计算资源，配合 定时开关机 策略，实现高性价比部署。
核心优势：

预计月成本可控制在 70-130 USD（低使用量场景）
3-5 天内可完成核心系统部署并跑通
调试方便，适合快速迭代
为后续迁移到 SageMaker 保留平滑路径


二、背景与目标
当前痛点：

原计划使用 EC2 g4dn.2xlarge 受配额限制
SageMaker 方案虽然专业，但部署周期较长、初期成本相对较高
项目急需跑通完整流程（多 Agent + RAG + LLM）以支持后续开发与作品集展示

部署目标：

快速将 FinGPT（或 Llama3 LoRA）+ LangGraph 多 Agent 系统部署到云端
实现低成本运行（Spot + 定时开关机）
保证系统稳定可调试
为后续演进到生产级架构（SageMaker + Fargate）做好准备


三、总体架构与成本优化设计
推荐架构：

计算层：1 台 g4dn.2xlarge Spot 实例（同时运行 vLLM + FastAPI + LangGraph）
存储层：EBS gp3（持久化模型、代码、日志）
调度层：Lambda + EventBridge（定时开关机）
推理引擎：vLLM（支持 LoRA，推理效率高）
应用层：FastAPI + LangGraph（Agent 编排与 API 服务）

成本优化核心策略（必须实施）：

使用 Spot 实例（比 On-Demand 便宜 60-70%）
使用 定时开关机（工作日自动开机，非工作时间自动关机）
模型与代码放在 EBS 上，关机不丢失数据
初期 RAG 使用轻量方案（FAISS），降低存储成本
设置 AWS Budgets 告警


四、详细部署步骤
Phase 0: 前置准备（0.5-1 天）

确认配额已生效（已批准 8 vCPU）
创建或确认 Key Pair（.pem 文件）
创建 Security Group：
SSH (22)
TCP 8000（vLLM）
TCP 8001（FastAPI，可选）

创建 S3 Bucket 用于模型存储与备份
准备模型文件（Llama-3-8B + FinGPT LoRA adapter）并上传至 S3

Phase 1: 启动 Spot g4dn.2xlarge 实例（0.5 天）
推荐 AMI：Deep Learning AMI GPU PyTorch（Ubuntu 版本，预装 NVIDIA 驱动与 CUDA）
启动要点：

Instance Type：g4dn.2xlarge
Purchasing option：Request Spot instances
Storage：至少 100GB gp3
Security Group：使用上面创建的安全组
Key Pair：选择已创建的密钥对

启动后使用以下命令登录：
Bashchmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<Public-IP>
Phase 2: 环境配置与 vLLM 部署（1-1.5 天）
登录实例后执行：
Bash# 更新系统
sudo apt update && sudo apt install -y git wget curl

# 安装 vLLM
pip install vllm --upgrade

# 创建模型目录
mkdir -p ~/models
部署 FinGPT / Llama3 LoRA 推荐命令（示例）：
Bashpython -m vllm.entrypoints.openai.api_server \
    --model /home/ubuntu/models/llama-3-8b-instruct \
    --enable-lora \
    --lora-modules fingpt=/home/ubuntu/models/fingpt-lora \
    --port 8000 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.85 \
    --host 0.0.0.0
建议将模型下载脚本写入 User Data 或使用 S3 自动下载。
Phase 3: 部署 FastAPI + LangGraph（1-1.5 天）
Bashmkdir ~/alphapilot && cd ~/alphapilot
git clone <你的仓库> .
pip install -r requirements.txt
推荐项目结构：
textalphapilot/
├── app/
│   ├── main.py
│   ├── agents/
│   └── services/          # 封装 vLLM 调用
├── docker-compose.yml
└── requirements.txt
启动服务：
Bashuvicorn app.main:app --host 0.0.0.0 --port 8001
在 LangGraph 中通过 httpx 或 langchain 调用本地 vLLM（http://localhost:8000/v1）。
Phase 4: 配置定时开关机（0.5-1 天，最关键的成本控制）
使用 AWS Lambda + EventBridge 实现自动化：

创建两个 Lambda 函数：
StartAlphaPilotInstance：启动 EC2
StopAlphaPilotInstance：停止 EC2

使用 EventBridge 规则：
工作日 8:30 触发启动
工作日 23:00 触发停止


此策略可将月成本降低 40-60%。
Phase 5: RAG 与完整集成（1-2 天）

初期使用 FAISS + 本地/S3 文档 快速跑通流程
验证 Supervisor + 多个专业 Agent 协作
测试完整链路（用户请求 → Agent 编排 → vLLM 调用 → RAG 增强 → 返回结果）


五、成本估算
预估月成本（新加坡区域，低使用量）：

Spot g4dn.2xlarge + 定时开关机（每天 6 小时）：约 70-110 USD
加上 EBS、数据传输、CloudWatch 等：总计约 80-130 USD/月

相比 24/7 运行 On-Demand 实例，可节省 60% 以上 费用。

六、风险与应对措施






























风险影响应对措施Spot 实例被中断中使用 EBS 持久化数据；设置中断通知；准备备用 On-Demand 实例模型加载慢低使用 EBS 存储模型；开机后自动加载定时开关机失败低Lambda 添加重试机制 + CloudWatch 告警安全组配置不当中仅开放必要端口；使用 IAM Role 而非长期 Access Key

七、实施时间线（建议）















































阶段时间关键交付物优先级Phase 0Day 1配额确认 + Security Group + S3高Phase 1Day 1-2Spot 实例启动 + vLLM 正常运行高Phase 2Day 2-3FastAPI + LangGraph 服务上线高Phase 3Day 3-4定时开关机配置完成高Phase 4Day 4-5RAG 集成 + 完整流程测试通过中成本优化与监控Day 5+预算告警 + 监控 Dashboard中
预计 4-6 天 可完成核心系统部署并稳定运行。

八、后续演进建议

短期（当前阶段）：使用本方案快速跑通项目，支撑开发与迭代。
中期（作品集完善阶段）：将 LLM Inference 部分迁移到 SageMaker（展示 MLOps 能力）。
长期（生产需求出现时）：演进为 SageMaker Endpoint + ECS Fargate 架构。


九、所需支持与下一步
下一步行动建议：

确认是否采用本方案。
我将立即提供以下配套材料：
完整的 User Data 启动脚本
Lambda 定时开关机代码
vLLM + LangGraph 集成示例
详细的安全组与 IAM 配置建议


请领导审阅本方案。如有任何调整意见（如预算上限、时间要求、是否优先使用 Spot 等），请随时告知。

何金航
MSc Data Science & Artificial Intelligence
The Hang Seng University of Hong Kong
2026年6月4日