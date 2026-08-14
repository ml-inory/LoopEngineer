# LoopEngineer distill 模式：需求包与设计定稿

本文件是 2026-08-14 需求对齐（grill-me）后的权威存档，对应 `main` 分支实现。

## 目标

让 LoopEngineer 具备“会话蒸馏”能力：定期扫描 Codex 会话历史，鉴别其中的重复性
工作，将其抽象为可安装、可执行、可持续演化的 workflow，并沉淀到 awesome-skills
仓库。用户不再需要人工总结会话经验。

## 关键决策（全部经用户确认）

| 决策点 | 结论 |
|--------|------|
| 产物形态 | 活的 workflow：先批量蒸馏 v1，之后随新会话增量演化；每个产物目录含给人看的 README.md |
| 输出位置 | `~/Codes/awesome-skills/<name>/`（SKILL + hidden helpers + workflow YAML + README.md + CHANGELOG.md），经 `setup.sh --codex` 激活；目录缺失时自动按 `AWESOME_SKILLS_REPO` clone |
| 触发方式 | cron 每日 07:00 / 23:00 headless 运行 + 用户手动触发 |
| 自动化边界 | 半自动：自动巡检/聚类/起草；激活前批量确认；纯增量低风险可自动 |
| 鉴别方式 | 两段式：动作指纹聚类（意图指纹 + 命令/文件/skill + cwd 密度 + 价值信号）→ LLM 命名筛选 |
| 已有 workflow 判重 | 聚类时同时扫描 awesome-skills、Codex/Claude 已安装 skill 与会话引用的项目 workflow；命中已有产物只允许 update（in awesome-skills）或 skip（项目内/已安装），禁止另起新名重复蒸馏 |
| 候选门槛 | 同簇 ≥2-3 会话；高价值单会话可人工决定 |
| 信号库 | 可插拔 extractor：意图、动作、cwd 密度、价值（时长/事件量/resume 代理/跨轮增量） |
| 验证门槛 | 三层：结构校验 → holdout 回溯覆盖率 ≥80% → 激活后影子模式校正 |
| 演化机制 | 增量更新而非重蒸；纯增量自动 + changelog，结构性改动需确认；git commit 即审计/回滚；收敛标记 stable 降噪 |
| 通知通道 | SSH 登录钩子（保底）+ 钉钉 webhook（手机）+ Windows Toast（本机 WSL 自适应）+ tmux 徽标；notifier 可插拔 |
| 入口形态 | 扩展 `$loop-engineer`，新增 `distill` 模式 |
| 数据源 | v1 仅 `~/.codex/sessions`（Codex）；Claude 留作后续 |

## 验收

1. 首次扫描能建立全量会话索引，之后增量识别新增/变长会话；
2. 候选簇检出合理（Magnetar 18 会话、moon-bridge 9 会话等真实簇可被识别）；
3. 蒸馏产物目录含给人看的 README.md（`# <name>` + 用法 / 安装与更新 / 维护），并通过结构校验 + holdout ≥80% 回溯；
4. 低风险更新自动落地并生成 changelog，结构性更新需确认；
5. 通知在四种通道按环境可用性送达，钉钉消息带加签；
6. 全流程可离线 dry-run 验证，不产生外部副作用。

## 安全约定

- 钉钉 webhook / 密钥只存在于 `config/distill.env`（gitignore + 0600），禁止进代码与 git 历史；
- 通知失败（网络/凭据缺失）自动降级：登录钩子 + inbox 保底，不阻塞蒸馏主流程。
