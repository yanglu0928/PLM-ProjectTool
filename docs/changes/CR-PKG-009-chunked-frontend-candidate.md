# CR-PKG-009：当前前端分块构建与非发行派生包校验不兼容

日期：2026-10-24；来源：`PKG-PILOT-01-A01`；状态：`NON_RELEASE_IMPLEMENTED_AND_VERIFIED / FORMAL_RELEASE_OPEN`。承接 CR-PKG-008；不改 Gate 2 冻结架构、API、Schema 或既有候选包。

## 冲突与证据

现有 `package_windows_current_app_candidate.py` 仅接受 `index.html` 加各一份 `assets/index-*.js/.css`。当前 Vue/Vite 构建的 `dist` 包含 50 个 JS、36 个 CSS 和一个 HTML；其余资源是按页面分块、带构建哈希的静态文件。原校验会拒绝真实当前应用，不能以旧前端代替。

此外 CLI 以整个工作区 `git status --porcelain` 判脏；工作区存在用户自有未跟踪 `.tmp/`，不属于打包输入。直接清理它会越界，忽略所有未跟踪源码又会损害来源证明。

## 方案比较与选择

- A：关闭布局校验或任意拷贝 `dist`。可能带入源映射、Secret、临时文件；不选。
- B：保留 `index.html` 唯一入口，允许 `assets/` 下带固定哈希后缀的 JS/CSS 分块；拒绝其他类型、层级、链接和重名；仍逐件入清单并独立验真。源码脏检查只忽略工作区外部的用户 `.tmp/`，但输入目录与已跟踪修改必须干净。选择 B。
- C：改前端构建为单包。会扩大产物和改变当前产品构建策略；不选。

## 差异、影响、迁移与回滚

只改变非发行候选的输入验证/构建工具与测试。父 ZIP、原候选和产品运行代码不动；无数据库迁移、权限/API 变更。新包以唯一 ID、源码提交、wheel 与逐件资源哈希区分；仍标记 `release_eligible=false`、`legal_clearance=false`。回滚为弃用新候选并恢复旧校验器，历史 ZIP 不覆盖。风险是分块文件漏收或意外包含额外资源，须用真实 `dist`、负例和独立清洁解包核查。

## 验证计划

定向测试覆盖多分块通过、非白名单文件/链接/缺入口失败、父包与 wheel 哈希约束；在干净已提交源码上重新构建 wheel/dist，生成全量新非发行 ZIP，独立读回哈希与清洁暂存，不把缺失的正式公钥、法律结论、安装/升级及 Gate 说成通过。同步代码、测试、记录和版本说明到 GitHub；大型 ZIP 仅留受控本地忽略区。

## 实施与结果

已在提交 `0bb3ed2db7dae42dca449540a12239fcfe2a92eb` 实施方案 B；包内前端布局为 87 件。定向打包/暂存测试 5/5；新非发行 ZIP SHA-256 `da90e98b41e8684a12af83c9d03a0162292cab9288e28c220dc38dfd72a4bb6a`，22,145 件载荷，独立清洁解包及哈希读回通过。详见 [A01 证据](../progress/pkg-pilot-01-a01-current-candidate-precheck.md)。这只关闭分块不兼容与候选完整性，不关闭正式安装、信任或法律验收。
