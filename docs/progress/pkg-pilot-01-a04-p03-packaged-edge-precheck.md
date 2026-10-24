# PKG-PILOT-01-A04-P03：固定候选 Edge 页面与后续业务入口预检

日期：2026-10-24；编码前状态：`IN_PROGRESS / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P03`；仅证明固定非发行候选的真实 Edge 登录、项目、Workflow 页面和后续入口|
|输入基线|Gate 2、CR-EXEC-002、固定候选 SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`；A04-P02 合成 License/HTTPS/Workflow API PASS|
|前置检查|Windows 11 Edge 和 Node 可用；A04-P02 夹具仅对一次性 PG/Vault/公钥副本使用合成数据，固定候选保持不变|
|模块、实体、API|只增验收驱动；既有 Auth、Project、Workflow 前端和冻结 `/api/v1` 的只读调用；不改产品/Schema/迁移|
|权限|合成项目经理仅访问自身项目；浏览器独立临时配置、隔离 HTTPS，退出后销毁；正式发行公钥和真实客户 License 仍缺|
|验收标准|从真实 Edge 页面完成登录→项目列表→项目详情→Workflow v1，刷新仍为 HANDOVER；检查后续业务链接并至少打开交接、调研、需求、原型、方案、计划入口，报告可达与错误；网络响应与前端异常可审计，包 SHA 不变且临时资源清理|
|风险|部分后续页面在空白合成项目上可能显示“暂无数据”或依赖未建立的事实；仅检查入口/受控空状态，不声称业务闭环。自签证书仅限一次性隔离浏览器通过，不能作为正式 TLS 验收。|

本项不改变冻结设计；验收驱动复用已存在的 Edge/CDP 和 A04-P02 HTTPS 夹具。若浏览器无法进入某页面，记录实际失败，不删除正式目标或放宽生产权限。

## 首轮诊断

首轮固定候选真实 Edge 运行：包内 PG/API/Caddy、合成 License、Workflow HTTPS GET/START/重放/拒绝/Audit 先通过；浏览器登录、项目列表和项目详情响应均为 200。进入“交接分析与待确认事项”后，页面出现“暂时无法读取项目交接分析，请稍后重试。”，故本项首轮 `FAIL`，不能声称入口验收通过。该轮网络观察没有交接接口的响应记录；已补充浏览器加载失败与剩余入口的诊断，待复验后区分请求层、UI 和夹具时序。首轮异常路径中的临时布局、进程和合成 Vault 均由既有烟测 finally 清理，未修改固定候选。

## 复验与结论

第二轮固定候选再次完成包内 PG/API/Caddy、合成 License 及 Workflow HTTPS GET/START/重放/CSRF/冲突/Audit 前置验证；真实 Edge 登录、项目列表和详情为 200。交接入口仍出现同一读取失败；调研、需求、原型、方案目录、实施计划页面无可见告警，其只读 API 均为 200；Workflow 页面及刷新均为 `ACTIVE/HANDOVER/v1`，两个 Workflow GET 均为 200。整项因交接入口失败判定 `FAIL`，不得将五个可达入口等同完整业务链/UAT。

原因定位：交接 `HandoverReadClient.#get` 使用 `this.fetcher(...)`，在真实浏览器原生 `fetch` 上改变调用上下文并在网络请求前报 `Illegal invocation`；其 mock 测试没有约束调用上下文，因而未发现。相邻调研/需求客户端已使用局部函数调用。修复另列 `HND-01-A05-A08`，旧候选保持原 SHA 和失败历史；新前端必须重新打包并通过 Edge 复验。未验证正式信任、完整链、升级、UAT 或任何 Gate。

Changed/Files：仅此验收驱动及记录；Migration/API/权限：无变更。Tests：固定候选包内 HTTPS/Workflow 前置 PASS，两轮真实 Edge 整项 FAIL。Result：`PACKAGED_EDGE_HANDOVER_READ_FAIL`。Known Issues：交接原生 fetch 上下文；其余入口只验证空白项目可达，未形成真实业务结果；正式 Pilot 仍 NOT_READY。Next：使用 `HND-01-A05-A08` 修复构建新候选并复验 `PKG-PILOT-01-A04-P03`。
