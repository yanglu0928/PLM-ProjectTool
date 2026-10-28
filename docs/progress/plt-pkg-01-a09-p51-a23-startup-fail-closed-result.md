# PLT-PKG-01-A09-P51-A23：包内生产入口安全拒绝结果

- 日期：2026-10-28
- 状态：PASS_LIMITED（仅缺数据库凭据条件下的生产入口安全拒绝；API未启动）
- Hosted Windows workflow：40614113243，PR #56 head f46a163c2e309cbf8a53eaab68577212db643f27
- Parent artifact：12784802709，20,113 payload项
- Parent ZIP：359,821,816 bytes，SHA-256 f0e5f8ddb08ac00f1bfda6dca5a633b8f643ccf595e8ae52a01e4fb530e9eedc
- Smoke artifact：12784224347

## 实施

复用父包clean extraction/hash验证和临时PG smoke；在PG启动前检查当前hosted账户固定数据库Credential target。此target不存在时，生成只在runner D盘临时根内的非敏感bootstrap配置，用包内Python隔离模式运行 serve_windows --platform-write，并将所有PLM_*与PYTHONPATH从子进程环境移除。断言退出码1、stdout为空、stderr为固定的 Production server unavailable; configuration or credential rejected.，然后重新绑定同一loopback端口确认服务未监听。若runner已有不明Credential则跳过入口调用，不读取秘密。

## 首轮失败与修复

- Run 40611975169：Credential存在性函数漏掉sys导入，在探测Credential前抛出NameError；未调用包内程序，不计通过。
- Run 40613037995：假定Python在payload/runtime/python/python.exe；实际由embedded backend打包器确认是payload/runtime/python.exe，故在启动前路径检查失败；未调用产品入口，不计通过。
- 两个偏差均在新run前记录并修复；A22公钥资源检测同步从错误的payload/runtime/python/packages修正为payload/runtime/packages。

## 验收证据

Run 40614113243全7 jobs成功。Smoke输出startup_entrypoint_probe=FAIL_CLOSED_MISSING_ACCOUNT_DATABASE_CREDENTIAL；A22 startup_preflight.formal_startup_ready=false，缺公钥阻断码FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED；PostgreSQL 18.6/pgvector 0.8.6、runner_drive=D:、product_api_started=false、production_installation=false。脚本成功退出同时证明固定拒绝消息/退出码和同端口重新绑定断言均通过；临时PG快速停止与runner临时目录清理通过。没有连接任何数据库、没有写入Credential、没有创建服务/安装根，也没有客户数据外发或本机执行。

## 剩余缺口

生产公钥/License信任仍缺；A23负例只证明无数据库Credential时入口失败关闭，不证明其他生产信任链。正式API成功启动、HTTPS/Edge、服务账户ACL、OCR、离线安装升级、完整纵向业务链、UAT、Gate或Release均未通过。下一项按STATUS推进当前父包与既有完整离线候选的Web/启动链集成差异审计。
