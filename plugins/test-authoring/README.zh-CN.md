<!-- translated from README.md, source sha256 98876cdefb3886133692c15bd55b8d59d98319a14dd0aa56c7eaa5a27bf6a621; see CLAUDE.md "Translations of the root README" before editing -->
# test-authoring

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

一个自成一体、用于在你的代码库中编写测试的 plugin。包含一组相互配合的 6 个 skill、8 个 subagent，以及它们遵守的规则书。

这个 plugin 是 **相互配合的**：skill 是设计成一起工作的。每个 skill 都直接从 plugin 的 `resources/templates/{rules,shared}/` 读取规则书，不会有任何东西被复制到使用方的 repo，因此 plugin 一升级，就会同时作用于每个 repo。`setup-test-context` 是建立在这之上的 **可选加速器**：它对使用方的 repo 做一次概况分析，并把跨层映射（项目架构、反复出现的验证模式）缓存在 `.claude/conventions/tests/` 下。没有它，每个流程（`scan-test-gaps`、`add/update {unit,integration} test`）仍然可以运行，在运行时从最近的相邻测试中找出约定。

---

<a id="plugin-structure"></a>
## Plugin 结构

```
plugins/test-authoring/
├── .claude-plugin/plugin.json              # plugin metadata
├── README.md                               # this file
├── skills/                                 # 6 plugin-bundled skills
│   ├── setup-test-context/SKILL.md         # one-time repo profile (optional)
│   ├── scan-test-gaps/SKILL.md
│   ├── add-unit-test/SKILL.md
│   ├── add-integration-test/SKILL.md
│   ├── update-unit-test/SKILL.md
│   └── update-integration-test/SKILL.md
├── agents/                                 # 8 plugin-bundled subagents (flat, bare names)
│   ├── add-{unit,integration}-test-agent.md
│   ├── update-{unit,integration}-test-agent.md
│   ├── verify-add-{unit,integration}-test-agent.md
│   └── verify-update-{unit,integration}-test-agent.md
├── resources/
│   ├── templates/                          # the rule books; read from here, never copied per-repo
│   │   ├── rules/                          # 8 .md
│   │   └── shared/                         # scope-resolution.md
│   └── static/                             # plugin-internal, never written per-repo
│       └── status-legend.md                # controlled vocabulary, do not extend
└── docs/                                   # detailed per-skill / per-agent / shared docs
    ├── skills/{readme-*.md}                # one per skill
    ├── agents/{readme-*.md}                # high-complexity update + verify-update agents
    └── shared/{readme-*.md}                # cross-cutting concept primers
```

**plugin 内置 vs 每个 repo 各自的**：`plugins/test-authoring/` 下的一切，包括 skill、agent、规则书和静态资源，都随 plugin 提供并直接从 plugin 读取，因此 plugin 一升级，就会同时作用于每个使用方 repo。唯一属于各个 repo 的文件，是 `setup-test-context` 通过分析生成的那一到两份约定文件；它们没有模板，因为它们正是为那些无法随 plugin 提供的内容而存在的。

---

<a id="what-setup-test-context-writes-per-repo"></a>
## setup-test-context 在每个 repo 中写入什么

当 `/test-authoring:setup-test-context` 在使用方的 repo 中运行时，它会写入一到两份文件，两者都由分析生成，不会复制或填写任何模板。它不会触碰那个目录以外的任何东西：忽略规则是一份范围限定的 `.claude/conventions/.gitignore`，内容是 `*`，与 `resolve-issue` 用于 `.claude/resolve/` 的做法相同。repo 根目录的 `.gitignore` 属于团队，从不被修改。

```
.claude/
└── conventions/tests/                  # repo-specific patterns, learned from the codebase
    ├── project-architecture.md         # source/test layout, naming, mirroring, shared test project
    └── common-verification-patterns.md # only if a qualifying pattern was detected
```

各测试类型的 `{type}-test-conventions.md` **不会** 被写入，plugin 也不再读取它们。编写者使用最近的相邻测试，它永远比缓存更及时；而一份没有任何东西会生成、却会被每个编写者信任的文件，是一个注入入口，而且因为路径被 gitignore，在审查中看不到。

**为什么 `conventions/` 存放的是唯一属于各个 repo 的 *内容***：编写者 agent 对待规则和约定的方式不同。**规则不可协商**，在每个 repo 中都一样，因此随 plugin 提供。**约定是描述性的模式**，观察到的相邻测试可以推翻它们，也是唯一一种只能靠分析发现、无法随 plugin 一起提供的东西。

**不会写入各个 repo 的**（存放在 plugin 中）：
- 9 本规则书：`resources/templates/{rules,shared}/`，在运行时直接读取
- 6 个用户可调用的 skill（以 `/test-authoring:<name>` 调用）
- 8 个 subagent（以 `Agent(subagent_type="test-authoring:<name>-agent")` 调用）
- `status-legend.md`：受控词汇，属于 plugin 内部，位于 `resources/static/status-legend.md`

---

<a id="skills-user-invocable"></a>
## Skill（用户可调用）

在 Claude Code 的 prompt 中以 `/test-authoring:<skill-name> [scope]` 运行。当描述匹配时，也支持根据自然语言自动触发。

| Skill | 源文件 | 详细说明 | 用途 |
|---|---|---|---|
| `setup-test-context` | [SKILL.md](skills/setup-test-context/SKILL.md) | [docs](docs/skills/readme-setup-test-context.md) | 对 repo 做一次概况分析，缓存为约定；可以重复运行，重新运行就是刷新 |
| `scan-test-gaps` | [SKILL.md](skills/scan-test-gaps/SKILL.md) | [docs](docs/skills/readme-scan-test-gaps.md) | 找出没有测试的代码和过时的测试；反复委派生成与更新。范围：仅限单元测试和集成测试 |
| `add-unit-test` | [SKILL.md](skills/add-unit-test/SKILL.md) | [docs](docs/skills/readme-add-unit-test.md) | 为变更过的源代码或指定的目标生成单元测试 |
| `add-integration-test` | [SKILL.md](skills/add-integration-test/SKILL.md) | [docs](docs/skills/readme-add-integration-test.md) | 生成集成测试（endpoint、handler、consumer） |
| `update-unit-test` | [SKILL.md](skills/update-unit-test/SKILL.md) | [docs](docs/skills/readme-update-unit-test.md) | 分两个阶段（审计 → 执行）更新单元测试 |
| `update-integration-test` | [SKILL.md](skills/update-integration-test/SKILL.md) | [docs](docs/skills/readme-update-integration-test.md) | 同上，专用于集成测试（含 env_failure 处理） |

---

<a id="agents-subagents-spawned-by-skills"></a>
## Agent（由 skill 启动的 subagent）

用户不会直接调用。由编排器 skill 通过 `Agent(subagent_type="test-authoring:<agent-name>")` 启动（Claude Code 在运行时会自动应用 plugin 命名空间；每个 agent frontmatter 中的 `name:` 字段是不含命名空间的标识名）。每个（角色 × 支持的测试类型）组合各有一个 agent。

| Agent | 源文件 | 用途 |
|---|---|---|
| `add-unit-test-agent` | [agents/add-unit-test-agent.md](agents/add-unit-test-agent.md) | 单元测试的编写者 |
| `add-integration-test-agent` | [agents/add-integration-test-agent.md](agents/add-integration-test-agent.md) | 集成测试的编写者（选择测试项目，并处理 env_failure） |
| `update-unit-test-agent` | [agents/update-unit-test-agent.md](agents/update-unit-test-agent.md) | 单元测试的两阶段更新编写者 |
| `update-integration-test-agent` | [agents/update-integration-test-agent.md](agents/update-integration-test-agent.md) | 同上，专用于集成测试 |
| `verify-add-{unit,integration}-test-agent` | [agents/](agents/) | 新增流程产出的只读验证者 |
| `verify-update-{unit,integration}-test-agent` | [agents/](agents/) | 更新流程产出的只读验证者（核对删除是否有依据、核对有效测试是否完整保留、区分 env_failure） |

较复杂的 update 和 verify-update agent 的详细说明在 [`docs/agents/`](docs/agents/)。新增流程和 verify-add 的 agent 比较简单，直接阅读 agent 文件即可。

**模型：subagent 继承调用者的模型。** 这些 agent 在 frontmatter 中没有声明 `model`，所以编写者或验证者会使用调用这个 skill 的模型来运行：以更强的模型进行的复杂运行，会让编写者和它的独立验证者一起提升；便宜的运行则让两者都保持便宜。我们有意 **不** 固定模型，也不为了节省成本而降级到更便宜的模型：那等于未经同意就牺牲调用者选定的产出质量，来换取更低的成本。因此，在强模型的 session 下运行大型的 `scan-test-gaps` 分派，本来就会花得更多；想让它便宜一些，请自己调低 session 的模型。

---

<a id="rule-books-strict-prescriptive-plugin-bundled"></a>
## 规则书（严格、规范性、plugin 内置）

每个 skill 和 agent 都直接从 `resources/templates/{rules,shared}/` 读取，没有任何东西会把它们写进 repo。它们全都是通用的；没有特定于某种测试类型的规则文件。skill 在它的 Step -1 解析一次 `resources/templates/` 的绝对路径，并以 `plugin_resources_path` 交给每个 subagent，因为 subagent 自己无法解析它；如果无法解析，skill 会停止，而不是在没有规则的情况下运行。

**context 纪律（延迟加载）**：编排器从不在一开始就把整套规则一次读完。每个 skill 的 Step -1 只 *解析* 参考文件的位置，它的“Orchestrator reading list”则是在每份编排器用的文档第一次被用到的那一步才去读。编写者和验证者的规则书（`common-writer-instructions.md`、`common-verifier-checks.md`、`test-writer-rules.md` 等）由 subagent 在它们各自独立的 context 中读取，从不预先加载到主 context。

**文件分类：`common-*` vs 规则书**：`common-*` 文件是 **角色生命周期文档**，说明这个角色是谁、它的输入规范、流程和输出结构；每个角色一份（编排器 / 编写者 / 更新编写者 / 验证者）。其余的文件是 **规则书**：约束和协议，按读者划分范围：`test-rules.md` 约束每个 agent，`test-writer-rules.md` 约束编写者，而 `fix-protocol.md` 由 **编排器** 读取，用来决定验证者发现的去向；每个验证者也会读它，以了解自己的发现会如何被处理（验证者本身的检查顺序是 `common-verifier-checks.md`）。新增内容时，把角色的流程放进它的 `common-*` 文件，把约束放进对应的规则书，绝不两边都放（在这一对之间重复，正是规则分裂成两个权威来源的原因）。

| 文件 | 源文件 | 用途 |
|---|---|---|
| `test-rules.md` | [resources/templates/rules/test-rules.md](resources/templates/rules/test-rules.md) | 修复规则（绝不弱化、跳过或删除失败的测试）以及构建与测试的验证。**不是** 约定清单：约定来自相邻测试 |
| `test-writer-rules.md` | [resources/templates/rules/test-writer-rules.md](resources/templates/rules/test-writer-rules.md) | 要测什么（正常路径、校验、异常、边界情况）以及不该做什么 |
| `fix-protocol.md` | [resources/templates/rules/fix-protocol.md](resources/templates/rules/fix-protocol.md) | 验证者的修复协议；熔断机制（全局 3 次 / 每个问题 2 次） |
| `sut-analysis.md` | [resources/templates/rules/sut-analysis.md](resources/templates/rules/sut-analysis.md) | SUT 分析流程；外部 / 内部包源代码的运行时解析流程 |
| `common-orchestrator-flow.md` | [resources/templates/rules/common-orchestrator-flow.md](resources/templates/rules/common-orchestrator-flow.md) | 通用的编排器流程：范围解析、委派编写者、启动验证者、修复与验证循环、总结 |
| `common-writer-instructions.md` | [resources/templates/rules/common-writer-instructions.md](resources/templates/rules/common-writer-instructions.md) | 通用的编写者流程：角色、输入规范、SUT 分析、从相邻测试学习、输出结构 |
| `common-update-instructions.md` | [resources/templates/rules/common-update-instructions.md](resources/templates/rules/common-update-instructions.md) | 更新编写者通用的两阶段（审计 → 执行）流程 |
| `common-verifier-checks.md` | [resources/templates/rules/common-verifier-checks.md](resources/templates/rules/common-verifier-checks.md) | 通用的验证者检查顺序、输出结构、转交规则 |
| `scope-resolution.md` | [resources/templates/shared/scope-resolution.md](resources/templates/shared/scope-resolution.md) | Mode A（git diff）vs Mode B（明确参数）的范围解析流程 |

---

<a id="per-repo-conventions-descriptive-learned-from-code"></a>
## 各 repo 的约定（描述性、从代码中学来）

从实际的代码库分析得出的 repo 专属模式，也是唯一会写入各个 repo 的东西。编写者 agent 把它们作为参考信息；在运行时，相邻测试仍然优先。

| 文件 | 源文件 | 用途 |
|---|---|---|
| `project-architecture.md` | _（由分析生成，没有模板）_ | 源代码与测试的目录结构、命名约定、功能组织方式、共享的测试项目 |
| `common-verification-patterns.md` | _（由分析生成，仅在检测到至少一个同层通用或跨层通用的模式时才会生成）_ | 反复出现的验证模式 |

`status-legend.md` **不会** 写入各个 repo。它位于 [`resources/static/status-legend.md`](resources/static/status-legend.md)，skill 通过 `<plugin-root>/resources/static/status-legend.md` 直接读取。这让受控词汇只有一个来源；用户在各 repo 副本中的扩展不会被采用。

---

<a id="no-generated-file-versioning"></a>
## 生成的文件没有版本管理

`setup-test-context` 在两次运行之间 **不保留任何状态**：没有 manifest、没有记录的哈希值、没有每个文件的 `schema_version`。它只知道当前 plugin 版本会写入的那组固定路径。

- 在那些路径上已经存在的文件会被重写，而且无法撤销：确认关卡会先把它列出来，那里就是你把手动修改复制出来的时机。
- `.claude/{conventions,rules,shared}/tests/` 下的其他东西会被列出但不会被改动：没有记录下来的状态，一份已退役模板留下的文件和你手写的文件看起来一模一样。
- 没有任何东西会替使用方检测文件是否过时。模板的变更，要等有人在那个 repo 重新运行 setup 才会生效。请提升 plugin 的版本号，让 `/plugin update` 真正拉取到这次变更。

要保留手动修改，请在重新运行之前先复制出来：写入清单会先把它标为 `OVERWRITE`。把它 commit 起来没有用：那个路径被 `.gitignore` 覆盖了。

---

<a id="docs--deeper-documentation"></a>
## docs/：更深入的文档

- [`docs/skills/`](docs/skills/)：每个 skill 一份 readme
- [`docs/agents/`](docs/agents/)：较复杂的 update 和 verify-update agent 的 readme
- [`docs/shared/`](docs/shared/)：横切性概念的入门说明：
  - [readme-shared-orchestration.md](docs/shared/readme-shared-orchestration.md)：熔断机制、修复与验证循环
  - [readme-shared-scope-and-status.md](docs/shared/readme-shared-scope-and-status.md)：Mode A/B 范围、状态图例
  - [readme-shared-update-patterns.md](docs/shared/readme-shared-update-patterns.md)：两阶段更新的生命周期

规则文件和简单的 agent（新增流程和 verify-add）没有单独的 readme，请直接阅读源文件。
