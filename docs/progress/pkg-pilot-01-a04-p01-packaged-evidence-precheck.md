# PKG-PILOT-01-A04-P01：当前候选合成授权业务证明前置检查

日期：2026-10-24；状态：`SYNTHETIC_PACKAGED_EVIDENCE_PASS / FULL_VERTICAL_CHAIN_OPEN`。

|检查项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P01`：固定候选随包 Python/PG 的项目 Evidence 资格/权限链|
|输入基线|Gate 2、CR-EXEC-002、CR-PKG-008～010；A02/A03 ZIP SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`，包内0185及隔离HTTPS拒绝链已验|
|前置任务|A03通过，但只验无License Project403；现有 Evidence 随包脚本只接受旧P47 SHA，须使固定候选身份作为显式输入，不能沿用旧字节证明|
|涉及模块/实体|仅非发行验证工具，合成一次性 Project/Evidence/Review/Audit 数据；不修改正式产品|
|涉及 API / 权限|复用现有隔离 ASGI/PG validator，验证资格/回执/跨项目/撤权/License拒绝；不把合成客户签署当正式业务事实|
|验收标准|候选及暂存哈希/manifest一致，包内Python与PG运行，已有验证矩阵完整PASS，临时库和候选前后状态清理；结果只算一个业务片，不代表完整纵向链或浏览器UAT|
|风险|旧 validator 可能与0185头版本不兼容；失败需如实记录并停止该片，不改客户数据或降低权限/License检查|

## 实测结果

显式输入固定 ZIP SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`，候选与暂存 manifest/全量 22,191 件清单校验通过。复用既有 Evidence 资格验证器，在一次性隔离 PG18 使用**随包 Python**与 PG，项目 Evidence 候选→资格/HTTP 重放→原回执查询，以及并发赢家、跨项目/模板/撤销/License拒绝、Audit回滚与角色撤权矩阵完整返回固定 PASS 标记；工具退出0。临时 PG 目录删除，原数据库未触碰，候选前后 SHA 未变。边界单元1/1通过。

Changed：仅验证入口从旧 P47 固定 SHA 改为必填显式固定候选 SHA，业务验证器与产品未改。Files：`tools/smoke_current_app_packaged_evidence.py`、其测试、本进度/决策/版本说明。Migration/API/权限：无产品变更。Result：`SYNTHETIC_PACKAGED_EVIDENCE_PASS`。Known Issues：此片是隔离 ASGI/PG 业务证明，未在 HTTPS 包内进程完成合成有效 License 的纵向 Project→Plan/Output 链，也未真实浏览器、正式公钥/服务账户/客户确认、安装升级、法律或 Gate 验收。Next：`PKG-PILOT-01-A04-P02` 对同一候选进行合成授权的 HTTPS 当前业务路由与浏览器入口预检；不得把本片当可用 Pilot。
