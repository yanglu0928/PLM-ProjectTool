# PLT-PKG-01-A09-P36：新布局HTTPS静态/API回归

日期：2026-10-01；状态：`NON_RELEASE_CADDY_GO_LAYOUT_HTTPS_PASS / AUTH_REGRESSION_OPEN`。输入P33固定ZIP、P34新暂存与P35隔离布局；本项仅验证新包默认API与Caddy边界，不将P26旧包网络结果移植为新包证据。

编码前检查：Phase2/Gate3开放；先独立验P33/P22谱系、新暂存全载荷、布局21,115项全文件集与逐件Hash，再用包内Caddy/API和随机回环端口/临时合成证书做真实HTTPS请求。实体/API合同/权限/Schema/SCM/正式安装根均不修改。风险是默认API仅提供健康/404，不证明正式License与生产登录可用。

`tools/smoke_caddy_go_layout_https.py`真实执行exit0，目标映射SHA-256 `d4072ed23558da5026911fad3575ee8b4d67944814b58096b6587c1bf9908580`，21,115件Hash PASS；实际Caddy validate、HTTPS首页与两项JS/CSS字节同落盘、`/health/ready` 200/UP、默认`/api/v1/projects` 404且不被改为HTML、SPA深链200、错误Host421。Caddy/API子进程退出、临时证书销毁；新旧布局定向单元2/2 PASS。正式安装/服务/数据库未改。

下一项P37以新布局Caddy/PG18复跑生产登录/Session/CSRF/审计组合断言，并继续区分仓库应用对象和随包生产模式进程。正式信任源、客户证书/账户、产品NOTICE/法律、Server2025、Debian13（实机暂缓）、升级/UAT/Gate继续开放；`release_eligible=false`。回滚弃用本非发行探针，P33原包不变。
