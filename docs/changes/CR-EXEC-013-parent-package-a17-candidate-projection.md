# CR-EXEC-013：基于同提交父包重建 A17 当前应用验收候选

- 日期：2026-10-28
- 状态：`RECORDED / IMPLEMENTATION_PENDING`
- 关联：`CR-EXEC-002/003/005/006/007`、`PLT-PKG-01-A09-P51-A17/A27`
- 授权依据：用户已持续授权按计划自主处理不兼容并记录后实施；本项仅调整云端验证输入，不扩大产品 Scope 或信任边界。

## 证据与偏差

A17 的 `validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py` 通过旧 P51-A05 runner 接受 `WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE`，要求独立当前应用包、旧父包摘要和 pgvector wheel 摘要。当前 hosted workflow (run 40637815870) 从官方固定来源重建的是 `WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE`，其中嵌入后端 manifest/第三方清单/同提交应用 wheel/前端资源在父包内，并含 PG/Caddy/配置/来源证据；workflow没有产出旧 P45 父包或单独 PGVector wheel。把静态语法检查或普通父包 PG smoke当作 A17 Edge业务通过不成立。

## 方案

在本轮 hosted Windows job 内，从已通过来源、提交、run ID、manifest 和逐文件 SHA-256 校验的父包候选，投影出 A17 runner 所需的当前应用候选：
1. 校验父包归档摘要、非发行/未法务放行、当前源码提交及 workflow run 身份。
2. 从父包 `provenance/embedded-backend-manifest.json` 验证 pgvector 0.5.0 官方 wheel 的原始 SHA-256与既有固定值相同；复用父包已逐文件验过的 pgvector/运行时内容，不重复叠加 wheel。
3. 用本次同提交后端 wheel 与前端 dist 替换包内相应应用文件；保留其它已摘要验证的运行时/PG/Caddy文件；生成新 current-app manifest、清单和摘要并逐项读回。
4. 在隔离 hosted Windows Server 2025 job 的非 C 盘 RUNNER_TEMP 执行已有 A17 Edge/HTTPS/PG 合成旅程。Node/浏览器、PG、配置、凭据和所有临时文件必须只用本轮拥有的路径/账户；真实客户资料、正式私钥与客户批准均不使用。

## 影响、风险和回滚

- 仅增加非发行验证候选投影与 hosted validation job；不修改产品 API、ORM、Schema、Migration、依赖或运行授权。
- 最主要风险是父包布局/第三方 wheel manifest 和旧 runner 输入协议不一致；任一来源、wheel 或文件摘要无法精确匹配时失败关闭，不允许改 pin、不猜测或改成合成摘要。
- 结果最多标记 `PASS_LIMITED`；Windows hosted runner 不是 Windows 11 实机，合成评审不是客户确认，真实 License trust/服务账户/TLS仍另行验收。
- 回滚为删除本次投影逻辑与 workflow job；不覆盖或删除旧 P45 历史、A26 候选及其证据。

## 验证计划

先验证投影器拒绝来源/摘要/提交/run/wheel 不匹配及归档路径/重复项，再用 hosted Windows workflow构建同提交 candidate、清洁解包并运行 Edge→HTTPS→PG PlanVersion Create/GET/Validate/SubmitReview/Review GET；独立 SQL核对 WBS/需求映射、Validation/Audit/Receipt/Review/Round及0条Decision。确保 cleanup，记录最终摘要和artifact；任何步骤失败只记录具体失败且保留旧证据。
