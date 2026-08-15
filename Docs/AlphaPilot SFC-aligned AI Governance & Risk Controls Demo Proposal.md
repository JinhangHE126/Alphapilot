# AlphaPilot SFC-aligned AI Governance & Risk Controls Demo Proposal

## 1. 项目摘要

本项目计划在一个工作日内，为 AlphaPilot 增加一套可运行、可测试、可演示的 AI 治理与风险控制层。

控制设计参考：

- [SFC 2024《Use of generative AI language models》通函](https://apps.sfc.hk/edistributionWeb/gateway/EN/circular/doc?refNo=24EC55)
- [SFC 2026 AI-enabled cyberattack 通函](https://apps.sfc.hk/edistributionWeb/gateway/EN/circular/intermediaries/supervision/doc?refNo=26EC32)
- [2026 GenAI Sandbox++ 联合通函](https://apps.sfc.hk/edistributionWeb/gateway/EN/circular/intermediaries/supervision/doc?refNo=26EC11)
- SFC Code of Conduct
- 香港 PDPO 及 PCPD AI 指引

本项目是工程控制 Demo，不是法律意见、SFC 认证或正式合规结论。

建议统一使用以下表述：

> AlphaPilot demonstrates engineering controls aligned with selected SFC regulatory expectations published between 2024 and 2026. It is not an SFC certification or a determination of regulatory compliance.

## 2. AlphaPilot 用例定义

### 2.1 用例

AlphaPilot 是一个 AI-assisted investment research system，能够：

- 收集结构化市场和基本面数据
- 检索公司公告、年报和新闻
- 运行多个分析 Agent
- 生成股票研究结论及报告
- 保存 Evidence Packet 和引用记录

### 2.2 明确边界

Demo 必须声明：

- 不提供个人化投资建议
- 不执行交易
- 不自动向客户发布报告
- 不进行 suitability assessment
- 不取代持牌人士、Compliance 或 Responsible Officer
- 所有正式报告必须经过人工审批

### 2.3 风险分类

AlphaPilot 虽然不交易，但输出可能影响投资决策。因此本 Demo 自愿按高影响用例管理：

> AlphaPilot is voluntarily treated as a high-impact AI use case for this demonstration because its outputs may influence investment research and decision-making.

这不代表 SFC 已正式认定 AlphaPilot 属于某一风险类别。

## 3. 当前系统基础

AlphaPilot 已经具备部分良好基础：

- `schemas/evidence_packet.py`
  - 结构化事实、来源、置信度、缺失数据和冲突
  - Evidence Score 和输出等级控制
- `agents/guard_agent.py`
  - unsupported claim 检查
  - ticker mismatch 检查
  - 文档引用和 grounding 检查
- `services/citations.py`
  - 将 `[doc:N]` 映射到原始 document chunk
- `db/models.py`
  - 分析历史、Agent event 和 citation 数据
- `knowledge/sensitive_scanner.py`
  - 身份证、银行卡、电话及邮箱打码
- `api/main.py`
  - 用户身份认证和 request ID
- `analysis_service.py`
  - Guard、Evidence Packet、citation 和 SSE 工作流

因此第一天不需要重写 Agent 系统，应在现有 Evidence Packet、Guard、数据库和 API 上增加治理控制。

## 4. 当前主要缺口

### 4.1 Audit Log 不完整

当前记录尚未形成统一的 audit record，缺少：

- request ID 与分析记录关联
- 操作用户
- model/provider/version
- prompt version
- 输入数据来源完整快照
- Guard 结果
- 风险标记
- 审核人和审批状态
- 发布状态
- kill-switch 状态

### 4.2 引用验证仍有宽松路径

当前 `services/citations.py` 在报告没有 `[doc:N]` 时，会把所有 document evidence 作为 fallback 保存。

这不能证明报告中的结论真正引用了这些资料。Demo 中应改为：

- 没有引用时明确记录 `missing_citations`
- 不把所有检索资料假定为已引用
- 重要结论缺少有效引用时阻止审批

此外，`FULL_ANALYSIS` 下部分 document grounding 问题目前会降级为 warning。对于重要研究结论，建议改为 blocking issue。

### 4.3 缺少人工审批和发布门控

当前分析完成后直接保存为 completed，没有：

- Draft
- Pending Review
- Approved
- Rejected
- Revision Requested
- Published

也没有 reviewer、review comments 和 approval timestamp。

### 4.4 安全控制不足

现有敏感信息扫描主要针对上传文档，而且覆盖类型有限。仍缺少：

- 用户 prompt 敏感数据扫描
- Prompt injection 检测
- System prompt override 检测
- 外部文档不可信指令隔离
- 模型/API 故障 fallback
- 全局 kill switch

## 5. 第一天目标

当天必须完成的 P0 控制：

1. 统一 audit record
2. 严格 citation/unsupported claim validation
3. 人工 Approve、Reject、Request Revision
4. 未批准报告不得发布
5. AI 免责声明
6. Prompt injection 和敏感数据基础检查
7. Kill switch
8. 自动化测试及一条完整演示链路

以下内容作为 P1，有时间再完成：

- 完整审批前端
- 多级 reviewer 权限
- 供应商健康状态自动监控
- 高级语义 Prompt injection classifier
- 完整 incident management UI

## 6. 建议分支

```text
feat/sfc-ai-governance-controls
```

从团队实际集成分支创建。开始前应确认使用 `dev` 还是 `master`，不要凭空选择。

第二天的批量分析分支应在本分支合并后创建：

```text
feat/batch-1000-equities
```

## 7. 建议目录结构

```text
docs/
└── compliance/
    ├── SFC_CONTROL_MAPPING.md
    ├── AI_USE_CASE_RISK_ASSESSMENT.md
    ├── MODEL_CARD.md
    ├── THIRD_PARTY_REGISTER.md
    ├── EVALUATION_REPORT.md
    └── INCIDENT_RESPONSE.md

alphapilot/
├── governance/
│   ├── audit.py
│   ├── approvals.py
│   ├── claim_validation.py
│   ├── prompt_security.py
│   ├── kill_switch.py
│   └── disclaimers.py
├── schemas/
│   ├── audit_record.py
│   └── approval.py
└── test/
    ├── test_audit_record.py
    ├── test_approval_gate.py
    ├── test_claim_validation.py
    ├── test_prompt_security.py
    └── test_kill_switch.py
```

不要移动现有 Evidence Packet、Guard 或 citation 模块。治理层应组合并复用它们。

## 8. 统一 Audit Record

每次分析应生成不可混淆的审计记录：

```text
request_id
analysis_id
session_id
user_id
timestamp_started
timestamp_completed
use_case
stock_symbol
data_sources
retrieved_document_ids
cited_chunk_ids
evidence_packet_snapshot
model_provider
model_name
model_version
prompt_version
generated_output
citation_validation
guard_result
risk_flags
human_reviewer
review_comments
approval_status
approval_timestamp
publication_status
kill_switch_status
```

建议新增独立 `ai_audit_records` 表，而不是继续向 `analysis_history` 塞入大量字段。

Audit log 不应保存：

- API key
- 密码或 token
- 未打码个人资料
- 完整 system prompt 中的敏感配置

## 9. 人工审批工作流

状态机：

```text
DRAFT
  ↓
PENDING_REVIEW
  ├── APPROVED
  ├── REJECTED
  └── REVISION_REQUESTED → DRAFT
```

规则：

- Guard 未通过：不能提交审批
- 重要结论缺少引用：不能提交审批
- Kill switch 开启：不能生成或发布
- 只有 `APPROVED` 报告能够标记为 `PUBLISHED`
- 报告修改后，原审批自动失效
- 审批和拒绝均写入 audit event
- reviewer 不得为空

建议 API：

```text
POST /analyses/{id}/submit-review
POST /analyses/{id}/approve
POST /analyses/{id}/reject
POST /analyses/{id}/request-revision
POST /analyses/{id}/publish
GET  /analyses/{id}/audit
GET  /analyses/{id}/audit/export
```

第一天可以只实现 API 和简单前端按钮，不必构建复杂 Compliance Dashboard。

## 10. Citation 和 Claim Validation

重要结论包括：

- 买入、卖出或持有判断
- 公司盈利或增长判断
- 估值判断
- 重大风险判断
- 所有数字、比例、日期及金额
- 对公告、年报或管理层表述的引用

验证规则：

- `[doc:N]` 必须对应真实 chunk
- 引用必须属于当前 ticker
- 数字必须存在于 Evidence Packet
- 无来源数字标记为 `UNSUPPORTED_NUMERIC_CLAIM`
- 无有效引用的重要结论标记为 `MISSING_CITATION`
- 虚构 document marker 标记为 `INVALID_CITATION`
- blocking issue 存在时不能提交审批

验收测试必须证明：

1. 有来源结论通过
2. 虚构 `[doc:99]` 被拒绝
3. 无来源数字被拒绝
4. 错误 ticker 资料被拒绝
5. 仅检索但未引用的资料不能被当作 citation evidence

## 11. Prompt 与数据安全

### 输入检查

在用户 prompt 和上传文档进入 Agent 前检查：

- 个人资料
- 密码、token、API key 格式
- “ignore previous instructions”
- “reveal system prompt”
- “override policy”
- 来自检索文档的操作指令
- 要求绕过 citation 或 Guard 的内容

处理方式：

- 个人资料：打码并记录命中类型
- Secrets：阻止请求并提示删除
- Prompt injection：隔离指令、记录风险标记
- 严重攻击：阻止分析

不要声称基于正则表达式的扫描可以识别所有攻击。文档中应明确它只是基础控制。

## 12. Kill Switch 与故障降级

环境变量建议：

```text
AI_OUTPUT_ENABLED=true
AI_PUBLICATION_ENABLED=true
```

行为：

- `AI_OUTPUT_ENABLED=false`
  - 不调用模型
  - 返回服务暂停提示
  - 写入 audit event
- `AI_PUBLICATION_ENABLED=false`
  - 可以生成 Draft
  - 禁止审批后发布
- 模型/API 故障
  - 不伪造成功结果
  - 保留已收集 Evidence Packet
  - 输出 `DATA_SUMMARY_ONLY` 或明确失败状态
  - 记录 provider、错误类型和时间

## 13. AI 免责声明

所有 Draft 和 Approved 报告均显示：

> This report was generated with AI assistance for research and engineering demonstration purposes. It may contain errors or omissions and does not constitute personalised investment advice, an offer, solicitation or recommendation to trade any security. Important conclusions must be independently reviewed by an authorised human reviewer before publication or use.

免责声明不能替代实际控制，也不能把不合格报告变成可发布报告。

## 14. Agent 实施指令

Agent 开始编码前必须：

1. 阅读官方监管资料
2. 阅读 `README.md`
3. 阅读 `alphapilot/Docs/architecture.md`
4. 阅读 Evidence Packet、Guard、citation、analysis service、数据库及 API
5. 运行现有 Guard、citation、sensitive scanner 测试
6. 记录现有测试基线
7. 确认当前分支和工作区状态
8. 不覆盖用户未提交的修改

编码顺序：

1. 定义 audit 和 approval schemas
2. 增加数据库表及 repository
3. 将 request ID 传播到 analysis workflow
4. 收紧 citation fallback
5. 增加 claim validation
6. 增加 approval state machine
7. 增加发布门控
8. 增加 prompt security
9. 增加 kill switch 和 fallback
10. 增加 API
11. 增加最小前端展示
12. 补充测试和治理文档

Agent 不应：

- 宣称项目已经 SFC compliant
- 把免责声明当成控制
- 仅通过 prompt 要求模型自行检查
- 在无引用时自动附上所有检索结果
- 允许 Guard 失败报告进入 Approved
- 为赶 Demo 绕过认证或用户隔离

## 15. 用户需要人工完成的事项

项目负责人需要：

- 确认 AlphaPilot 的实际运营主体
- 确认运营主体是否为 SFC Licensed Corporation
- 确认系统是否用于 regulated activities
- 指定 use-case owner
- 指定 reviewer 和 approver
- 确认实际模型及 API 供应商
- 填写第三方数据处理地点和保留政策
- 审核免责声明
- 决定 audit log 保留期限
- 与 Compliance、Legal 和管理层确认正式上线要求

Agent 不能代替这些审批。

## 16. 一天执行时间表

### 09:00–10:00：范围和基线

- 阅读监管资料
- 确认用例边界
- 运行现有测试
- 完成 control gap list
- 冻结 P0 范围

### 10:00–12:00：Audit 与审批基础

- 新增 audit schema/table
- 传播 request ID
- 保存模型、prompt、证据及 Guard 信息
- 实现审批状态机和 repository

### 13:00–14:30：Citation 与 Claim 控制

- 删除 citation fallback 的错误证明效果
- 验证重要结论和数字
- Guard blocking issue 接入审批门控
- 编写负面测试

### 14:30–15:30：安全和故障控制

- Prompt injection 基础规则
- Secrets 与敏感数据检查
- Kill switch
- 模型失败降级

### 15:30–16:30：API 和最小 UI

- Review API
- Audit export API
- Approve、Reject、Revision 按钮
- 展示免责声明和审批状态

### 16:30–17:30：测试和评估

- 单元测试
- API 权限测试
- 审批状态转换测试
- Prompt injection 测试
- Kill switch 测试
- Evidence traceability 测试

### 17:30–18:00：演示和彩排

- 生成一份 AAPL 或 0700.HK 报告
- 展示 claim → citation → chunk
- 演示 unsupported claim 被拒绝
- 演示人工审批
- 导出 audit log
- 展示 kill switch

## 17. 当天交付物

必须交付：

- 可运行的治理控制代码
- Audit log 数据结构和导出
- Human approval workflow
- Citation/claim blocking
- Prompt security 基础控制
- Kill switch
- 自动化测试
- `SFC_CONTROL_MAPPING.md`
- `AI_USE_CASE_RISK_ASSESSMENT.md`
- `MODEL_CARD.md`
- `THIRD_PARTY_REGISTER.md`
- `EVALUATION_REPORT.md`
- `INCIDENT_RESPONSE.md`

六份治理文档允许是 Demo-grade，但必须：

- 内容真实
- 明确 owner 尚未确认的项目
- 不伪造审批
- 不把未来计划写成已实现控制
- 对每项 remaining limitation 清楚说明

## 18. 验收标准

Demo 通过需要同时满足：

- 能从一条研究结论追溯到原始 document chunk
- 无来源数字被自动标记
- 无效 citation 被阻止
- Guard 失败报告无法提交审批
- 未批准报告无法发布
- 审核人可以 Approve、Reject、Request Revision
- 能导出包含模型、prompt、证据、验证及审批信息的 audit log
- Prompt injection 测试被识别或隔离
- Kill switch 能暂停 AI 输出
- 模型失败不会生成虚假成功报告
- UI 和导出报告包含 AI 免责声明
- 所有文档明确说明并非正式 SFC 合规认证

## 19. Demo 演示脚本

建议使用 AAPL 或 0700.HK：

1. 登录 AlphaPilot
2. 提交股票研究请求
3. 展示 request ID
4. 展示 Evidence Packet
5. 展示 Agent 生成报告
6. 点击一条 `[doc:N]` 查看原始来源
7. 注入无来源数字，展示 Guard 拒绝
8. 提交人工审核
9. Request Revision
10. 修订后重新提交
11. Approve
12. 发布报告
13. 导出 audit log
14. 开启 kill switch
15. 再次请求分析并展示系统拒绝生成

最终介绍：

> Day 1 added an SFC-aligned governance layer to AlphaPilot, including evidence traceability, deterministic claim validation, human approval, security controls, operational fallback and auditable records. The implementation is an engineering demonstration and not a certification of regulatory compliance.
