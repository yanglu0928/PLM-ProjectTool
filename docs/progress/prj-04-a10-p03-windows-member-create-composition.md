# PRJ-04-A10-P03：Windows 显式平台成员创建组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A10-P03。输入：P02 可选成员创建 HTTP、P01 幂等快照、既有 Windows 显式平台信任源门禁；决策 DEC-20260925-069。
- Changed：在 `--platform`/`--platform-write` Schema、License、Secret cursor、成员 cursor 全部就绪后，以现行 Session、ProjectManager 授权、Audit 和通用收据装配成员创建。普通登录模式维持 404；缺信任源拒绝启动且不发布路由。
- Files：Windows 组合根、组合契约与临时 PostgreSQL 验证、决策/状态/版本记录。
- Migration：无新增，目标库需已有 `20260925_0016`。API：挂载冻结 `POST /api/v1/projects/{project_id}/members`，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 413/413 PASS；PostgreSQL 18 临时库 `--platform` 和 `--platform-write` 真实 Session 同 Key 两次 201 仅一成员/Audit、非负责人 404、合成 License 403、缺成员 cursor 密钥拒绝启动 PASS；开发 wheel PASS。临时库已删除，服务停止。
- Result：Windows 显式合成组合 PASS；正式目标账户信任源、Server 2025/HTTPS、PRJ-04 整体、Gate 3 与最终程序包未完成。
- Known Issues：Debian 13 按用户指令暂不验证；发行信任源仍需工作台操作员仪式和目标账户材料。
- Next：按 Project/Department WBS 推进下一个未完成可独立任务；不以本项替代正式生产信任源验证。
