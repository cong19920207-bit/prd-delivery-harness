# PRD Delivery Harness

一个总控 Skill 加四个可独立调用的阶段 Skill，用于把 PRD 审查、STEP 拆解、STEP 复审修正和里程碑计划串成一次稳定执行。

## 包含内容

| 目录 | 用途 | 可独立调用 |
|---|---|---|
| `prd-delivery-harness/` | 总控：按固定顺序执行全部四阶段 | 是 |
| `prd-review/` | 审查 PRD、核验来源并建立需求台账 | 是 |
| `prd-to-steps/` | 把已审查需求拆成可执行 STEP | 是 |
| `step-doc-review/` | 审查、修正并完整复审 STEP | 是 |
| `milestone-step-execution/` | 把已验证 STEP 编排为里程碑计划 | 是 |

总控内部顺序固定为：

```text
prd-review
→ prd-to-steps
→ step-doc-review
→ milestone-step-execution
```

出现业务歧义、关键来源缺失、机械校验失败或高风险决定时会阻断；普通阶段间不会反复要求用户确认。该总控只生成规划文档，不修改业务代码或正式 Contract。

## 安装

克隆一次仓库，再一次复制五个 Skill 目录：

```bash
git clone https://github.com/cong19920207-bit/prd-delivery-harness.git
mkdir -p ~/.codex/skills
cp -R prd-delivery-harness/{prd-delivery-harness,prd-review,prd-to-steps,step-doc-review,milestone-step-execution} ~/.codex/skills/
```

也可以从 GitHub 下载一个 ZIP，解压后将上述五个目录复制到 `~/.codex/skills/`。因此只需下载一个仓库，但五个目录都需要保留：总控负责串联，四个阶段 Skill 仍可单独调用。

安装后重启 Codex，或新建任务使 Skill 列表重新加载。

## 使用

完整流程需显式调用：

```text
$prd-delivery-harness 请根据 path/to/prd.md 生成已验证 STEP 和里程碑计划。
```

也可以按需独立调用，例如：

```text
$prd-review 请只审查 path/to/prd.md。
$step-doc-review 请复审并修正 path/to/steps.md。
```

每个 Skill 的触发条件、输入输出和停止规则以对应目录中的 `SKILL.md` 为准。

## 完整性校验

在仓库根目录运行：

```bash
shasum -a 256 -c SHA256SUMS
```

`VALID` 仅表示某次运行的结构、映射、引用、依赖和摘要通过机械门禁，不代表业务语义绝对正确。

## 许可

当前仓库尚未附带开源许可证；公开可见不等于自动授予复制、修改或分发许可。如需对外开放复用，请由仓库所有者选择并添加合适的 LICENSE。
