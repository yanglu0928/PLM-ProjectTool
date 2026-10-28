# PLT-PKG-01-A09-P51-A22：父包启动前置状态报告结果

- 日期：2026-10-28
- 状态：PASS_LIMITED（机器可读报告与缺公钥断言；不代表应用可启动）
- Workflow：GitHub hosted Windows run 40614113243（PR #56）
- Head commit：f46a163c2e309cbf8a53eaab68577212db643f27
- Parent artifact：12784802709（20,113 payload项；至2026-11-11保留）
- Parent ZIP：359,821,816 bytes，SHA-256 f0e5f8ddb08ac00f1bfda6dca5a633b8f643ccf595e8ae52a01e4fb530e9eedc
- Smoke artifact：12784224347

## 变更

父包装配器从已验证的embedded backend payload清单中检测产品公钥资源，当前实际路径为 payload/runtime/packages/plm_assistant/modules/license/trust/product_public_key.json；manifest与verification summary写入一致的 startup_preflight。缺资源时状态为正式启动未就绪并列出 FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED。Smoke断言两份清单一致且未误报ready。

## 偏差记录

第一次A22实现使用了另一种旧布局的 payload/runtime/python/packages 路径。A23编码前检查通过embedded backend打包器核实实际布局后修正，并在本次run重新组装的父包内重验公钥资源位置。旧run 40609229745、40610590590只作为历史证据；本结果以run 40614113243的修正后源码、父包与smoke为准。

## 云端验收

run 40614113243的7 jobs成功：后端测试/wheel、前端测试/typecheck/build、Python 3.13.15 embedded、PG18/pgvector、embedded backend、父包组装与逐项hash readback、D盘临时解包/PG smoke。Smoke日志确认formal_startup_ready=false、packaged_product_public_key_resource_present=false、blocker_codes=[FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED]。

## 边界

本WBS证明机器可读报告按正确payload布局指出正式公钥缺失，并保持fail-closed；不证明生产API已启动、真实License可用或包已安装。A23单独验证了缺数据库凭据时包内生产入口拒绝启动。HTTPS、Credential Store实际DB链、服务账户/ACL、OCR、安装升级、真实业务、UAT、Gate和Release仍未通过。
