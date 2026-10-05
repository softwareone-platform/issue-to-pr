# Translation glossary

The root `README.md` is translated into Traditional Chinese (`README.zh-TW.md`) and Simplified Chinese (`README.zh-CN.md`). This file fixes how its terms are rendered, so that every re-translation uses the same words and a diff shows only what really changed.

## Never translated

Kept exactly as written in the English README: product and service names (Claude Code, GitHub, Azure DevOps, Atlassian, Jira, Python, SonarCloud), plugin, skill and subagent names (`disconfirm-first`, `resolve-issue`, …), slash commands, file and directory paths, command lines, every fenced code block (including the pipeline diagram, whose alignment CJK full-width characters would break), and every link target.

These stay in English inside translated prose too, because they are what a reader types or searches for: plugin, skill, subagent, marketplace, hook, PR (and pull request), issue, story, repo, working tree, branch, remote, commit, push, pipeline, session, agent, badge, token, transcript, frontmatter, fixture.

## Rendered terms

| English | zh-TW | zh-CN |
|---|---|---|
| ticket | 工單 | 工单 |
| plan | 計畫 | 计划 |
| fix (noun) | 修正 | 修复 |
| pre-mortem | 事前驗屍 | 事前验尸 |
| adversarial review | 對抗式審查 | 对抗式审查 |
| altitude (review level) | 層級 | 层级 |
| fact-check | 事實查核 | 事实核查 |
| gate | 關卡 | 关卡 |
| plan approval | 計畫核准 | 计划批准 |
| orchestrator / orchestration | 協調者 / 協調 | 编排器 / 编排 |
| writer (subagent) | 撰寫者 | 编写者 |
| verifier (subagent) | 驗證者 | 验证者 |
| convention | 慣例 | 约定 |
| dashboard | 儀表板 | 仪表盘 |
| checkpoint | 檢查點 | 检查点 |
| learnings | 經驗 | 经验 |
| auto-update | 自動更新 | 自动更新 |
| dependency | 相依套件 | 依赖 |
| standalone | 獨立使用 | 独立使用 |
| ground truth | 依據 | 基准 |
| outward change | 對外變更 | 对外变更 |
| wall-clock time | 實際經過時間 | 实际耗时 |
| user-global | 使用者全域 | 用户全局 |
| optional | 選用 | 可选 |
| pressure-test | 壓力測試 | 压力测试 |
| sibling tests (the existing tests next to the target) | 相鄰測試 | 相邻测试 |
| extension (CLI) | 擴充功能 | 扩展 |
| codebase | 程式碼 | 代码库 |
| claim (in an issue) | 主張 | 论断 |
| triage (a review comment) | 判斷如何處理 | 判断如何处理 |
| open (a PR) | 開出 | 创建 |

## How to translate

Read what a sentence describes before rendering it — the skill's own `SKILL.md` or README when the sentence summarises one — rather than translating word by word. Keep the paragraph structure of the English README one for one, so the two files can be compared section by section. When the English changes, re-translate only the changed paragraphs and leave the rest as they are.
