# PRD Delivery Harness 流水线协议

本协议只定义四阶段交接和机械门禁，不判断业务语义，也不是通用工作流引擎。

## 1. 固定阶段与停止规则

| 阶段 | 成功状态 | 成功产物 |
|---|---|---|
| `prd-review` | `PRD_READY` | `requirements_ledger` |
| `prd-to-steps` | `STEPS_DRAFTED` | `steps_draft` |
| `step-doc-review` | `STEPS_VERIFIED` | `step_audit`、`steps_verified` |
| `milestone-step-execution` | `IMPLEMENTATION_PLAN_READY` | `execution_plan` |

`stage_results` 必须是上述顺序的唯一前缀。成功阶段只能认领表中精确产物；不能提前认领未来产物，也不能重复认领。

- `PASS` / `PASS_WITH_RISKS`：进入该阶段的成功状态。
- `DOCUMENT_ONLY`：只允许 `prd-review → PRD_DOCUMENT_ONLY` 和 `prd-to-steps → PROVISIONAL_STEPS_READY`；产物分别为台账和 `steps_provisional`，随后停止。
- `BLOCKED` / `FAILED_VALIDATION`：保持前一状态，当前阶段只可保留本阶段允许的诊断产物，且不得出现后续 `stage_results` 或未来产物。

正式终态的顶层 `phase` 为 `final`；只要任一阶段是 `PASS_WITH_RISKS`，顶层 outcome 也必须是 `PASS_WITH_RISKS`。暂定或停止终态的顶层 `phase/state/outcome` 必须与最后阶段一致。

## 2. 来源与原始快照

`source_manifest` 为非空数组，每项包含唯一 ID、来源类型、实际文件路径和内容 SHA-256：

```json
{"id":"prd","source":"PRD","sha256":"64 lowercase hex characters","path":"/absolute/path/prd.md"}
```

来源类型只允许 `USER_DECISION`、`PRD`、`CONTRACT`、`REPO_BASELINE`、`RUNTIME`。`PLANNED` 和 `UNVERIFIED` 不是已读取文件来源。

对每项生成 `ID<TAB>source<TAB>sha256`，按完整行排序，以 UTF-8 `\n` 连接且末尾不加换行，再计算 `source_digest`。每个门禁通过时复制到 `validated_source_digest`；二者不同表示旧验证失效。校验器会重读文件并重算摘要，而不是只比较两个字段。

### 非文件输入

对话文本粘贴、URL 响应、OCR 结果或初始用户决定没有稳定路径时，先写入运行目录的 `sources/`：

- 文本粘贴按收到的原始 UTF-8 字节保存；不整理空行、缩进、代码块或表格。需要规范化时另存派生副本，清单仍绑定 raw snapshot。
- URL 只保存本轮实际取得的原始响应正文，并在可选 `origin` 记录最终 URL；不可访问时返回 `FAILED_VALIDATION`，不得按记忆补写。
- OCR 保存实际识别结果并在台账标记识别风险；不得把润色文本冒充原始识别结果。
- 不保存认证头、Cookie、密钥或与输入无关的页面内容。

快照是来源证据，不进入 `artifacts`。

## 3. STEP 引用

需求和验收记录只能来自 `USER_DECISION`、`PRD` 或 `CONTRACT`。每个 STEP 的 `requirement_ids` 和 `acceptance_ids` 都必须非空，且所有需求/验收至少映射一个 STEP。

引用状态只用 `existing`、`planned`、`unverified`；`kind` 只用：

- `path`：`value` 与 `locator` 规范化后必须严格相等，且严格指向 `source_id` 绑定的来源文件；禁止绝对路径和 `..`。
- `symbol`：`locator` 必须是具体标识符；`value` 只能等于该标识符，或使用与绑定文件严格匹配的 `path::symbol` / `symbol in path`。按标识符边界在来源正文中查找，不能用通用关键字或子串背书。
- `contract`：`value` 必须与精确条款 `locator` 严格相等，或为 `文件名::精确条款`；条款须实际出现在绑定来源中。

每个 `existing` 引用必须包含 `source_id`、`locator`、来源类型和布尔型 `critical`。`planned` 使用 `PLANNED`，`unverified` 使用 `UNVERIFIED`。关键 `unverified` 不得进入 `steps-verified.md` 或正式计划。

## 4. `run.json` 核心结构

```json
{
  "schema_version": 2,
  "run_id": "20260801T120000Z-example",
  "phase": "final",
  "state": "IMPLEMENTATION_PLAN_READY",
  "outcome": "PASS",
  "code_status": "NOT_STARTED",
  "source_digest": "64 lowercase hex characters",
  "validated_source_digest": "same digest",
  "source_manifest": [
    {"id":"prd","source":"PRD","sha256":"...","path":"/path/prd.md"},
    {"id":"example-file","source":"REPO_BASELINE","sha256":"...","path":"/repo/app/example.py"}
  ],
  "artifacts": {
    "requirements_ledger":{"path":"requirements-ledger.md","role":"requirements_ledger","sha256":"..."},
    "steps_draft":{"path":"steps-draft.md","role":"step_draft","sha256":"..."},
    "step_audit":{"path":"step-audit.md","role":"step_audit","sha256":"..."},
    "steps_verified":{"path":"steps-verified.md","role":"step_verified","sha256":"..."},
    "execution_plan":{"path":"execution-plan.md","role":"execution_plan","sha256":"..."},
    "run":{"path":"run.json","role":"run_index"}
  },
  "stage_results": [
    {"phase":"prd-review","state":"PRD_READY","outcome":"PASS","source_digest":"...","artifact_keys":["requirements_ledger"]},
    {"phase":"prd-to-steps","state":"STEPS_DRAFTED","outcome":"PASS","source_digest":"...","artifact_keys":["steps_draft"]},
    {"phase":"step-doc-review","state":"STEPS_VERIFIED","outcome":"PASS","source_digest":"...","artifact_keys":["step_audit","steps_verified"]},
    {"phase":"milestone-step-execution","state":"IMPLEMENTATION_PLAN_READY","outcome":"PASS","source_digest":"...","artifact_keys":["execution_plan"]}
  ],
  "requirements": [{"id":"RQ-1","source":"PRD"}],
  "acceptance": [{"id":"AC-1","source":"PRD"}],
  "steps": [{
    "id":"STEP-001",
    "requirement_ids":["RQ-1"],
    "acceptance_ids":["AC-1"],
    "depends_on":[],
    "references":[{
      "kind":"path","value":"app/example.py","status":"existing",
      "source":"REPO_BASELINE","source_id":"example-file",
      "locator":"app/example.py","critical":true
    }]
  }],
  "execution_plan":{"milestones":[{"id":"M1","step_ids":["STEP-001"]}]}
}
```

`run.json` 是索引，不保存完整 PRD 或 STEP 正文。每个里程碑的 `step_ids` 必须非空；每个 STEP 在全部里程碑中恰好出现一次。

## 5. 产物绑定

除 `run.json` 外，每个 Markdown 产物的首个非空行是单行 JSON 元数据，字段只保留真实性链必需项：

```markdown
<!-- prd-delivery-harness-meta {"schema_version":2,"run_id":"...","artifact":"steps_verified","owner_phase":"step-doc-review","state":"STEPS_VERIFIED","outcome":"PASS","code_status":"NOT_STARTED","source_digest":"..."} -->
# 已验证 STEP

> Harness: phase=step-doc-review; state=STEPS_VERIFIED; outcome=PASS; code_status=NOT_STARTED
```

校验器重算 artifact SHA-256，并核对 `owner_phase/state/outcome/code_status/source_digest` 与对应 `stage_results`。固定 `> Harness:` 摘要必须逐字匹配，防止人类可读结论与 `run.json` 的 `PASS/BLOCKED` 或代码状态矛盾。

不再用正文长度或“每个 ID 必须在正文任意位置出现”的启发式规则冒充语义验证；业务内容仍由 Phase 2 完整复审。

## 6. 最终机械门禁

运行：

```bash
python3 scripts/validate.py /absolute/path/to/run.json
```

只有退出码 `0` 且输出 `VALID` 才通过。主要错误包括：

- 来源：`E_SOURCE_FILE_DIGEST_MISMATCH`、`E_SOURCE_DIGEST_CONTENT_MISMATCH`
- 产物：`E_ARTIFACT_NOT_FOUND`、`E_ARTIFACT_DIGEST_MISMATCH`、`E_ARTIFACT_METADATA_MISMATCH`
- 阶段：`E_STAGE_ORDER`、`E_STAGE_ARTIFACT_FORBIDDEN`、`E_STAGE_STOP_STATE`
- 映射：`E_STEP_REQUIREMENTS_EMPTY`、`E_STEP_ACCEPTANCE_EMPTY`、`E_REQUIREMENT_UNMAPPED`、`E_ACCEPTANCE_UNMAPPED`
- 依赖与计划：`E_DEPENDENCY_CYCLE`、`E_MILESTONE_STEPS_EMPTY`、`E_STEP_ASSIGNED_MULTIPLE`
- 引用：`E_REFERENCE_VALUE_SOURCE_MISMATCH`、`E_REFERENCE_LOCATOR_NOT_FOUND`、`E_CRITICAL_UNVERIFIED`

脚本只判断这些机械不变量；`VALID` 不等于业务语义绝对正确。
