---
name: prd-delivery-harness
description: >-
  Use only when the user explicitly invokes $prd-delivery-harness or explicitly
  names this skill to produce reviewed, repaired, verified STEPs and a planning-only milestone plan from a PRD.
---

# PRD Delivery Harness

## 手动触发

仅在用户显式调用 `$prd-delivery-harness` 或明确点名 `prd-delivery-harness` 时使用。普通谈话中提到 PRD、STEP、里程碑或上传文档，不自动触发。

## 核心目标

用户只调用一次，本 Skill 在同一任务内按固定顺序完成：

1. `prd-review`
2. `prd-to-steps`
3. `step-doc-review`
4. `milestone-step-execution`

每进入一个阶段，才读取该阶段 Skill 的 `SKILL.md` 和它直接要求的资源，并按其 `orchestrated` 模式执行。不要要求用户逐个调用阶段 Skill。这里的 `orchestrated` 是本 Skill 的内部协议，不是假设平台提供递归 Skill 调用。

## 边界

本 Skill 只生成规划文档，不修改业务代码、正式 Contract、部署配置或项目数据。最终业务代码状态固定为 `NOT_STARTED`。实际开发必须由用户在本次流程结束后另行显式启动。

不覆盖用户提供的 PRD 或 STEP。为每次运行创建新的、用户可访问的产物目录；优先复用项目既有规划目录，没有约定时使用当前获授权输出区中的新运行目录。不得覆盖旧运行。

## 共享协议

阶段只返回：`PASS`、`PASS_WITH_RISKS`、`DOCUMENT_ONLY`、`BLOCKED`、`FAILED_VALIDATION`。

- `PASS` / `PASS_WITH_RISKS`：通过当前门禁；记录风险后继续。
- `DOCUMENT_ONLY`：只能走暂定分支，不能生成正式执行计划。
- `BLOCKED` 或 `FAILED_VALIDATION`：立即停止，不得继续下一阶段。

只维护这些状态：

```text
INPUT_READY → PRD_READY → STEPS_DRAFTED → STEPS_VERIFIED → IMPLEMENTATION_PLAN_READY
INPUT_READY → PRD_DOCUMENT_ONLY → PROVISIONAL_STEPS_READY → 停止
```

事实、产物和 `run.json` 的结构遵循 [流水线协议](references/pipeline-contract.md)。来源优先级为用户明确决定、PRD、PRD 引用契约、仓库基线、项目规范、派生文档。不得创造业务字段、值、状态、错误码、优先级或顺序。

## 运行流程

### 0. 初始化输入

1. 读取用户给出的 PRD、补充决定、项目规则、契约和仓库位置。
2. 创建新运行目录与 `run.json`，状态为 `INPUT_READY`，代码状态为 `NOT_STARTED`。
3. 按流水线协议建立含实际文件路径和 SHA-256 的 `source_manifest`。对话文本粘贴、URL 响应、OCR 结果等非本地文件输入先原样快照到运行目录的 `sources/`，再纳入清单；不可访问的 URL 不得猜测内容。由清单计算 `source_digest`，每个阶段前重新计算；变化时旧验证失效，从最早受影响阶段重做。
4. 若任一阶段 Skill 或必要资源无法发现/读取，返回 `FAILED_VALIDATION` 并停止。

### Phase 0：审查 PRD

读取并执行 `prd-review`：建立 `requirements-ledger.md`，完成 PRD 二次来源检查、代码/契约核验和阶段报告。

- 通过：状态改为 `PRD_READY`。
- 缺少代码但文档可审查：状态改为 `PRD_DOCUMENT_ONLY`。
- 真正业务歧义、高风险决定或必要来源缺失：停止。

### Phase 1：拆解 STEP

读取并执行 `prd-to-steps`：先做需求/验收到 STEP 的映射，再生成自包含、范围单一、依赖显式的 STEP。

- 从 `PRD_READY` 进入：生成 `steps-draft.md`，状态改为 `STEPS_DRAFTED`。
- 从 `PRD_DOCUMENT_ONLY` 进入：生成 `steps-provisional.md`，机械验证后改为 `PROVISIONAL_STEPS_READY` 并停止；不进入 Phase 2 或 Phase 3。

### Phase 2：审查、修正与完整复审

读取并执行 `step-doc-review` 的 `orchestrated` 模式：全量审查，修正确凿问题，重建映射和依赖，再从 PRD、契约和代码完整复审。最多两轮；保留原文、首次报告和 Diff，写入 `step-audit.md`。

Phase 2 若确认确凿的来源或语义错误来自 `requirements-ledger.md`，不得只修正下游 STEP；应使本次 Phase 0 及之后的候选派生产物失效，从冻结的原始输入重新执行 Phase 0，然后按固定顺序重做 Phase 1 和 Phase 2。这类上游重建最多一次；同类错误仍存在时返回 `FAILED_VALIDATION` 并停止。若错误涉及业务决策，不得用重建代替用户确认。

- 完整通过：生成唯一正式来源 `steps-verified.md`，状态改为 `STEPS_VERIFIED`。
- 仍有业务歧义、高风险决定或关键 `UNVERIFIED`：停止，不生成验证版。

### Phase 3：生成里程碑执行计划

读取并执行 `milestone-step-execution` 的 `orchestrated` 模式。只接受 `steps-verified.md`；只重组、排序和分批，不改 STEP 内容。生成 `execution-plan.md`，确保每个 STEP 唯一归属、无遗漏，批次无依赖或资源冲突，并为每个里程碑给出验收闸门。

计划状态为 `IMPLEMENTATION_PLAN_READY`，业务代码仍为 `NOT_STARTED`。不执行任何 STEP，也不写正式 Contract。

### Final Gate

1. 更新 `run.json` 的来源清单与摘要、`stage_results`、映射、依赖、证据绑定、产物角色/摘要和计划归属；每个 Markdown 产物写入流水线协议规定的机器元数据注释。
2. 运行 `python3 scripts/validate.py <run.json>`。
3. 校验失败时，只修机械上唯一确定的问题并重新运行；语义问题返回 `BLOCKED`，不能收敛的结构问题返回 `FAILED_VALIDATION`。
4. 校验通过后才保留 `IMPLEMENTATION_PLAN_READY` 结论并停止。

## 产物

正式分支最多生成以下用户交付产物：

- `requirements-ledger.md`
- `steps-draft.md`
- `step-audit.md`
- `steps-verified.md`
- `execution-plan.md`
- `run.json`

仅在用户补充决定时生成 `decision-addendum.md`。无代码分支用 `steps-provisional.md`，不生成 `steps-verified.md` 或 `execution-plan.md`。`sources/` 只保存无法直接引用本地文件的输入快照，不属于派生交付产物，不得混入业务结论。

## 用户确认边界

阶段间不做重复流程确认。只有以下情况向用户集中提出最小问题并停止：

- 多个合理业务解释；
- 需要选择业务值、权限、状态或范围；
- 安全、数据丢失、不可逆迁移、合规或公开接口破坏；
- 用户要求写业务代码、正式 Contract 或其他未授权位置。

普通实现细节根据已核实项目约定标为 `PLANNED`，或暂记 `UNVERIFIED`；不能伪装成已有事实。`PLANNED` 本身不等于风险，也不应自动触发 `PASS_WITH_RISKS`。只有证据表明某项不确定性可能影响可行性、验收、兼容性或安全性，但仍不阻断规划时，才记录非阻断风险；可在实施时按既有约定唯一发现的位置或内部名称只记为 `PLANNED`。

“现有查询入口、路由、下载约定、构建或测试命令”属于待核实项目事实，不是可自由命名的普通 `PLANNED` 细节。若来源中没有定位但可用明确的实施前停止门安全处理，结果至少为 `PASS_WITH_RISKS`；若缺失会阻止判断核心可行性或验收方式，则走 `DOCUMENT_ONLY` 或停止。

## 最终回复

简明列出：

- 最终结论和状态；
- 需求与验收映射结果；
- 非阻断风险；
- 阻断或待确认项；
- 最终产物路径；
- “业务代码尚未实施（`NOT_STARTED`）”。

不要声称业务语义绝对正确，也不要把仓库证据表述为线上运行证据。

## 自检

- [ ] 四阶段严格按固定顺序执行
- [ ] 每阶段只读取当时必要的 Skill 和资源
- [ ] `DOCUMENT_ONLY` 只生成暂定 STEP 并停止
- [ ] 修正后执行了完整复审
- [ ] 关键 `UNVERIFIED` 未进入正式计划
- [ ] `validate.py` 已真实运行且通过
- [ ] 来源文件摘要、清单重算值与已验证摘要一致
- [ ] `stage_results` 是固定阶段顺序的合法前缀，停止结果后无后续阶段
- [ ] `existing` 引用已用 `source_id` 和 `locator` 绑定到实际来源
- [ ] 索引中的全部产物文件真实存在，内容摘要与机器元数据均通过
- [ ] 没有修改业务代码或正式 Contract
- [ ] 最终状态与产物一致，代码状态为 `NOT_STARTED`

## 资源

- [流水线协议](references/pipeline-contract.md)：阶段输入、产物和 `run.json` 结构。
- [机械校验器](scripts/validate.py)：只校验映射、依赖、引用、来源摘要和计划归属，不判断业务语义。
