# PLT-PKG-01-A09-P21-A01：Caddy Host 边界诊断与兜底

日期：2026-10-01；状态：`SYNTHETIC_HOST_BOUNDARY_PASS / PRODUCTION_AUTH_OPEN`。依 `CR-PKG-005`、P19/P20；原P15非发行ZIP不覆盖。

编码前检查：Phase2/Gate3开放；输入为固定Caddy v2.11.4、随包P15/P17布局和P20错误Host状态码200。仅测试Web边界；业务模块/实体/API/权限/Schema/Migration均不变。验收：辨别状态码与实际响应体、确定可验证的显式拒绝配置、用真实固定二进制/21,103件包重跑好Host静态/API/SPA、坏Host和重复Host，退出清理。风险：合成证书/默认健康API不等于生产登录/CSRF/SSE、正式信任源和三平台验收。

`tools/probe_caddy_host_boundary.py` 使用纯合成证书、随机回环端口与Host回显：原单站点配置中正常Host为200/`localhost`，错误Host状态200但**空正文**，重复Host为400。P20文档称“返回静态首页”不符合证据，已保留并加更正。按CR-PKG-005要求，增同端口`https://:<port>`无主机名兜底站点、明确`421 Misdirected Request`，主站仍限定`localhost`且保持原API/SPA路径。最小探针返回正常200、错误421、重复400。

更新`tools/smoke_caddy_same_origin_https.py`后，固定官方Caddy输入及P15/布局21,103件Hash重验，index/JS/CSS字节、health200/UP、默认API404、未知API404不回退HTML、SPA深链200均保持；错误Host 421、重复Host 400；Caddy/API子进程正常退出，合成证书目录清理，`C:\PLMTool`不存在。定向单元2/2，真实PoC`SYNTHETIC_CADDY_HTTPS_HOST_BOUNDARY_PASS`。无正式包/服务/DB变更，`release_eligible=false`。

下一项P21-A02：对真实生产登录路由在合成PostgreSQL/License信任源和Caddy HTTPS入口下验证Host、Origin、Cookie Secure/HttpOnly及CSRF拒绝；P21-A03再单测SSE。正式客户证书、目标账户/ACL、NOTICE、Server2025、Debian13与Gate均开放。
