# Merge-Explain

**可解释性 AI 合并工具 — 先理解，再合并**

AI 生成代码越来越普遍，但多个分支各自有大量改动时，开发者看不懂 Diff，合并冲突不敢处理。

Merge-Explain 不做黑盒自动合，而是先分析双方变更语义，输出风险等级和处理建议，按确认后逐块自动合并。

---

## 快速开始

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 Key（兼容 OpenAI / DeepSeek / 通义千问）

# 2. 安装
python3 -m venv .venv
source .venv/bin/activate
./run.sh install

# 3. 启动
./run.sh dev
```

浏览器打开 `http://localhost:5173`。

---

## 使用流程

```
① 选择仓库 → ② 选择分支 → ③ 分析冲突 → ④ 查看结果
```

1. **选择仓库** — 点击「选择文件夹」用 macOS 原生对话框选目录，或直接在路径栏输入
2. **选择分支** — 选两个特性分支和一个目标分支（默认 main）
3. **分析冲突** — 点「分析冲突」，LLM 分析变更语义
4. **查看结果** — 风险等级卡片 + 可展开的冲突详情 + 侧边对比 Diff

勾选「应用修改并提交合并」后点「自动解决冲突」→ LLM 逐块生成合并代码 → 写入文件 → git commit。

---

## 命令

| 命令 | 说明 |
|------|------|
| `./run.sh dev` | 开发模式（Vite 热更新 + FastAPI 后端） |
| `./run.sh ui` | 生产模式（需先 `./run.sh build`） |
| `./run.sh install` | 安装后端 pip 依赖 + 前端 npm 依赖 |
| `./run.sh build` | 构建前端生产版本 |

---

## 项目结构

```
merge-explain/
├── server.py              # FastAPI 后端
├── frontend/              # React + Vite + TypeScript
│   └── src/
│       ├── App.tsx        # 主组件（仓库/分支/冲突/Diff）
│       ├── App.css        # 暗色主题样式
│       └── api.ts         # API 客户端
├── src/                   # 核心 Python 代码
│   ├── main.py            # CLI 入口
│   ├── analyzer.py        # LLM Prompt + API 调用
│   ├── git_ops.py         # Git diff 获取
│   ├── merger.py          # 冲突标记解析 + 自动合并
│   ├── reporter.py        # 报告输出
│   └── models.py          # Pydantic 数据模型
├── tests/                 # 39 个测试
├── run.sh                 # 启动脚本
└── pyproject.toml         # Python 依赖
```

---

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/load` | 加载仓库，返回分支列表 |
| `POST /api/analyze` | 分析两个分支的冲突 |
| `POST /api/resolve` | 自动解决冲突 |
| `POST /api/list-dirs` | 列出目录内容 |
| `POST /api/compare` | 侧边对比两个版本的 Diff |
| `POST /api/pick-folder` | macOS 原生文件夹选择器 |

---

## 技术栈

- **后端**: Python 3.9+ / FastAPI / GitPython / OpenAI SDK
- **前端**: React 18 / Vite / TypeScript
- **CLI**: Typer / Rich / Pydantic v2

## 安全策略

- analyze 阶段只读，不碰任何文件
- resolve 默认预览，`--apply` 或勾选应用才写入
- 写入前自动备份，语法检查不通过自动回滚
- RED 级别冲突跳过自动解决
- `git merge --abort` 兜底恢复
