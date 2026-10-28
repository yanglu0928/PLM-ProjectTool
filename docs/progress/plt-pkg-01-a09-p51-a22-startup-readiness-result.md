# PLT-PKG-01-A09-P51-A22：父包启动前置状态报告结果

- 日期：2026-10-28
- 状态：`PASS_LIMITED`（机器可读报告与缺公钥阻断断言；不代表应用可启动）
- Workflow：GitHub hosted Windows run `40609229745`，PR #56
- Head commit：`ce7dc422d47aefeaf1bb703702e3b3b5eb3fc358`
- Workflow merge-ref source commit：`f8a946a259a79696f83a8bc92284c8e97a2f1cd9`
- Parent artifact：`12782432091`（至2026-11-11保留）
- Parent ZIP：359,821,795 bytes，20,113 payload项，SHA-256 `cdbaf9ba6a1b8bacc6d7e92cbc53b2c8cb03913962c5d653a380cc746485a1ab`
- Smoke artifact：`12782486817`

## 变更

父包装配器从已验证的 embedded backend 清单路径中检测正式产品公钥资源，并在父包 `manifest.json` 与 `verification-summary.json` 写入相同 `startup_preflight` 字段。正式启动保持 `false`；当前包未包含资源时列出 `FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED`。临时PG smoke必须核对ZIP manifest和summary都报告同一个缺公钥状态；缺字段、意外ready或两份状态不一致均拒绝通过。没有读取、生成、请求或写入任何密钥。

## 云端验收

Run `40609229745` 的7个jobs均成功：后端测试/wheel、前端测试/typecheck/build、Python 3.13.15 embedded、PG18/pgvector、embedded backend、父包组装/逐项hash readback，以及从新包清洁解压后的临时PG smoke。Smoke在hosted Windows runner D盘临时目录启动PostgreSQL 18.6、创建并查询pgvector 0.8.6，停止和临时目录清理成功。日志中的summary确认：
- `formal_startup_ready=false`
- `packaged_product_public_key_resource_present=false`
- `blocker_codes=[FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED]`
- `product_api_started=false`、`production_installation=false`

## 边界与后续

本WBS证明父包能明确暴露当前启动阻断，并保持fail-closed；不证明生产API已启动、真实License可用或包已安装。正式公钥/签发信任、Windows凭据Vault、服务账户/ACL、HTTPS、OCR模型/native依赖、安装升级、Edge/UAT、Gate及Release仍未验。下一项A23在hosted runner D盘做包内生产入口缺凭据/缺公钥安全拒绝验证，不接触真实数据库、正式安装根或用户本机。
