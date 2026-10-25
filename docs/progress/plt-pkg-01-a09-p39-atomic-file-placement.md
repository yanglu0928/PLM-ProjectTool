# PLT-PKG-01-A09-P39：Windows 新安装文件原子落地隔离验证

日期：2026-10-01；状态：`NON_RELEASE_ATOMIC_FILE_PLACEMENT_PASS / FORMAL_INSTALL_BLOCKED`。输入为 P33 固定非发行 ZIP、P22 父 ZIP、P34 暂存与 P38 正式安装阻断项；不变更 Gate 2 冻结基线。

编码前检查：Phase 2/Gate 3 开放；本任务仅处理新安装文件落地，不处理已有安装升级。涉及安装工具，无实体/API/权限/Migration 改动。验收：来源及暂存全量校验先行；仅允许全新 ASCII Temp 直属目标，先复制至同卷私有待发布目录、逐文件 Hash 读回、再一次目录 rename；普通复制异常只回收本次待发布目录且目标仍不存在；已有目标不可覆盖。风险为目标误选、错误清理、异常中断留下半成品及误将文件就绪等同正式可用。

`tools/install_windows_caddy_go_atomic_rehearsal.py` 固定校验 P33/P22 谱系及 P34 逐件 Hash，复用确定性 21,115 项映射。待发布目录由 `mkdtemp` 在目标同卷 Temp 根创建，复制时以 `xb` 排除覆盖，来源/目标 Hash 与精确文件集读回通过后才 `os.rename` 到尚不存在的新目标；同时创建空的 plugins/data/logs/license 目录。对可捕获的异常，仅在确认目录仍位于 Temp、名称属于本工具且无链接后删除该私有目录。**进程被强杀、断电或存储错误后的待发布目录可能保留，尚无自动断电恢复/耐久性证明；绝不自动清理未知目录。** 不覆盖用户已有安装，不提供升级回滚。

定向单元 4/4：成功发布及空目录、注入复制中断后的仅私有目录回收、已有目标拒绝且内容保留、未验证来源在复制前拒绝。实际 Windows 11 固定 P33 候选落地到 `C:\Users\17231\AppData\Local\Temp\plm-install-rehearsal-p39-20261001a`，返回 21,115 项、P33 SHA-256 `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`、映射 SHA-256 `d4072ed23558da5026911fad3575ee8b4d67944814b58096b6587c1bf9908580`；独立 `verify_layout` 随后全量文件集/Hash 再验通过。未动 `C:\PLMTool`、SCM、证书或数据库。

兼容性：Windows 11 隔离新装文件验证；Server 2025 未运行，Debian 13 按用户要求暂缓实机但仍为发行目标。升级说明：本项无数据迁移，也不是升级工具。回滚/恢复：在正式发布前，捕获异常清理本次私有待发布目录；发布后仅弃用此临时布局，不操作客户数据。正式安装前还需目标账户/ACL、证书/License、服务与 PostgreSQL、法律和平台验收；`release_eligible=false`。

下一项 P40：为进程崩溃遗留的私有待发布目录设计可验证的只读发现与受控恢复，随后才考虑正式安装根的 ACL/服务编排；不得从 P39 的单次 rename 推定断电或升级恢复通过。
