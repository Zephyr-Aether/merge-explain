---
name: "merge-explain"
description: "Analyze and resolve git merge conflicts. Use when the user asks to analyze branch differences, understand conflicting changes between branches, auto-resolve merge conflicts, or get a structured merge report."
---

## 能力说明

你可以自己分析两个 Git 分支之间的代码变更，不需要依赖任何外部 API。

**流程**：
1. 获取两个分支的 diff
2. 分析变更语义
3. 判断冲突风险等级
4. 给出合并建议
5. 可选：自动解决冲突

---

## 分析冲突

### 1. 获取 diff

```bash
# 找到共同祖先
MERGE_BASE=$(git merge-base <branch-a> <branch-b>)

# 获取双方的变更
git diff $MERGE_BASE <branch-a>
git diff $MERGE_BASE <branch-b>

# 查看变更文件列表
git diff $MERGE_BASE <branch-a> --name-status
git diff $MERGE_BASE <branch-b> --name-status

# 查看单个文件的详细 diff
git diff $MERGE_BASE <branch-a> -- <file-path>
git diff $MERGE_BASE <branch-b> -- <file-path>
```

### 2. 分析变更

逐文件、逐函数分析每个分支改了哪些内容。重点关注：

- **函数逻辑**：条件判断、循环、异常处理的变化
- **类结构**：新增/删除/修改的类、继承关系
- **API 接口**：参数、返回值、路由的变化
- **配置文件**：环境变量、依赖、配置项的变化
- **数据库模型**：字段、索引、关联关系的变化

可以忽略：代码格式化、变量重命名、注释修改、空白字符。

### 3. 判断风险等级

| 等级 | 定义 | 处理方式 |
|------|------|---------|
| 🟢 **green** | 双方改的是完全不同的文件或函数，逻辑无交集 | 可以安全自动合并 |
| 🟡 **yellow** | 双方改了同一文件/函数但改的是不同方面，没有直接行冲突 | 建议人工复核 |
| 🔴 **red** | 双方改动了同一行、同一判断条件、互斥的配置值 | 必须人工决策，不能自动合 |

### 4. 给出建议

对每个冲突点输出：
- 哪个文件、哪个函数
- 双方各自做了什么（自然语言描述意图）
- 具体的处理建议
- 风险等级

### 5. 输出格式

按以下结构汇报结果，**必须包含实际代码块**，不要只写文字描述：

`````
### 📁 变更文件

<file-path>

#### 🅰️ <branch-a> 的改动
```diff
(实际 diff 内容)
```

#### 🅱️ <branch-b> 的改动
```diff
(实际 diff 内容)
```

---

### ⚡ 冲突分析

#### #1 <file-path>  🟡/🔴/🟢

双方实际改动的代码：

```diff
<<<<<<< HEAD (<branch-b>)
(冲突代码)
=======
(<branch-a> 的代码)
>>>>>>> <branch-a>
```

**建议**：具体可执行的处理建议

---

### 📊 总体判断

**建议**：自动合并 / 人工审查 / 阻塞
**理由**：一句话解释
**冲突代码**：如果只有一处冲突，直接展示完整冲突块
`````

---

## 自动解决冲突

### 触发合并

```bash
# 切换到目标分支
git checkout <branch-b>

# 触发合并（会产生冲突标记）
git merge <branch-a> --no-commit --no-ff

# 查看冲突文件
git diff --name-only --diff-filter=U
```

### 解析冲突标记

冲突文件包含 `<<<<<<<` / `=======` / `>>>>>>>` 标记，格式为：

```
<<<<<<< HEAD
当前分支的代码
||||||| base_sha
共同祖先的代码（diff3 格式才有）
=======
合并进来的分支代码
>>>>>>> branch-a
```

### 解决冲突

对每个冲突块：
1. 看懂两边的代码意图
2. 保留双方的有效逻辑
3. 生成合并后的代码
4. 替换冲突标记

### 应用解决方案

```bash
# 替换文件中的冲突标记为合并后的代码
# 然后提交
git add <resolved-file>
git commit -m "merge: resolve conflicts"
```

**安全措施**：
- 修改前备份文件
- 替换后运行 `python -c "compile(open(file).read(), file, 'exec')"` 检查语法
- 语法不通过则回滚

---

## 列出分支

```bash
git branch
```

---

## 快速测试（验证技能可用）

```bash
echo "--- 测试分析能力 ---"
echo "Base:    return a + b"
echo "Branch A: return a + b + 1"
echo "Branch B: return a * b"
echo ""
echo "分析：共同的函数逻辑被两个分支从不同方向修改"
echo "A 改成了加 1，B 改成了乘法，互斥，属于 🔴 red"
```

## 安全提醒

- `analyze` 阶段是只读的，不修改任何文件
- 解决冲突前务必备份文件
- 替换冲突标记后做语法检查
- RED 等级的冲突建议用户人工决策
