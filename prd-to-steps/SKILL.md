---
name: prd-to-steps
description: >-
  Use only when the user explicitly invokes $prd-to-steps or explicitly names
  this skill to turn a reviewed PRD into traceable development STEP drafts.
---

# PRD → STEP 草稿拆解

## 手动触发

仅在用户显式调用 `$prd-to-steps` 或明确点名 `prd-to-steps` 时使用。普通谈话中提到需求拆解、开发步骤或上传 PRD，不自动触发。

## 核心原则

把已审查的需求拆成范围单一、依赖显式、可验证且可追踪的 STEP 草稿。独立 STEP 指提示词自包含、范围单一、依赖写清楚，不代表没有依赖。

`steps-draft.md` 是草稿，不代表已经验证或可执行；只有 `step-doc-review` 完整复审后的 `steps-verified.md` 才能进入正式执行计划。

## 执行模式

- `standalone`：直接读取用户提供的已审查 PRD 或需求台账，输出本阶段的人类可读 STEP 文档后结束，不自动进入下一阶段。
- `orchestrated`：由 `$prd-delivery-harness` 在 Phase 1 读取本 Skill 后执行，接收 Phase 0 台账并把草稿、映射和阶段结果交回总控；不自行调用审查或里程碑 Skill。

## 输入与前置门禁

支持 `.md`、`.docx`、`.pdf`、URL、本地路径和文本粘贴。扫描件先 OCR；URL 只在可访问时读取。

必须有已审查的 PRD 或 `requirements-ledger.md`，且至少包含需求、验收和排除项。若输入仍有会改变业务行为的歧义，返回 `BLOCKED`。未实际读取必要代码或契约时可以继续文档级拆解，但只能生成 `steps-provisional.md` 并返回 `DOCUMENT_ONLY`。

## 事实与防补造

来源标签统一为：`USER_DECISION`、`PRD`、`CONTRACT`、`REPO_BASELINE`、`RUNTIME`、`PLANNED`、`UNVERIFIED`。用户提供并明确标为 PRD 的正文仍标 `PRD`；`USER_DECISION` 只表示用户在 PRD 之外明确补充或确认的具体决定。

- 禁止使用 `[自定义]` 来掩盖 PRD 缺失；禁止自行生成业务字段、状态、错误码、权限值、优先级或业务顺序。
- 用户说“按行业惯例补齐”不是具体业务决定。只有缺失选择会改变 PRD 定义的业务语义或使需求级验收无法表达，并且在已读取的 PRD、契约和仓库中仍不存在唯一答案时，才返回 `BLOCKED`。
- 尚未读取代码/契约、而缺失细节可能由现有项目唯一确定时，不提前要求用户决定；标为 `UNVERIFIED`，生成暂定 STEP 并返回 `DOCUMENT_ONLY`。
- 普通实现细节可标为 `PLANNED`，但只写“按已核实的项目约定确定”，不得先填具体值或声称已经决定。
- “现有查询入口、路由、下载约定、构建或测试命令”不是普通内部命名；未在来源中定位时必须标明发现门。若仍可安全规划则返回 `PASS_WITH_RISKS`，若它决定核心可行性或验收则走 `DOCUMENT_ONLY` 或阻断。
- 用户口述的仓库事实属于 `USER_DECISION`；只有本轮实际读取的代码证据才是 `REPO_BASELINE`。
- 没有 `RUNTIME` 证据时，不描述线上行为已经验证。

## 动态发现项目上下文

先从当前工作区、用户路径和项目规则中动态发现：PRD、契约、代码、测试、进度记录和文档约定。复用真实存在的布局，不固定假设 `docs/contract.md`、`docs/progress/` 或任何编辑器专用目录。

每个引用的路径或符号必须标记：

| 状态 | 含义 |
|---|---|
| `existing` | 已从当前仓库核实存在，并记录证据 |
| `planned` | 本次计划新增，尚不存在 |
| `unverified` | 目前无法核实；关键项不得进入正式计划 |

在 `orchestrated` 模式中，每个 `existing` 引用还必须记录总控 `source_manifest` 中的 `source_id` 与实际 `locator`；路径必须绑定到对应文件，符号定位符必须能在该文件中找到。`standalone` 报告若不生成 `run.json`，也应在人类可读证据中给出同等的具体文件/符号位置。

### 缺失信息分类

| 情况 | 本阶段动作 |
|---|---|
| PRD 明确要求沿用现有行为，但代码/契约未提供 | 标 `unverified`，生成 `steps-provisional.md`，返回 `DOCUMENT_ONLY` |
| 编码、文件名、内部接口路径等普通实现细节未规定 | 标 `planned` 或 `unverified`，不填具体值，不阻断草稿 |
| “与当前列表一致”但列表字段尚未核实 | 在暂定 STEP 中要求从现有列表/契约核实，不自行选择列集合 |
| 已查完可用来源后仍有多个会改变业务结果的合理解释 | 返回 `BLOCKED`，只询问最小业务决定 |

## 拆解流程

### 1. 固化输入清单

列出全部需求 ID、验收 ID、排除项和技术债。禁止用“核心/扩展/可选”等新优先级改写 PRD；只有来源已明确时才保留原优先级。

保留 PRD 显式 ID；未编号约束使用 `CSTR-*`，不得改造成新的 `RQ-*`。

### 2. 建立覆盖映射

先建立需求 → STEP、验收 → STEP 的映射，再写 STEP 正文。每个有效需求和验收必须至少映射一个 STEP；每个 STEP 必须至少引用一个需求 ID，并引用它负责的验收 ID。

STEP 只有在直接承担完整条款或可独立分割的子条款时，才能映射对应需求或验收 ID。仅相关的实现细节不得映射该 ID，也不得把同一 ID 泛化到每个相邻层级。

### 3. 划分最小单元和依赖

- 每个 STEP 只有一个可独立验证的目标；
- 显式写出前置 STEP，不得用编号顺序暗示依赖；
- 记录输入、输出、范围和排除项；
- 不把多个业务目标塞进一个 STEP；
- 不为看似独立而隐藏真实依赖。

### 4. 写自包含提示词

每个 STEP 使用 [STEP 模板](references/step-template.md)，至少包含：

- STEP ID、标题、目标和阶段状态；
- 需求 ID、验收 ID 与短原文；
- 前置依赖及验证方式；
- 参考路径/符号、状态和来源；
- 开发任务与明确不做；
- 可测试的正常、异常和边界验收；
- 完成标志与进度回传。

### 5. 自检并返回阶段结果

| 结果 | 使用条件 |
|---|---|
| `PASS` | 草稿结构、覆盖和必要代码事实完整，风险列表为空 |
| `PASS_WITH_RISKS` | 必要来源已核实，仅有明确的非阻断风险 |
| `DOCUMENT_ONLY` | 缺少必要代码/契约，只能生成 `steps-provisional.md` |
| `BLOCKED` | 需求仍需业务决定，无法安全拆解 |
| `FAILED_VALIDATION` | 映射、依赖、结构或来源摘要校验失败 |

只要报告列出非阻断风险，结果必须是 `PASS_WITH_RISKS`。`standalone` 在本阶段结束；`orchestrated` 将结果交回总控。不得由本 Skill 宣布 `STEPS_VERIFIED`、生成里程碑计划或开始开发。

## 输出

生成一个主要人类可读文件：

- 有代码/契约证据：`steps-draft.md`；
- 仅文档证据：`steps-provisional.md`。

文件包含：来源摘要、功能清单、STEP 总览、需求映射、验收映射、完整 STEP 提示词、自检和阶段结果。进度区块使用 [进度模板](references/progress-template.md)；只有项目已有独立进度文档约定或用户明确要求时才另存文件，路径从项目动态发现。

## 自检

- [ ] 所有需求和验收均映射到 STEP
- [ ] 每个 STEP 的需求 ID、验收 ID、依赖和范围明确
- [ ] 未增加 PRD 中不存在的业务语义
- [ ] 未使用 `[自定义]` 补造业务字段或值
- [ ] 所有路径和符号标记 `existing`、`planned` 或 `unverified`
- [ ] `existing` 引用均绑定实际来源 ID 与定位符
- [ ] 关键 `unverified` 未被表述为可执行事实
- [ ] 草稿未自称已验证或可执行
- [ ] 阶段只返回五种结果之一并在本阶段停止

## 参考文件

- [STEP 模板](references/step-template.md)
- [进度模板](references/progress-template.md)
