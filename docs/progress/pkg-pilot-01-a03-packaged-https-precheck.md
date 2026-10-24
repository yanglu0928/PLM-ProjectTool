# PKG-PILOT-01-A03：固定候选隔离 HTTPS/License 前置检查

日期：2026-10-24；状态：`SYNTHETIC_PACKAGED_HTTPS_PASS / PILOT_NOT_READY`。

|检查项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / `PKG-PILOT-01-A03`：固定 A02 新候选的隔离 HTTPS/License 与业务路由烟测|
|输入基线|Gate 2、CR-EXEC-002、CR-PKG-008～010；A02 ZIP SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`，22,191 件独立清洁暂存与包内0185隔离PG验证通过|
|前置任务|A02 PASS；原合成 HTTPS 工具固定旧载荷数 21,182、旧迁移0052，须先改为以已签名清单/manifest动态计数并验证新 `0185`/Python pgvector 路径|
|涉及模块/实体/API|仅非发行验收工具；临时合成用户/项目与现有冻结登录/Project API，不改正式产品|
|权限/验收标准|匿名/错误Host/Origin失败关闭、合成登录与 Secure Cookie、缺 License 的受保护 Project 403；候选前后同Hash，临时Vault/进程/PG清理；不把合成公钥称正式信任|
|风险|合成私钥只存在一次性内存/副本；固定 Vault 目标可能被占用；两份临时布局需空间。预检 `C:\PLMTool` 不存在、固定目标0占用、C盘空闲约11.7GB，单份解包约1.39GB；只写直接 Temp 子目录|

本片不执行正式安装、SCM注册、证书供给或客户数据处理。

## 首轮实际失败（保留）

候选固定 SHA 与 22,191 件载荷映射校验通过，两份一次性布局经完整复制和哈希读回后，临时 API 子进程在 `/health/ready` 之前退出；首轮烟测退出 1，未进入正式 HTTPS 请求验收。原工具将子进程错误输出丢弃，无法据此判断业务启动根因。检查固定 Vault 目标占用为 0，临时安装布局、PG 运行目录和进程均已清理。仅对验收工具添加异常类型/缺失模块名的安全诊断并复验，保留本失败证据；不修改候选或生产代码，不把合成信任当正式来源。

## 修复与最终复验

第二轮仍因 API 健康前退出失败；安全诊断显示正式入口只输出泛化拒绝。第三轮加入**仅供测试**的工厂异常类型/源码位置报告，定位到 `ProductionLoginStartupError@production_login.py:2046`，未输出配置/凭据。核对旧夹具发现仅初始化早期 12 个 Vault 引用，而当前生产组合使用 AI、交接、调研、需求、原型、方案、计划、Trace/Review 等独立签名游标。第四轮在仅补部分引用的旧运行进程上仍失败；随后把当前入口模块声明的游标/Token 引用全部纳入一次性夹具，测试扫描常量以防未来漂移。以上失败均保持记录，临时进程、布局与 Vault 清理复核通过，不修改产品缺钥失败关闭逻辑。

最终在同一固定 ZIP SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d` 上，22,191 件载荷映射为 22,194 件含元数据的隔离布局；两份新布局逐件哈希读回。包内 Python、临时 PG18 和 Caddy 实际启动；错误 Host 为421、错误 Origin 为403、合成登录/会话均200且 Cookie 带 Secure/HttpOnly/SameSite、未装 License 的受保护 Project 为403。合成公钥只注入临时副本；48 个合成 Vault 引用、PG/API/Caddy 进程及两份布局完成后清理，独立再查固定 Vault 目标0占用，候选 SHA 前后相同。最终脚本退出0；关联定向烟测6/6、打包/暂存/迁移相关合计14/14、真实候选布局映射21,194项通过。

Changed：非发行验收适配器改用已验 manifest 件数、检查 `0185`/pgvector 映射，更新合成引用集合与安全失败诊断。Files：`tools/smoke_current_app_packaged_https.py`、`tools/smoke_packaged_platform_write_https.py`、对应测试、决策/本记录/版本说明。Migration/API/权限：产品无变更。Result：`SYNTHETIC_PACKAGED_HTTPS_PASS`。Known Issues：此项只证明合成信任与**未授权**业务拒绝，未验证真实 License/客户授权业务写链、正式服务账户/公钥/证书、SCM离线安装/重启/备份/升级、法律审阅、三平台和UAT/Gate。Next：`PKG-PILOT-01-A04` 在同一候选上做隔离合成授权的当前纵向业务路由/真实浏览器预检；正式信任仪式仍独立阻塞 Pilot。
