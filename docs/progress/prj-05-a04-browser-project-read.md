# PRJ-05-A04 Windows 11 真实浏览器项目读取联调

2026-09-28 / 0.1.0.dev0 / PASS（Windows 11 合成浏览器+独立真实 HTTP/PG 两轮证据）；正式发行未验。

编码前检查：Phase 2 / PRJ-05-A04；输入冻结 PROJECT_LIST/GET、PRJ-04-A02 Windows 显式平台组合、PRJ-05-A01～A03 前端、既有 AUT-05-A05 浏览器脚手架；Gate 2 与本机 PostgreSQL 18.6 运行前置满足。涉及仅独立验证脚本，不修改正式实体、API、权限、Migration 或依赖。权限仍由真实 Session/Project SQL 及显式组合服务端重核，License Guard/游标签名仅本轮合成注入。验收：实际浏览器在 Windows 11 对隔离 PG 的成员项目列表/详情、跨项目 404、管理员无成员空列表、最终数据库计数和自有服务/库/角色/Vault 清理；不把合成信任当正式发行。风险是浏览器会话或轮次切换打断 fixture；只用唯一命名临时资源，回滚删除独立脚本并核对自有资源。

Changed：增加独立 `validation/prj-05-a04-browser-project/serve.py`。每次创建随机 `prj05a04_` 数据库/同名登录角色、两名合成用户和两个合成项目（仅一项目有一个有效成员），真实 Scrypt 密码、Windows Vault 数据库凭据、当前 Migration head、Windows 显式只读平台组合、Uvicorn/Vite 代理；License 和游标密钥在验证进程内合成注入，正式生产信任源不变。脚本在收到 VERIFY 时断言两个项目、至少两个 Session、一个有效成员，再清自有服务/库/角色/Vault。

Observed browser：本地 IAB 实际登录 Synthetic Project Member，服务端返回 1 个项目；`/projects` 只显示 `Synthetic Owned Project`，详情显示 OWNED/进行中。直接访问另一合成项目地址后页面无内存身份、不请求项目；从账户页显式读取当前 Cookie 身份再返回该地址，页面显示统一“项目不存在或无权查看”，未显示外项目正文。随后实际登录 Synthetic Project Admin，身份为部署管理员/授权项目 0；`/projects` 显示空列表及“管理员身份本身不授予项目成员权限”。管理员经页面退出成功。页面截图检查中文布局无明显遮挡；此观察不证明完整响应状态码、正式 HTTPS 或三平台。

Interruption：关闭临时浏览器页时 UI 工具操作被中断，原交互进程句柄随轮次切换消失，原隔离 PostgreSQL 服务也非正常停止。因此脚本的 `VERIFY` 终态 SQL 计数及自动清理分支未执行，不能记为完整 fixture PASS。随后用原数据目录恢复 PostgreSQL 18.6，确认唯一残留 `prj05a04_2bfb2b9c4fec` 库由同名角色持有、无活动连接，Vault 仅有一个 `PLMProjectTool/Test-...` 合成目标；只删除这些精确自有目标，复查库/角色均 0 且无 Test 凭据。服务原为运行状态，已恢复运行。未删除用户或生产数据。

P01 原始记录：验证脚本 `py_compile` PASS；前端139/typecheck/build来自A03，本项未重跑。实际浏览器行为如上；原后端PRJ-04合同/PG测试为已有证据，非本项重跑。P01没有终态SQL计数或HTTP原始状态码；原计划下一P02补验。后端全量/coverage/性能、正式License/HTTPS/Server2025/Debian、CR-AUT-008性能FAIL、Gate3/可用包仍待。

P02 补验（独立新 fixture，非追写被中断的原运行）：在原脚本增加 `--api-only` 自动退出模式，真实 Uvicorn/Vite/Windows 显式只读组合、独立 PG/Vault 与合成 License。httpx 通过网络核验无 Cookie 列表401、成员登录200/列表200唯一OWNED/详情200且响应强 ETag匹配、外项目404 RESOURCE_NOT_FOUND且不回显正文、管理员登录200/列表200空/成员项目详情404。终态 SQL 断言恰好2项目、2 Session、1有效成员；进程退出码0，脚本输出自有服务停止、临时库/角色不存在及Vault目标缺项1168。随后从PG目录独立复查 `prj05a04_%`库和角色均0，`cmdkey`无 Test 凭据。`py_compile`重跑PASS。两轮证据分别覆盖真实浏览器呈现与真实HTTP/SQL，不能把第二轮数据库计数冒充第一轮浏览器的原库计数；第一轮中断事实保留。Windows11合成范围 A04 收口PASS，正式信任/HTTPS/Server2025/Debian/后端全量/coverage/性能/Gate/程序包不据此通过。

下一 PRJ-05-A05：管理员创建项目的前端客户端合同。当前管理员可以登录和看到空项目页，但还不能从UI创建第一个项目；后端冻结PROJECT_CREATE及Windows显式写组合已具备。先核该写操作的CSRF/幂等/首次ProjectManager/不确定结果合同，再分任务实现界面与真实联调。
