# PLT-PKG-01-A09-P51-A24：Web 静态服务与离线启动链集成编码前检查

- 日期：2026-10-28
- 阶段：Phase 2 Platform Core；Windows 11 内部试用包关键路径
- WBS：PLT-PKG-01-A09-P51-A24
- 前置：A23 缺凭据失败关闭 PASS_LIMITED；hosted Windows run 40614113243 全7 jobs成功
- 输入基线：当前 Windows 父包构建链、embedded backend 父包、同run frontend dist、PG18.6/pgvector 0.8.6；正式 License/架构仍按已冻结基线
- 涉及模块：Windows 非发行候选打包、静态Web服务装配、hosted Windows 验收
- 涉及实体：父包 ZIP / manifest / payload hashes；不改业务数据库实体
- API：不改冻结 API Contract；只接入现有 /api/v1 和 /health 反代路径
- 权限：不增加身份权限；产品启动继续要求真实凭据/信任材料，缺失时 fail closed
- 验收标准：同提交前端与后端来源校验；Caddy 2.11.4 官方 Windows AMD64 ZIP 核对已锁定尺寸/SHA-256/发布 SHA-512；将静态服务文件作为明确标注 legal_clearance=false、release_eligible=false 的非发行组件并计入包哈希；hosted Windows D盘临时目录解包后通过静态 SPA 路由与 API 路由配置/进程探针；确认对外监听和生产服务未开启；全量构建工作流成功
- 风险：Caddy 的第三方法务审核未完成；TLS证书和密钥不得进入包；正式产品公钥仍缺失；真实 API 入口仍未就绪；不允许以loopback候选验收推定Pilot或正式发行可用
- 差异方案：既有 unified/Caddy 离线打包器绑定旧父包目录、旧内容哈希与 legacy runtime layout，无法安全复用。采用最小兼容改造：仅为当前 same-run parent assembler 增加一个显式校验的 Caddy 输入组件及 loopback-only Caddyfile template；不改旧冻结构建链。启动脚本先检查配置/证书/凭据并调用既有产品入口，失败即不启动 Caddy；临时烟测只验证静态文件及 /api 路由映射，不提供正式 TLS。
- 迁移：新 parent manifest schema 增加 edge 组件来源与摘要、版本和阻断标志；旧候选包保持原格式与可读性
- 回滚：移除新 edge payload/manifest字段并回退至A23父包构建器版本；不动数据库与安装根；产物仍保留在短期 Actions artifact
- Secret 检查：不读取任何Credential内容、不收录私钥/证书/API Key；拒绝证书/私钥扩展和未列举 ZIP 项
- 运行边界：所有程序、临时解包、Caddy和PG仅 GitHub hosted Windows runner 的非C盘临时目录；绝不在用户本机运行

## 证据与实现前提核对

- 当前 parent builder 固定加入 embedded runtime、frontend/dist、PG 和无敏感配置示例，严格校验同提交来源并逐文件哈希读回；当前 smoke 已安全探测生产入口未监听。
- 当前 package 不含 Caddy、Caddyfile、启动脚本或安装工具；仅有前端构建产物，不存在可服务SPA的Web进程。
- 既有 Caddy 偏移：旧包布局为 runtime/caddy、runtime/python 与 app/frontend/dist；当前包布局为 payload/runtime/python.exe、payload/runtime/packages 与 payload/frontend/dist，且旧构建器固定旧父包与输入哈希，故不直接复用。
- 当前已锁定 Caddy 2.11.4 的 Windows amd64 官方 ZIP（17,559,418 bytes，SHA-256 1708333f79e274c7697285afe6d592ab39314e0b131e9ec6bea08ad27df62ebf）；官方 ZIP内只有 caddy.exe、LICENSE、README.md；已知 Caddy Apache 2.0，但第三方法务放行仍为 false。打包时只纳入程序/License/版本说明，不纳入证书/密钥。
- A24只建立可重复的受限 Web 静态候选及启动链守门，不声称生产 API 可启动、HTTPS、SCM/ACL、安装/升级、OCR、UAT、Gate 或 Release 通过。

## 变更前风险和验证

- 新增输入下载需严格固定官方 URL、大小及 SHA-256，并再次与官方发布 SHA-512 清单比对。
- 新增 package component需验证无路径穿越、符号链接、大小写碰撞、凭据文件、证书/私钥或Secret命名文件。
- 只允许临时回环测试；端口选动态可用端口，测试结束释放并确认进程停止、目录清理。
- 变更前建立本记录；修改仅限 A24 所需构建、烟测、工作流、manifest与本进度文档。
