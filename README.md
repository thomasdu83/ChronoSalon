# ChronoSalon（史境群聊）

ChronoSalon（史境群聊）是一个面向学生个人使用的历史人物 AI 群聊学习工具。

学生输入一个历史主题后，系统自动创建主题聊天室，邀请相关历史人物、群体角色和历史助手进入群聊。学生可以像普通群聊一样提问、@人物、打断和追问；历史人物之间也会围绕主题自动对话。产品目标是用更有趣、更有结构的方式帮助学生理解历史。

## 产品定位

- 面向学生个人使用。
- 不做教师端。
- 不做学校管理场景。
- 一个主题一个聊天室。
- 支持历史现场聊天室和跨时空讨论聊天室。
- 核心入口是“智能建房”：输入主题，自动生成聊天室配置。

## 核心体验

```text
学生输入：安史之乱
↓
系统自动生成聊天室
↓
历史助手开场并点名
↓
安禄山、李隆基、杨国忠等人物群聊式回应
↓
学生可以 @ 指定人物追问
↓
历史助手解释关键词、推动冲突、轻量总结
↓
系统生成学习回顾和复习题
```

## 当前状态

当前阶段：MVP 骨架已实现。

已完成：

- 项目定位。
- MVP 边界。
- 智能建房器设计。
- 聊天室类型设计。
- 人物系统设计。
- 群聊机制设计。
- 历史助手定位。
- 前端页面方案。
- 模型调用流程草案。
- 数据模型草案。
- 后端离线 MVP：智能建房、对话编排、人物群聊响应、学习回顾。
- 静态前端原型：主题输入、建房预览、群聊界面、学习线索卡片。
- 自动化测试。

详细计划见 [PROJECT_PLAN.md](./PROJECT_PLAN.md)。

## 本地运行

启动后端 API 和前端页面：

```powershell
cd F:\Thomas\QuantSystem\ChronoSalon
python chronosalon_cli.py serve --host 127.0.0.1 --port 8000
```

然后打开：

```text
http://127.0.0.1:8000
```

命令行演示：

```powershell
python chronosalon_cli.py build-room 安史之乱
python chronosalon_cli.py demo-chat 安史之乱 '@安禄山 你为什么起兵？'
python chronosalon_cli.py check-config
```

前端原型：

```text
打开 frontend/index.html
```

如果直接打开静态 HTML，前端会在后端不可用时使用演示数据；启动服务后会调用真实 `/api/*` 接口。

## API

核心接口：

- `GET /api/health`
- `POST /api/rooms/build`
- `POST /api/chat`
- `POST /api/review`

`/api/chat` 默认会尝试按 `src/config/model_config.yaml` 和 `src/.env` 使用真实大模型；如果密钥缺失、网络失败或模型异常，会自动退回本地离线 responder，保证主流程可用。

## 测试

```powershell
python -m pytest -q
node --check frontend\scripts\app.js
```

## 建议开发顺序

1. 建立工程骨架。
2. 实现智能建房器 MVP。
3. 建立人物卡 schema 和第一批人物卡。
4. 实现后端群聊编排 API。
5. 实现前端首页、建房预览和聊天室。
6. 实现学习回顾。
7. 优化史实约束和群聊体验。

## 技术栈建议

初期建议：

- 前端：React + TypeScript + Vite。
- 后端：Python FastAPI。
- 数据：先用本地 JSON / SQLite，后续升级 PostgreSQL。
- AI 服务：分为智能建房器、对话编排器、人物发言生成器、历史助手生成器、学习回顾生成器。

## 大模型配置

项目已有：

- `src/.env`：存放大模型 API key 等敏感环境变量，仅用于本地环境。
- `src/config/model_config.yaml`：模型设置文件模板，用于配置智能建房器、对话编排器、人物发言、历史助手、学习回顾等模块的模型参数。

后续开发中不得在代码、文档或日志中暴露 `.env` 内的真实密钥。
