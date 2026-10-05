<!-- translated from README.md, source sha256 98876cdefb3886133692c15bd55b8d59d98319a14dd0aa56c7eaa5a27bf6a621; see CLAUDE.md "Translations of the root README" before editing -->
# test-authoring

[English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

一個自成一體、用於在你的程式碼中撰寫測試的 plugin。內含一組彼此配合的 6 個 skill、8 個 subagent，以及它們遵守的規則書。

這個 plugin 是 **彼此配合的**：skill 是設計成一起運作的。每個 skill 都直接從 plugin 的 `resources/templates/{rules,shared}/` 讀取規則書，不會有任何東西被複製到使用者的 repo，所以 plugin 一升級，每個 repo 都會同時套用。`setup-test-context` 是建立在這之上的 **選用加速器**：它為使用者的 repo 做一次概況分析，並把跨層對照表（專案架構、反覆出現的驗證模式）快取在 `.claude/conventions/tests/` 下。沒有它，每個流程（`scan-test-gaps`、`add/update {unit,integration} test`）仍然能執行，在執行時從最接近的相鄰測試找出慣例。

---

<a id="plugin-structure"></a>
## Plugin 結構

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

**plugin 內建 vs 每個 repo 各自的**：`plugins/test-authoring/` 底下的一切，包括 skill、agent、規則書和靜態資源，都隨 plugin 提供並直接從 plugin 讀取，所以 plugin 一升級，每個使用端 repo 都會同時拿到更新。唯一屬於各個 repo 的檔案，是 `setup-test-context` 從分析產生的那一到兩份慣例檔；它們沒有範本，因為它們正是為了那些無法隨 plugin 提供的內容而存在。

---

<a id="what-setup-test-context-writes-per-repo"></a>
## setup-test-context 在每個 repo 寫入什麼

當 `/test-authoring:setup-test-context` 在使用者的 repo 中執行時，它會寫入一到兩份檔案，兩者都由分析產生，不會複製或填寫任何範本。它不會碰那個目錄以外的任何東西：忽略規則是一份範圍限定的 `.claude/conventions/.gitignore`，內容是 `*`，和 `resolve-issue` 用於 `.claude/resolve/` 的做法相同。repo 根目錄的 `.gitignore` 屬於團隊，從不被修改。

```
.claude/
└── conventions/tests/                  # repo-specific patterns, learned from the codebase
    ├── project-architecture.md         # source/test layout, naming, mirroring, shared test project
    └── common-verification-patterns.md # only if a qualifying pattern was detected
```

各測試類型的 `{type}-test-conventions.md` **不會** 被寫入，plugin 也不再讀取它們。撰寫者使用最接近的相鄰測試，它永遠比快取還新；而一份沒有東西會產生、卻會被每個撰寫者信任的檔案，是一個注入的入口，而且因為路徑被 gitignore，在審查中看不見。

**為什麼 `conventions/` 存放的是唯一屬於各個 repo 的 *內容***：撰寫者 agent 對待規則和慣例的方式不同。**規則不可協商**，在每個 repo 都一樣，所以隨 plugin 提供。**慣例是描述性的模式**，觀察到的相鄰測試可以推翻它們，而且是唯一只能靠分析找出、無法隨 plugin 提供的東西。

**不會寫入各個 repo 的**（存放在 plugin 內）：
- 9 本規則書：`resources/templates/{rules,shared}/`，在執行時直接讀取
- 6 個使用者可叫用的 skill（以 `/test-authoring:<name>` 叫用）
- 8 個 subagent（以 `Agent(subagent_type="test-authoring:<name>-agent")` 叫用）
- `status-legend.md`：受控詞彙，屬於 plugin 內部，位於 `resources/static/status-legend.md`

---

<a id="skills-user-invocable"></a>
## Skill（使用者可叫用）

在 Claude Code 的 prompt 中以 `/test-authoring:<skill-name> [scope]` 執行。當描述相符時，也支援從自然語言自動觸發。

| Skill | 原始檔 | 詳細說明 | 用途 |
|---|---|---|---|
| `setup-test-context` | [SKILL.md](skills/setup-test-context/SKILL.md) | [docs](docs/skills/readme-setup-test-context.md) | 為 repo 做一次性的概況分析，快取成慣例；可以重複執行，重新執行就是更新 |
| `scan-test-gaps` | [SKILL.md](skills/scan-test-gaps/SKILL.md) | [docs](docs/skills/readme-scan-test-gaps.md) | 找出沒有測試的程式碼和過時的測試；反覆委派產生與更新。範圍：只限單元測試和整合測試 |
| `add-unit-test` | [SKILL.md](skills/add-unit-test/SKILL.md) | [docs](docs/skills/readme-add-unit-test.md) | 為變更過的原始碼或指定的目標產生單元測試 |
| `add-integration-test` | [SKILL.md](skills/add-integration-test/SKILL.md) | [docs](docs/skills/readme-add-integration-test.md) | 產生整合測試（endpoint、handler、consumer） |
| `update-unit-test` | [SKILL.md](skills/update-unit-test/SKILL.md) | [docs](docs/skills/readme-update-unit-test.md) | 分兩階段（稽核 → 執行）更新單元測試 |
| `update-integration-test` | [SKILL.md](skills/update-integration-test/SKILL.md) | [docs](docs/skills/readme-update-integration-test.md) | 同上，專用於整合測試（含 env_failure 處理） |

---

<a id="agents-subagents-spawned-by-skills"></a>
## Agent（由 skill 啟動的 subagent）

使用者不會直接叫用。由協調者 skill 透過 `Agent(subagent_type="test-authoring:<agent-name>")` 啟動（Claude Code 在執行時會自動套用 plugin 命名空間；每個 agent frontmatter 中的 `name:` 欄位是不含命名空間的識別名稱）。每個（角色 × 支援的測試類型）組合各有一個 agent。

| Agent | 原始檔 | 用途 |
|---|---|---|
| `add-unit-test-agent` | [agents/add-unit-test-agent.md](agents/add-unit-test-agent.md) | 單元測試的撰寫者 |
| `add-integration-test-agent` | [agents/add-integration-test-agent.md](agents/add-integration-test-agent.md) | 整合測試的撰寫者（選擇測試專案，並處理 env_failure） |
| `update-unit-test-agent` | [agents/update-unit-test-agent.md](agents/update-unit-test-agent.md) | 單元測試的兩階段更新撰寫者 |
| `update-integration-test-agent` | [agents/update-integration-test-agent.md](agents/update-integration-test-agent.md) | 同上，專用於整合測試 |
| `verify-add-{unit,integration}-test-agent` | [agents/](agents/) | 新增流程產出的唯讀驗證者 |
| `verify-update-{unit,integration}-test-agent` | [agents/](agents/) | 更新流程產出的唯讀驗證者（核對刪除是否有依據、核對有效的測試是否完整保留、區分 env_failure） |

較複雜的 update 和 verify-update agent 的詳細說明在 [`docs/agents/`](docs/agents/)。新增流程和 verify-add 的 agent 比較簡單，直接讀 agent 檔即可。

**模型：subagent 繼承呼叫者的模型。** 這些 agent 在 frontmatter 中沒有宣告 `model`，所以撰寫者或驗證者會使用叫用這個 skill 的模型來執行：以更強的模型進行的複雜執行，會讓撰寫者和它的獨立驗證者一起提升；便宜的執行則讓兩者都保持便宜。我們刻意 **不** 固定模型，也不為了節省成本而降級到較便宜的模型：那等於未經同意，就犧牲呼叫者選定的產出品質，來換取較低的成本。因此，在強模型的 session 下執行大型的 `scan-test-gaps` 分派，本來就會花比較多；想讓它便宜一些，請自己調低 session 的模型。

---

<a id="rule-books-strict-prescriptive-plugin-bundled"></a>
## 規則書（嚴格、規範性、plugin 內建）

每個 skill 和 agent 都直接從 `resources/templates/{rules,shared}/` 讀取，沒有任何東西會把它們寫進 repo。它們全都是通用的；沒有特定於某種測試類型的規則檔。skill 在它的 Step -1 解析一次 `resources/templates/` 的絕對路徑，並以 `plugin_resources_path` 交給每個 subagent，因為 subagent 自己無法解析它；如果無法解析，skill 會停止，而不是在沒有規則的情況下執行。

**context 紀律（延遲載入）**：協調者從不在一開始就把整套規則一次讀完。每個 skill 的 Step -1 只 *解析* 參考檔的位置，它的「Orchestrator reading list」則是在每份協調者用的文件第一次被用到的那一步才去讀。撰寫者和驗證者的規則書（`common-writer-instructions.md`、`common-verifier-checks.md`、`test-writer-rules.md` 等）由 subagent 在它們各自獨立的 context 中讀取，從不預先載入主 context。

**檔案分類：`common-*` vs 規則書**：`common-*` 檔案是 **角色生命週期文件**，說明這個角色是誰、它的輸入規格、程序和輸出結構；每個角色一份（協調者 / 撰寫者 / 更新撰寫者 / 驗證者）。其餘的檔案是 **規則書**：約束和協定，依讀者劃分範圍：`test-rules.md` 約束每個 agent，`test-writer-rules.md` 約束撰寫者，而 `fix-protocol.md` 由 **協調者** 讀取，用來決定驗證者發現的去向；每個驗證者也會讀它，以了解自己的發現會如何被處理（驗證者本身的檢查順序是 `common-verifier-checks.md`）。新增內容時，把角色的程序放進它的 `common-*` 檔，把約束放進對應的規則書，絕不兩邊都放（在這一對之間重複，正是規則分裂成兩個權威來源的原因）。

| 檔案 | 原始檔 | 用途 |
|---|---|---|
| `test-rules.md` | [resources/templates/rules/test-rules.md](resources/templates/rules/test-rules.md) | 修正規則（絕不弱化、跳過或刪除失敗的測試）以及建置與測試的驗證。**不是** 慣例清單：慣例來自相鄰測試 |
| `test-writer-rules.md` | [resources/templates/rules/test-writer-rules.md](resources/templates/rules/test-writer-rules.md) | 要測什麼（正常路徑、驗證、例外、邊界情況）以及不該做什麼 |
| `fix-protocol.md` | [resources/templates/rules/fix-protocol.md](resources/templates/rules/fix-protocol.md) | 驗證者的修正協定；斷路器（全域 3 次 / 每個問題 2 次） |
| `sut-analysis.md` | [resources/templates/rules/sut-analysis.md](resources/templates/rules/sut-analysis.md) | SUT 分析程序；外部 / 內部套件原始碼的執行時解析流程 |
| `common-orchestrator-flow.md` | [resources/templates/rules/common-orchestrator-flow.md](resources/templates/rules/common-orchestrator-flow.md) | 通用的協調者流程：範圍解析、委派撰寫者、啟動驗證者、修正與驗證迴圈、摘要 |
| `common-writer-instructions.md` | [resources/templates/rules/common-writer-instructions.md](resources/templates/rules/common-writer-instructions.md) | 通用的撰寫者程序：角色、輸入規格、SUT 分析、從相鄰測試學習、輸出結構 |
| `common-update-instructions.md` | [resources/templates/rules/common-update-instructions.md](resources/templates/rules/common-update-instructions.md) | 更新撰寫者通用的兩階段（稽核 → 執行）程序 |
| `common-verifier-checks.md` | [resources/templates/rules/common-verifier-checks.md](resources/templates/rules/common-verifier-checks.md) | 通用的驗證者檢查順序、輸出結構、轉交規則 |
| `scope-resolution.md` | [resources/templates/shared/scope-resolution.md](resources/templates/shared/scope-resolution.md) | Mode A（git diff）vs Mode B（明確參數）的範圍解析程序 |

---

<a id="per-repo-conventions-descriptive-learned-from-code"></a>
## 各 repo 的慣例（描述性、從程式碼學來）

從實際的程式碼分析得出的 repo 專屬模式，也是唯一會寫入各個 repo 的東西。撰寫者 agent 把它們當成參考資訊；在執行時，相鄰測試仍然優先。

| 檔案 | 原始檔 | 用途 |
|---|---|---|
| `project-architecture.md` | _（由分析產生，沒有範本）_ | 原始碼與測試的目錄結構、命名慣例、功能組織方式、共用的測試專案 |
| `common-verification-patterns.md` | _（由分析產生，只在偵測到至少一個同層共通或跨層共通的模式時才會產生）_ | 反覆出現的驗證模式 |

`status-legend.md` **不會** 寫入各個 repo。它位於 [`resources/static/status-legend.md`](resources/static/status-legend.md)，skill 透過 `<plugin-root>/resources/static/status-legend.md` 直接讀取。這讓受控詞彙只有一個來源；使用者在各 repo 副本中的擴充不會被採用。

---

<a id="no-generated-file-versioning"></a>
## 產生的檔案沒有版本管理

`setup-test-context` 在兩次執行之間 **不保留任何狀態**：沒有 manifest、沒有記錄的雜湊值、沒有每個檔案的 `schema_version`。它只知道目前 plugin 版本會寫入的那組固定路徑。

- 在那些路徑上已經存在的檔案會被改寫，而且無法復原：確認關卡會先把它列出來，那裡就是你把手動修改複製出來的時機。
- `.claude/{conventions,rules,shared}/tests/` 底下的其他東西會被列出但不會被動到：沒有記錄下來的狀態，一份已退役範本留下的檔案和你手寫的檔案看起來一模一樣。
- 沒有任何東西會替使用者偵測檔案是否過時。範本的變更，要等有人在那個 repo 重新執行 setup 才會生效。請 bump plugin 的版本，讓 `/plugin update` 真的會抓到這次變更。

要保留手動修改，請在重新執行之前先複製出來：寫入清單會先把它標成 `OVERWRITE`。把它 commit 起來沒有用：那個路徑被 `.gitignore` 涵蓋了。

---

<a id="docs--deeper-documentation"></a>
## docs/：更深入的文件

- [`docs/skills/`](docs/skills/)：每個 skill 一份 readme
- [`docs/agents/`](docs/agents/)：較複雜的 update 和 verify-update agent 的 readme
- [`docs/shared/`](docs/shared/)：跨領域概念的入門說明：
  - [readme-shared-orchestration.md](docs/shared/readme-shared-orchestration.md)：斷路器、修正與驗證迴圈
  - [readme-shared-scope-and-status.md](docs/shared/readme-shared-scope-and-status.md)：Mode A/B 範圍、狀態圖例
  - [readme-shared-update-patterns.md](docs/shared/readme-shared-update-patterns.md)：兩階段更新的生命週期

規則檔和簡單的 agent（新增流程和 verify-add）沒有個別的 readme，請直接讀原始檔。
