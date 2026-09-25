# PRJ-04-A11-P02：Windows 显式平台成员更新组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A11-P02。输入：P01 可选成员 PATCH、PRJ-02-A03 内部版本化历史、既有 Windows 显式平台信任源门禁；决策 DEC-20260925-071。
- Changed：`--platform`/`--platform-write` 仅在 Schema、License、Secret/成员 cursor 来源全部就绪后挂载成员 PATCH，复用真实 Session、ProjectManager 授权、历史与 Audit。默认登录模式维持 404；缺信任源拒绝启动且不发布路由。
- Files：Windows 组合根、组合契约与临时 PostgreSQL 验证、决策/状态/版本记录。
- Migration：无新增；目标库需已有 `0014`。API：挂载冻结成员 PATCH 路径，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 416/416 PASS；PostgreSQL 18 临时库 `--platform`/`--platform-write` 真实 Session 200/ETag、旧版本 409、非负责人 404、合成 License 403、仅一次历史/Audit、缺成员 cursor 密钥拒绝启动 PASS；开发 wheel PASS。临时库已删除，服务停止。
- Result：Windows 显式合成组合 PASS；正式目标账户信任源、Server 2025/HTTPS、PRJ-04 整体、Gate 3 与最终程序包未完成。
- Known Issues：Debian 13 按用户指令暂不验证；发行信任源仍需工作台操作员仪式和目标账户材料。
- Next：PRJ-04-A12 成员暂停/恢复/移除 HTTP 前置核查，重点检查状态命令的持久幂等。
