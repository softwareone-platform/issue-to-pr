<!-- translated from README.md, source sha256 07c526e69f72e4c41e40eaad7d74a011557e7888003eb2c32427bc832a8ca93f; see CLAUDE.md "Translations of the root README" before editing -->
# issue-to-pr

![resolve-issue-dashboard 正在展示一次运行到一半的 pipeline](docs/resolve-issue-dashboard.png)

<sub>`issue-to-pr-pipeline` 中的 `resolve-issue-dashboard` 正在跟踪一次运行在 pipeline 中的进度（示意用的示例数据）。</sub>

<div align="center">

[![CI](https://img.shields.io/github/actions/workflow/status/softwareone-platform/issue-to-pr/checks.yml?branch=main&label=CI)](https://github.com/softwareone-platform/issue-to-pr/actions/workflows/checks.yml) [![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.143%2B-blue)](#install) [![License: Apache-2.0](https://img.shields.io/github/license/softwareone-platform/issue-to-pr)](LICENSE)

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

</div>

<a id="overview"></a>
## 🧭 概览

一组 [Claude Code](https://claude.com/claude-code) plugin：由 skill 和 subagent 组成，把一个工单从诊断一路推进到经过审查的 pull request，并附带支撑这一流程的审查、测试编写和维护工具。

<a id="install"></a>
## 📦 安装

需要支持 plugin 的 Claude Code。依赖的自动安装以及启用时的依赖处理，需要上方 Claude Code badge 所示的版本；更旧的版本请改用下方逐个安装的清单。

这些 plugin 通过 [`tundra`](https://github.com/softwareone-platform/tundra) marketplace 发布；本 repo 存放的是它们的源代码，本身不是 marketplace。

安装 `issue-to-pr-pipeline` 即可：它把另外三个 plugin 声明为依赖，Claude Code 会从同一个 marketplace 自动解析并安装它们，并在安装输出的末尾列出新增了哪些。

```
/plugin marketplace add https://github.com/softwareone-platform/tundra.git
/plugin install issue-to-pr-pipeline@tundra
```

另一种方式：如果你的 Claude Code 比 badge 所示的版本旧（因而无法自动安装依赖），或者你只想要其中几个 plugin，就逐个安装：

```
/plugin marketplace add https://github.com/softwareone-platform/tundra.git
/plugin install disconfirm-first@tundra
/plugin install pr-lifecycle@tundra
/plugin install test-authoring@tundra
/plugin install issue-to-pr-pipeline@tundra
```

然后运行 `/reload-plugins` 来启用；它也会重新解析所有缺失的依赖。只安装你需要的 plugin 即可：除了构建在另外三个之上的 `issue-to-pr-pipeline`，其余都可以独立使用。

第三方 marketplace 的自动更新默认关闭。要自动接收新版本，请打开 `/plugin` → Marketplaces → `tundra` → Enable auto-update。

**从旧的 `itpr` marketplace 迁移。** 本 repo 过去是一个名为 `itpr` 的 marketplace，现在已经不是了：刷新 `itpr` 会失败，从它安装的 plugin 也会停止加载。请运行 `/plugin marketplace remove itpr`（这也会卸载从它安装的 plugin），然后添加 `tundra` 并按上面的方式安装。每个 plugin 只应从一个 marketplace 安装。

如果要基于克隆下来的 repo 开发这些 plugin，请用 `claude --plugin-dir ./plugins` 直接从 working tree 加载，而不是把克隆添加为 marketplace。

<a id="plugins-at-a-glance"></a>
## 🗂️ Plugin 一览

| Plugin | 提供什么 |
|---|---|
| [`disconfirm-first`](#disconfirm-first) | 在 issue、计划和代码三个层级进行对抗式审查 |
| [`pr-lifecycle`](#pr-lifecycle) | Pull request 的生命周期（Azure DevOps 或 GitHub） |
| [`test-authoring`](#test-authoring) | 测试编写：单元测试和集成测试 |
| [`issue-to-pr-pipeline`](#issue-to-pr-pipeline) | 从 issue 到 PR 的编排（串联上面三个） |

任何 skill 都可以用 `/<plugin>:<skill>` 调用，或者直接描述你要做的事：每个 skill 都会根据自然语言自动触发。

<a id="how-they-fit-together"></a>
## 🧩 它们如何协同

审查、测试和 PR 这三个 plugin 各自都可以单独使用。`issue-to-pr-pipeline` 把它们组合起来：`resolve-issue` 带着一个工单走完下方的 pipeline，以计划批准作为关卡，并在每个该由你决定的地方再次暂停；每个阶段都交给负责它的 skill 执行，包括审查、测试和 PR 的 skill，以及 Claude Code 内置的 `security-review`。

```
  PLAN
   ●─  1  Fact-check issue    does the bug actually hold in the code? (may ask)
   │
   ●─  2  Resolve decisions   settle open design decisions before planning (may ask)
   │
   ●─  3  Draft plan          sketch how the fix will be made
   │
   ●─  4  Harden plan         pre-mortem the plan, fix its design risks (may ask)
   │
   ◆─  5  Plan approval       you approve the plan before any code changes (always waits)
  BUILD
   ●─  6  Implement fix       make the code change
   │
   ●─  7  Write tests         cover the change with tests, then commit them (may ask)
   │
   ●─  8  Review security     scan the diff for vulnerabilities (may ask)
   │
   ●─  9  Review fix          pressure-test that the fix resolves the issue (may ask)
   │
   ●─ 10  Open PR             raise the pull request (always waits)
  DONE
   ◉─ 11  Done                pipeline complete, PR awaiting review
```

**只有“起草计划”和“修改代码”这两步不需要你参与。** 有两个停止点是无条件的：计划批准，以及创建 PR 前的确认；其他每一步都可能暂停来询问你，例如一个它被禁止自行猜测的设计决定、一个需要你处置的风险、一个测试类型的判断，或一个质量警示。每次等待都没有时限：暂停的运行会一直停在那里，直到有人回答。它会在 `state.md` 中写明自己在等什么，`resolve-issue-dashboard` 也会显示出来。按每个停止点存在的理由分组的完整说明，见 [resolve-issue 的 README](plugins/issue-to-pr-pipeline/skills/resolve-issue/README.zh-CN.md#where-the-run-stops-for-you)。

**一次运行的成本。** 大部分步骤都交给 subagent 执行，而测试和审查步骤各自要承担一个编写者加一个独立验证者的成本，所以即使是一行的修复也要为这一对付费。pipeline 中没有任何环节能报告自己的花费：编排器看不到自己的 token 用量，仪表盘上的计数器反映的是用量而不是价格。实际耗时同样给不出可靠的数字：一次运行的耗时，大部分是它在关卡前等待 **你** 的时间，所以这里不给出任何时长。请观察你第一次运行的用量，而不是相信任何估算。

整个运行过程都会在 `.claude/resolve/<ticket>/` 中保存检查点，因此新的 session 可以接着运行。`resolve-issue-dashboard` 实时展示一次运行的情况；`resolve-issue-learnings` 则从多次运行中提炼 pipeline 学到的经验。

**有一样东西会写到你调用它的 repo 之外。** `resolve-issue` 会把候选经验追加到 `~/.claude/resolve-learnings/candidates.md`，而 `resolve-issue-learnings` 会把通过验证的那些提升到 `~/.claude/resolve-learnings/conventions.md`，供之后的运行遵循。两者都是用户全局、所有 repo 共享的纯 Markdown 文件，你可以阅读、编辑或删除；它们也是这些 plugin 在 repo 之外写入的唯一文件。其他所有东西都留在那个 repo 的 `.claude/` 中；仪表盘会读取 `~/.claude/projects/`，但从不写入。

<a id="skills"></a>
## 🛠️ Skill

### disconfirm-first

三个对抗式审查者，每个层级一个：各自负责一种不同的产物，在它流向下游之前对它进行压力测试。

- **review-issue-fact**：在规划任何修复之前，对照代码库对一个 *issue*（bug 报告、story 或事故描述）进行事实核查；针对每一条论断给出判定，并建议 HALT / PROCEED / RESOLVE。
- **review-plan-risk**：对一份 *计划 / 规格 / SKILL.md* 进行事前验尸，自动修复它判定为真实的设计风险，并在报告前由独立的验证者核验每个修复。
- **review-code-risk**：在 PR 创建之前，对照 issue 和计划，以对抗方式审查一个 *已实现的修复*；自动修复变更文件中的真实风险，并重新运行构建和测试。

### pr-lifecycle

不绑定团队的 PR 生命周期，支持 Azure DevOps 或 GitHub：平台在运行时从 git remote 检测。两个 skill 在做出任何对外变更之前都会先确认。

- **open-pr**：创建一个 PR，标题和描述遵循 *你自己* 以往 PR 的约定；这些约定在运行时从你已合并的 PR 中学来，你的 PR 太少、看不出规律时，再参考其他人的。
- **resolve-pr-comments**：获取一个 PR 的评审评论线程，逐一判断如何处理，起草代码修复和回复，并在你确认一次之后 commit、push、回复，以及更新评论线程的状态。

### test-authoring

把测试编写交给编写者和验证者 subagent（共 8 个）。agent 遵守的规则随 plugin 一起提供，并直接从 plugin 读取，因此不会有任何东西被复制到你的 repo。如果运行过一次 `setup-test-context`，它还会把这个 repo 的跨层映射缓存下来；没有它，每个流程仍会从最近的相邻测试学习约定，照常运行。完整架构见 [plugin README](plugins/test-authoring/README.zh-CN.md)。

- **setup-test-context**：对 repo 做一次测试概况分析；把它的跨层映射以约定的形式缓存在 `.claude/conventions/tests/` 下。可以重复运行，重新运行就是刷新。
- **scan-test-gaps**：找出没有测试的代码和过时的测试，然后反复委派生成与更新。
- **add-{unit,integration}-test**：为变更过的源代码或指定的目标生成测试。
- **update-{unit,integration}-test**：分两个阶段（审计 → 执行）刷新已有的测试。

### issue-to-pr-pipeline

从 issue 到 PR 的编排。依赖于 `disconfirm-first`、`test-authoring` 和 `pr-lifecycle`。

- **resolve-issue**：带着一个工单走完整个 pipeline（见 [上方](#how-they-fit-together)），以计划批准作为关卡，并在每个该由你决定的地方再次暂停；可以从 `.claude/resolve/<ticket>/` 接着运行。
- **resolve-issue-dashboard**：一个实时、只读的仪表盘，通过跟踪 transcript 和 `state.md`，展示一次运行的 pipeline 步骤、每个 subagent 的活动、各项指标，以及它停在哪个关卡。只观察，从不驱动运行。
- **resolve-issue-learnings**：收集运行过程中记录下的跨 repo 经验，以当前的 skill 为基准逐一验证，并把通过的写入一个 pipeline 下次会读取的约定文件。

<a id="prerequisites"></a>
## 📋 前提条件

plugin 本身只是 Markdown 和 JSON，没有任何东西需要构建。少数 skill 会连接外部服务，或需要本地的运行环境；只需安装你实际使用的 plugin 所需要的：

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) 以及 `azure-devops` 扩展（`az extension add --name azure-devops`）：`pr-lifecycle` 在 Azure DevOps remote 上需要它，通过 `az repos` / `az devops` 操作。
- [GitHub CLI](https://cli.github.com/)（`gh`，需已登录）：`pr-lifecycle` 在 GitHub remote 上需要它，通过 `gh pr` / `gh api` 操作。
- 在 Claude Code 的 MCP 设置中加入 [Atlassian MCP Server](https://www.npmjs.com/package/@anthropic-ai/atlassian-mcp)：可选；为 `review-issue-fact`、`resolve-issue` 启用 Jira 集成，并让 `open-pr` 加上 Jira 链接。没有它时，这些 skill 会改用粘贴的链接或纯文本。
- PATH 上的 [Python](https://www.python.org/downloads/)：**可选**，而且只有 `resolve-issue-dashboard` 需要，它会在本地运行一个只用标准库的服务器（不需要 `pip install`，也不需要 virtualenv）。已在 Windows 和 Linux 上用 3.13 和 3.14 测试。在 Windows 上用 `winget install Python.Python.3.13` 安装（用户范围，不需要管理员权限），macOS 用 `brew install python`，或者用你的发行版的包管理器。没有它时，仪表盘会拒绝启动并用一行说明原因；`resolve-issue` 和其他所有 skill 的运行完全不受影响，因为仪表盘只负责观察。

<a id="repository-layout"></a>
## 📁 Repo 结构

```
plugins/<plugin>/
├── .claude-plugin/plugin.json     plugin metadata (name, version, dependencies)
├── skills/<skill>/SKILL.md        a user-invocable skill
├── agents/<agent>.md              a subagent (test-authoring only)
├── resources/                     bundled templates, static files, hook blocks
└── docs/                          deeper design docs
```
