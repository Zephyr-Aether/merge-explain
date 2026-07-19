# Merge-Explain

**可解释性合并工具 — 先理解，再合并**

AI 生成代码越来越普遍，但多个分支各有大量改动时，开发者看不懂 Diff，合并冲突不敢处理。

Merge-Explain 不做黑盒自动合，而是先分析双方变更语义，输出风险等级和处理建议，用户逐块决策后再执行合并。

---

## 安装

```bash
# 1. 克隆项目
git clone <你的仓库地址>
cd merge-explain

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 Key（兼容 OpenAI / DeepSeek / 通义千问）

# 3. 一键安装所有依赖
./run.sh install
```

`./run.sh install` 会自动：
- 创建 Python 虚拟环境（`.venv/`）
- 安装 Python 依赖（FastAPI / GitPython / OpenAI SDK 等）
- 安装前端依赖（React / Vite / TypeScript / shadcn/ui）

---

## 启动

### 开发模式（前后端热更新，推荐）

```bash
./run.sh dev
```

- 前端：Vite 开发服务器 → `http://localhost:5173`
- 后端：FastAPI → `http://localhost:13920`
- Vite 自动将 `/api/*` 请求代理到后端

### 仅启动后端 API

```bash
./run.sh api
```

后端 API 地址：`http://localhost:13920`

---

## 使用流程

```
① 选择仓库 → ② 选择分支 → ③ 分析冲突 → ④ 查看结果
```

### 1. 选择仓库
点击路径栏用目录浏览器选择仓库目录，或直接粘贴路径。最近打开过的仓库会显示在下方供快速切换。

### 2. 选择分支
选两个特性分支和一个目标分支（自动检测 main / master / develop）。提供交换 A/B 按钮快速互换。按 `Enter` 直接进入分析。

### 3. 分析冲突
LLM 分析双方变更语义，生成风险等级和处理建议。分析过程中显示骨架屏预览结果区域布局。

### 4. 查看结果

**风险总览** — 红/黄/绿三色卡片展示冲突分布，点击可筛选对应级别的冲突。

**分支变更摘要** — 显示两个分支各自改了哪些文件、什么函数、什么改动。

**冲突列表** — 默认全部展开。每张冲突卡片包含：
- 风险图标 + 文件路径 + 位置计数（3/12）
- 分支 A / 分支 B 的具体操作描述
- Diff 代码片段（CodeMirror 展示，行号 + 红绿高亮 + 语法着色）
- LLM 处理建议
- 查看 Diff 按钮 → 打开并排双面板对比弹窗
- 决策按钮：**采用 A / 采用 B / 使用 LLM 建议 / 手动编辑**

**决策流程**

```
逐冲突选边 → 预览合并结果 → 审查预览详情 → 应用修改 → git diff 审查 → 手动 commit
```

- 采用 A / 采用 B — 直接使用对应分支的版本
- 使用建议 — 由 LLM 生成合并代码
- 手动编辑 — 弹出 CodeMirror 编辑器（行号 + 语法提示），用户自行编写合并代码
- 预览合并结果 — 展示每个文件如何被解决
- 应用修改 — 写入文件但不自动提交，用户 `git diff` 审查后再手动 `commit`

**Diff 弹窗**
- 双面板并列对比：target vs branchA / target vs branchB
- 词级 diff 高亮（LCS 算法，逐词对比，不等同行）
- 冲突导航：上一处 / 下一处 按钮跳转
- 只读 CodeMirror 编辑器展示 + 语法着色

---

## 项目结构

```
merge-explain/
├── server.py                # FastAPI 后端
├── frontend/                # React + Vite + TypeScript
│   └── src/
│       ├── App.tsx          # 主组件（全部 UI 逻辑）
│       ├── api.ts           # API 客户端
│       ├── index.css        # Tailwind + shadcn/ui 主题
│       ├── lib/utils.ts     # cn() 工具函数
│       └── components/ui/   # shadcn/ui 组件
├── src/                     # 核心 Python 代码
│   ├── analyzer.py          # LLM Prompt + API 调用
│   ├── git_ops.py           # Git diff 获取 + Token 截断
│   ├── merger.py            # 冲突标记解析 + 决策合并
│   └── models.py            # Pydantic 数据模型
├── .env.example
└── run.sh                   # 启动脚本
```

---

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/load` | 加载仓库，返回分支列表 |
| `POST /api/analyze` | 分析两个分支的冲突 |
| `POST /api/resolve` | 执行合并（支持逐文件决策） |
| `POST /api/list-dirs` | 列出目录内容（目录浏览器用） |
| `POST /api/compare` | 对比两个版本的 Diff |
| `POST /api/pick-folder` | macOS 原生文件夹选择器 |

---

## 技术栈

- **后端**: Python 3.9+ / FastAPI / GitPython / OpenAI SDK
- **前端**: React 18 / Vite / TypeScript / shadcn/ui / Tailwind CSS / CodeMirror
- **UI 组件**: shadcn/ui（Button / Card / Dialog / Select / Badge / Tabs / ScrollArea / AlertDialog）

## 安全策略

- analyze 阶段只读，不碰任何文件
- resolve 默认预览（dry-run），不写文件
- 应用修改后不自动提交，用户 `git diff` 审查后再手动 commit
- 应用前弹 AlertDialog 确认框，列出要修改的文件
- 预览结果可视化，展示每个文件如何解决
- 决策按钮支持撤销，随时可以反悔
- RED 级别冲突跳过自动解决
- `git merge --abort` 兜底恢复工作区
