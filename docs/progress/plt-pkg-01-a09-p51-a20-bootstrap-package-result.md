# PLT-PKG-01-A09-P51-A20：父包bootstrap样例与操作说明结果

- 日期：2026-10-27
- 状态：`PASS_LIMITED`（仅非敏感配置示例与父包完整性）
- Workflow：hosted Windows Server 2025 run `40470225173`
- Parent artifact：`12718169549`，353,441,645 bytes，至2026-11-10保留
- Parent ZIP SHA-256：`bbf55d75d2a26744d3765e49a2c8386a8cbae0f89d9a877adb295b582a4f52aa`
- PostgreSQL smoke artifact：`12719060331`
- Branch source commit in Actions merge ref：`f5051a5d1b2d60e90a6a6dc25b6c8a826cd8fcb7`

## 变更

父包新增 `payload/config/bootstrap.example.yaml` 和 `payload/README-FIRST.md`。配置只含非敏感设置，示例 `data_root` 为 `D:/PLMTool/data`；新增说明要求操作者核对目标盘空间/权限，若目标机器无D盘则改用其他合适绝对路径，凭据经Windows受控凭据存储提供。原仓库配置样例保持不变。

## 云端验收

run `40470225173` 的后端测试/wheel、前端测试/typecheck/build、PG18.6/pgvector重建、Python 3.13.15 embedded base、embedded backend wheelhouse、父包assemble/readback、A19 D盘runner temp PG18.6/pgvector0.8.6 lifecycle smoke全部成功。父包含20,113 payload items；manifest保留 `release_eligible=false`、`legal_clearance=false`、`installation_performed=false`、`database_started=false`。A19 smoke仅在127.0.0.1创建临时库并验证版本，关闭和清理通过。

## 剩余缺口

配置样例不等于配置部署或应用可运行。产品API未启动，未执行迁移；Windows服务账户/ACL、数据库受控凭据、真实产品公钥、正式License/Trusted Time、HTTPS、OCR模型/原生组件、Edge/UAT、Gate和Release均未验。

当前分支缺少 `apps/backend/src/plm_assistant/modules/license/trust/product_public_key.json`（GitHub contents API 404），但 `pyproject.toml` 的package-data声明和 `PackagedProductKey` 运行时均要求该资源。不得生成猜测信任锚或用测试锚伪装正式包。具体启动前置核查转入A21。
