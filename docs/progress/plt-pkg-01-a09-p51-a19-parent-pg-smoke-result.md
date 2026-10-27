# PLT-PKG-01-A09-P51-A19：父包PG组件临时生命周期验证结果

- 日期：2026-10-27
- 状态：`PASS_LIMITED`（仅父包完整性与PostgreSQL/pgvector临时生命周期）
- Workflow：hosted Windows Server 2025 run `40466454597`
- 同run父包：artifact `12716703530`；353,438,357 bytes；至2026-11-10保留；archive SHA-256 `259af5595251083e8e67abe648727cb2410930455278d97fe2eb1067971498c1`
- Smoke summary：artifact `12717400427`；至2026-11-10保留
- Parent source commit：`86c8b543ad54061e70ffebe6bc7e08c0b5100a41`

## 结果

首次run `40458978359` 按45分钟上限取消：`pg_ctl start` 超时后，PG子进程继承stdout/stderr管道使Python等待pipe关闭。偏差和修正见 CR-EXEC-011；该次未产出PASS。修复后run `40464618526` 避免了pipe hang，但版本断言把多语句psql的状态行误当版本。拆分查询后，run `40466454597` 全workflow jobs完成，smoke终态成功。

机器可读summary记录：
- status `PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED`
- PostgreSQL `18.6`；pgvector `0.8.6`
- listen host仅 `127.0.0.1`
- temp DB only；runner drive `D:\\`
- `production_installation=false`、`product_api_started=false`、`license_trust_used=false`
- 父包 `20,111` payload files已清洁解包并逐项hash校验。

## 清理与界限

临时PG进程执行fast stop，D盘 runner temp目录清除；未触碰用户本机、客户数据或正式数据库。全量 backend/frontend/runtime/sidecar/父包构建亦成功。此次只验PG组件运行和父包载荷，未验证产品服务、数据库迁移/业务API、Edge/HTTPS、OCR模型、服务账户ACL、正式License信任、安装升级、Gate/Pilot/Release。
