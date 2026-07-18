# Merge-Explain 第二阶段：自动合并方案设计

## 一、竞品分析

### 1. 传统合并工具

| 工具 | 策略 | 局限性 |
|------|------|--------|
| **Git 内置 merge** | 三路合并算法，基于行的文本合并 | 只处理文本冲突，不理解语义。同个变量改两个值直接标冲突 |
| **IDE 合并工具**（VS Code / IntelliJ / Beyond Compare） | 三路对比 UI，人工逐块选择 | 需要手动操作，不支持批量处理，无法理解业务意图 |
| **Git rerere** | 记住之前怎么解决冲突的，自动复用 | 只能复用完全相同的冲突，无法泛化 |

总结：传统工具做的是 **行级/文本级** 合并，不做 **业务语义级** 合并。

### 2. AI 辅助方案

| 项目 | 方式 | 状态 |
|------|------|------|
| **GitHub Copilot / Cursor** | 在 IDE 中看到冲突标记后，AI 建议修改 | 被动触发，不是批量处理，强依赖 IDE |
| **JetBrains AI Assistant** | "Resolve Merge Conflict" 动作，逐块处理 | 强依赖 IntelliJ，不可脚本化 |
| **OpenAI Research / 学术论文** | 用 LLM 分析冲突上下文生成合并代码 | 纯研究，无产品化 CLI 工具 |
| **MergeMate / 同类 CLI** | 少量开源项目，但都停留在"读冲突"阶段 | 缺少"分析→决策→应用"的完整闭环 |

**核心空白**：没有一个 CLI 工具能做到「分析变更语义 → 给出合并建议 → 按建议自动合并代码」的完整链路。

---

## 二、技术方案：增量式冲突解决

### 核心思路

不重新发明 merge 算法。利用 Git 现有的 merge 引擎检测冲突，然后对每个冲突块用 LLM 辅助解决：

```
git merge --no-commit --no-ff
        │
        ▼
  解析冲突标记，提取三路代码
  (base / branch_a / branch_b + 上下文)
        │
        ▼
  对每个冲突块调用 LLM 生成合并代码
  (结合 analyze 阶段的 suggestion 作为参考)
        │
        ▼
  生成预览 diff，等待用户确认
        │
  --apply → 写入文件，语法验证
```

### 数据模型

```python
class ConflictRegion(BaseModel):
    """一个冲突块的三方代码 + 上下文"""
    file_path: str
    base_version: str       # 共同祖先的代码
    branch_a_version: str   # branch_a 的代码
    branch_b_version: str   # branch_b 的代码
    context_before: str     # 冲突前的上下文
    context_after: str      # 冲突后的上下文
    suggestion: str         # 来自 analyze 阶段的建议

class ResolveResult(BaseModel):
    """整个合并操作的完整记录"""
    file_path: str
    status: str             # "resolved" | "skipped" | "failed"
    resolved_code: str      # LLM 生成的合并后代码
    explanation: str        # LLM 解释为什么这么合
    risk: RiskLevel
```

### 安全策略

| 层级 | 措施 |
|------|------|
| **默认只预览** | 不写文件，只输出 unified diff |
| **--apply 才生效** | 用户明确确认后写入 |
| **语法校验** | 写入后自动 `compile()` 检查 Python 语法 |
| **RED 冲突跳过** | 风险等级为 RED 的冲突块不自动处理，留给人工 |
| **Git 备份** | 修改前自动 stash 当前工作区 |
| **每个冲突独立** | 一个冲突失败不影响其他冲突的解决 |

### CLI 接口设计

```
merge-explain resolve <branch-a> <branch-b>
  --from-report <report.json>   # 复用 analyze 的分析结果
  --dry-run                     # 只预览不写入（默认）
  --apply                       # 实际写入文件
  --risk-threshold <yellow>     # 最大自动处理等级（green/yellow，red 永远跳过）
```

### 工作流示例

```bash
# Step 1: 分析冲突
merge-explain analyze feature-a feature-b -o report.json

# Step 2: 审查报告（人工看完）

# Step 3: 自动解决非 RED 冲突
merge-explain resolve feature-a feature-b --from-report report.json

# 如果满意：
merge-explain resolve feature-a feature-b --from-report report.json --apply

# 强制处理所有（包括 RED）：
merge-explain resolve feature-a feature-b --from-report report.json --apply --risk-threshold red
```

---

## 三、与第一阶段的集成

analyze 阶段的输出（`MergeReport`）直接作为 resolve 的输入：

- `conflicts[].file_path` → 告诉 resolve 哪些文件有冲突
- `conflicts[].suggestion` → 作为 prompt 上下文，指导 LLM 如何合并
- `conflicts[].risk` → 决定哪些冲突可以自动解决（RED 跳过）

**这是我们的核心差异点**：竞品工具要么只有分析没有自动解决，要么做了自动合并但没有语义分析。我们把两者串联成了一个完整链路。

---

## 四、实施计划

### Phase 1：数据模型 + 冲突解析
- `models.py` 新增 `ConflictRegion`、`ResolveResult`
- `src/merger.py` 实现 `parse_conflict_markers()` —— 解析 `<<<<<<<` 标记，提取三路代码
- 测试：手动制造冲突文件，验证解析正确性

### Phase 2：单冲突 LLM 解决
- `merger.py` 实现 `resolve_region()` —— 对单个冲突块调用 LLM
- 设计 Resolution Prompt（与 analyze 的 System Prompt 配合）
- 测试：用已知冲突验证合并质量

### Phase 3：整体流水线
- `main.py` 加 `resolve` 命令
- `merger.py` 实现安全机制（stash / 语法检查 / dry-run）
- 测试端到端：从 analyze 到 resolve 的完整流程
