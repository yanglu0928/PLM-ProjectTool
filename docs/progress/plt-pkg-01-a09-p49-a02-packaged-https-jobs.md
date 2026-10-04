# P49-A02：当前非发行候选 HTTPS/License 与 Jobs 随包读链

2026-10-02 / Phase 2 / `SYNTHETIC_PACKAGED_RUNTIME_PASS / RELEASE_OPEN`。输入为 P49-A01 固定非发行 ZIP SHA `26cf6c7c5b4eb2c63673c4f792aee273ff5169a3c3431c8cf5c65d566a87878d`、D盘清洁暂存、P07 Jobs 隔离验证器与原 P47 HTTPS 烟测。编码前检查：无产品代码/API/Schema/权限/依赖改变；仅一次性复制、启动、验证、清理。正式根 `C:\PLMTool` 不存在且不触碰，父P45/P47候选及现有库不变。验收：隔离布局逐件同Hash、包内Python/Caddy/PG18真实启动、合成HTTPS登录与License拒绝；另用**新包内**Python/PG18跑Jobs列表和Document详情真实临时库矩阵，随后清理并复核固定ZIP SHA。

HTTPS工具将21,181个文件映射到两份全新D盘临时布局，复制及独立读回校验，合成信任仅注入测试副本。实际结果：包内Python/Caddy/PG18启动，登录200、会话200、无License项目403，固定候选未改；12个合成Vault Key、API/Caddy/PG进程及两份临时布局工具报告清理成功。工具退出0后只读复核两目标路径均不存在、无残余postgres/caddy进程，ZIP哈希仍为固定值。正向公钥与目标账户均为合成测试材料，不是正式信任源。

随后 P07 runner以当前候选解包中的 `payload/runtime/python.exe` 和 `payload/pgsql/bin` 运行原Windows Jobs列表双Factory/双Owner矩阵与Document详情双Factory矩阵，两个完成标记且总退出0；一次性127.0.0.1:55432实例停止，D盘 `plm-job-read-matrix-*` 临时目录和端口监听均不存在。这验证包内后端读链，但不等于浏览器实际导航或前端网络渲染验收。P49-A01前端三资产与当前构建同Hash及Jobs路由标记已独立验证。

Changed/Files：仅本进度、STATUS、CHANGELOG；程序包和清洁暂存在本地Git忽略区，没有上传未审大体积发行物。Migration/API/依赖：本项无变更；旧0052既有迁移在P49-A01通过。兼容性：Windows11合成技术候选，不是正式安装器。升级/回滚：不执行安装升级；弃用新候选即可，历史候选不改。

未验证：正式产品公钥/License与目标账户、产品级LICENSE/NOTICE与法律签核、真实浏览器、Server2025/Debian13发行安装/升级、20并发/性能、AI质量、全业务UAT及Gate3～Release。`release_eligible=false`、`legal_clearance=false`；不得交付为正式可使用程序包。下一项返回Phase2未完的受控业务写/安装编排，选择前置完备的独立任务；发行阻断保持记录。
