---
name: milestone-step-execution
description: >-
  Use only when the user explicitly invokes $milestone-step-execution or explicitly
  names this skill.
---

# 里程碑 STEP 执行

## 手动触发

仅在用户显式调用 `$milestone-step-execution` 或明确点名「milestone-step-execution」技能时使用。
不要仅因用户提到 PRD、STEP、里程碑、开发批次、阶段验收或契约而自动触发。

## 核心定位

将已经确认的开发 STEP 编排为可验收的 `M1…Mn`，并按确认后的顺序推进。

**本 Skill 只改变执行分组、顺序和批次，不改变需求或 STEP 内容。**

## 入口模式

- `standalone`：用户直接调用本 Skill。规划请求只输出本阶段计划；用户另行明确启动开发且满足执行门禁时，保留原有执行编排能力。当前阶段结束后停止，不自动进入其他 Skill。
- `orchestrated`：由 `$prd-delivery-harness` 在 Phase 3 读取本 Skill 后执行，只生成 `execution-plan.md`，不等待重复的阶段确认，不执行 STEP。业务代码或正式 Contract 必须由用户另行明确显式启动。

`orchestrated` 的唯一 STEP 输入是通过完整复审的 `steps-verified.md`。只有 `steps-draft.md`、`steps-provisional.md`，或存在关键未核实路径/符号时，返回 `FAILED_VALIDATION` 并停止；时间压力、已投入成本和上线承诺不能替代上游门禁。

## 前置条件与模式

必须同时具备：

- 已确认的 PRD 或等价需求文档；
- 已拆解完成、含完成标志或验收口径的开发 STEP；
- 用户提供或可从项目中发现的开发规范。

缺少 STEP 时停止，建议先使用 `prd-to-steps`。STEP 与 PRD 明显不一致时报告问题并暂停；需要审查时建议使用 `step-doc-review`。

根据用户意图区分：

- **规划模式**：用户要求制定计划、讨论拆分或安排顺序时，只产出草案；确认前不落盘、不执行开发。
- **执行编排模式**：仅用于 `standalone`，且用户另行明确要求开始开发时，按已确认计划组织 STEP 执行、验证、进度和契约，不替代 STEP 自身的技术要求。`orchestrated` 禁止进入此模式。

## 来源与阶段结果

来源标签统一为：`USER_DECISION`、`PRD`、`CONTRACT`、`REPO_BASELINE`、`RUNTIME`、`PLANNED`、`UNVERIFIED`。计划引用的现有路径/符号必须有 `REPO_BASELINE` 证据；总控模式中还必须保留上游 `source_id` 与可核实 `locator`，不得把新路径重新标成 existing。新产物标 `PLANNED`；关键 `UNVERIFIED` 不能进入正式执行计划。没有 `RUNTIME` 证据时，不声称线上行为已验证。

| 结果 | 使用条件 |
|---|---|
| `PASS` | 计划覆盖、依赖、批次和验收均通过，风险列表为空 |
| `PASS_WITH_RISKS` | 门禁通过，仅有明确的非阻断风险 |
| `DOCUMENT_ONLY` | 只能讨论暂定分组，不能生成正式 `execution-plan.md` |
| `BLOCKED` | 存在未解决的业务或高风险决策 |
| `FAILED_VALIDATION` | 输入不是 `steps-verified.md`、关键来源未核实、计划遗漏/重复或来源已变化 |

只要列出非阻断风险就使用 `PASS_WITH_RISKS`。`BLOCKED` 或 `FAILED_VALIDATION` 不得继续。

## 源文档不可改写

将 PRD、补充规格和 STEP 正文视为只读事实来源：

- 不新增、删除、改写或合并需求与 STEP；
- 不改变原有业务语义、范围、完成标志或验收口径；
- 不用实施计划补造 STEP 中不存在的需求；
- 发现遗漏、冲突、歧义或不可执行项时，记录证据、影响和阻塞位置，等待用户处理。

实施计划只能引用 STEP 编号、标题和原验收口径。

## 先发现项目约定

规划前先扫描项目目录和规则文件，定位：PRD、STEP、现有实施计划、进度记录、临时契约、正式契约及命名规范。

优先复用已有路径和格式。缺少某类执行文档时，提出建议路径、职责和最小结构，得到用户确认后再创建。不要假设固定的 `docs/` 布局、文件名或契约章节。

## 自适应划分里程碑

用户指定的阶段和约束优先。用户未指定时，根据以下信息提出 `M1…Mn` 草案：

1. STEP 的显式与隐式依赖；
2. 每组可独立验证的交付能力；
3. 技术风险、外部依赖和回滚难度；
4. 文件、数据、接口和契约冲突；
5. 用户要求的节奏、资源或发布日期。

里程碑数量不固定；简单模块可以只有一个，复杂模块可以有多个。不要机械按 STEP 编号、技术层或固定功能类型分组。

每个里程碑必须定义：

- 名称与一句话目标；
- 包含的 STEP、建议顺序和可并行候选；
- 前置依赖与明确排除项；
- 逐条验收清单和验证方式；
- 临时契约文档位置；
- 进入下一里程碑的闸门。

每个里程碑至少包含一个 STEP；不得用空里程碑占位。

先向用户展示完整划分草案及依据；只有用户确认后，才能写实施计划或开始执行。

## 决定执行批次

默认一次执行一个 STEP。多个 STEP 仅在同时满足以下条件时才可组成一个批次：

- 不存在未完成的先后依赖；
- 不会产生文件、数据、接口或契约冲突；
- 每个 STEP 可以独立验证、记录和回滚；
- 不跨越里程碑闸门。

批次数量不设固定上限。实施计划必须写明合批依据和独立验收方式，并在执行前取得用户确认。

## 工作流程

### 1. 生成计划草案

1. 读取源文档与项目约定，建立 STEP 依赖关系。
2. 生成 `M1…Mn` 划分、批次建议、风险和验收闸门。
3. 标明所有假设、冲突和待确认项。
4. 等待用户确认。

确认后，按项目约定写入实施计划，并建立或更新进度记录。使用 [实施计划模板](references/implementation-plan-template.md)。

在 `orchestrated` 中，总控已授权本阶段规划，跳过上述重复确认并直接生成 `execution-plan.md`；计划状态必须是 `IMPLEMENTATION_PLAN_READY`，业务代码状态必须是 `NOT_STARTED`，随后把阶段结果交回总控并停止。

### 2. 执行 STEP 或批次

执行前确认当前里程碑、前置依赖和本批范围。开发要求完全引用原 STEP，不重新解释为新需求。

每次交付至少包含：

- STEP 级改动文件列表；
- 对应原完成标志的验证证据；
- 契约增量草稿；
- 阻塞项、风险或偏差。

只有原 STEP 的完成标志全部满足时才更新为完成。使用 [执行指令模板](references/execution-prompt-templates.md)。

### 3. 里程碑验收

本里程碑所有 STEP 完成后：

1. 按已确认的验收清单逐条验证；
2. 未通过时记录缺口并留在当前里程碑；
3. 通过后汇总本里程碑全部契约增量，形成一份临时契约文档；
4. 更新进度记录；
5. 闸门通过后才进入下一里程碑。

临时契约使用 [临时契约模板](references/contract-draft-template.md)，只记录本里程碑的新增、变更和兼容影响。

### 4. 整合正式契约

仅当所有里程碑均完成并通过总验收后执行：

1. 读取全部里程碑临时契约和项目现有正式契约；
2. 按项目既有结构合并所有有效变更；
3. 更新已有条目而不是创建语义重复项；
4. 检查跨阶段冲突、重复、废弃项和兼容说明；
5. 保留临时契约作为阶段快照，并在进度记录中登记整合结果。

正式契约路径或格式不明确时，先提出方案并等待用户确认。

## 自检

- [ ] PRD 和 STEP 正文未被修改或重新解释
- [ ] 里程碑数量来自实际依赖和用户约束，而非固定模板
- [ ] 每个 STEP 只属于一个里程碑，且未遗漏
- [ ] 每个里程碑可独立验收，并有明确进入条件
- [ ] 合批 STEP 满足独立、无冲突、可分别验收
- [ ] 文档路径优先复用项目约定
- [ ] 执行中只更新临时契约，全部里程碑完成后才整合正式契约
- [ ] 发现需求或 STEP 问题时已暂停，而非自行改写
- [ ] `orchestrated` 只接收 `steps-verified.md`，只生成执行计划
- [ ] 执行计划中的 STEP 无遗漏、无重复归属
- [ ] 关键路径和符号没有 `UNVERIFIED`
- [ ] 计划明确标记业务代码 `NOT_STARTED`
- [ ] 已返回 `PASS`、`PASS_WITH_RISKS`、`DOCUMENT_ONLY`、`BLOCKED` 或 `FAILED_VALIDATION` 之一

## 附加资源

- [实施计划模板](references/implementation-plan-template.md)
- [临时契约模板](references/contract-draft-template.md)
- [执行指令模板](references/execution-prompt-templates.md)
