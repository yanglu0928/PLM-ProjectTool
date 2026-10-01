# PLT-PKG-01-A09-P23：新候选清洁解包与模板HTTPS烟测

日期：2026-10-01；状态：`NON_RELEASE_CLEAN_EXTRACT_AND_TEMPLATE_HTTPS_PASS / INSTALLER_OPEN`。依据P22固定ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`与`CR-PKG-005`。不覆盖旧P15、正式安装根或已有服务。

编码前检查：Phase2/Gate3开放；输入为P22非发行21,110件ZIP、固定Caddy可执行文件/模板及P21 HTTPS合成证据。仅新增隔离清洁暂存/模板烟测工具及新候选kind的通用只读验证支持，无业务实体/API/权限/Schema/Migration改动。验收：仅全新ASCII Temp直属目录，ZIP先全验、解包中Hash、落盘全文件集/Hash、源包末次同一性、模板实际渲染/Caddy validate/静态API Host回环烟测，不能把它当安装器。风险：模板的域名/客户证书/ACL、正式运行账户/服务/三平台/License仍开放。

`tools/stage_windows_unified_caddy_candidate.py`首先独立检查P22固定ZIP，再在`C:\Users\17231\AppData\Local\Temp\plm-caddy-stage-20261001a`逐件清洁解包、读回21,110件及顶层三清单完整文件集；源包末次再核。结果`NON_RELEASE_CADDY_CLEAN_EXTRACT_PASS`；未启动数据库、安装或改SCM。`tools/smoke_staged_caddy_template.py`核阶段内Caddy.exe SHA-256 `5cb9ab71e5756ce72840b8234177a2f40c8b4ab47a806b8e841e2b784e9df62b`及模板SHA-256 `b1a6e6032ee95d401c24b8565d6f719ec6f8f84445fb5d43ef409fd52462b117`；以合成证书、随机回环端口渲染包内占位模板，通过包内Caddy `validate`，启动包内默认API，验证index/JS/CSS实际字节、ready200/UP、默认API404、SPA深链200、错误Host421。`NON_RELEASE_STAGED_CADDY_TEMPLATE_HTTPS_PASS`，Caddy/API子进程均退出，临时证书目录清理。定向新单元4/4、旧暂存回归4/4通过；`C:\PLMTool`不存在。

所用端口替换仅供回环PoC；正式模板默认443，须在安装器中按确定的外部域名、目标证书/私钥ACL、API端口与前端路径渲染，并由目标账户验证。未验证生产登录在**新候选解包布局**（P21仅旧固定布局）、真实AI SSE、正式License/NOTICE、目标账户/Server2025/Debian13/升级/UAT/Gate。`release_eligible=false`。下一项P24规划新候选至安装根的精确映射、四边界/三应用服务职责及账户/证书来源，不直接注册SCM；随后按门禁做正式安装和目标平台验证。回滚弃用非发行暂存目录与新工具，不影响P15历史或数据库。
