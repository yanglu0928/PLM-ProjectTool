# PRJ-04-A15-P02：Windows 显式平台 Department 修改组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A15-P02。来源：冻结 API-01/02、PRJ-03-A03、PRJ-04-A15-P01；决策 DEC-20260925-083。
- Changed：仅在 `--platform` 与 `--platform-write` 既有门禁通过后装配 Department PATCH 服务与 Router；默认登录模式仍 404。
- Compatibility/Upgrade：冻结 `/api/v1` 不变，无新 Migration/依赖；目标数据库须已升级至 `20260925_0018`。
- Tests：Windows 11/Python 3.13 后端 437/437 PASS；PostgreSQL 18 临时库两种显式平台真实 Session 修改、强版本冲突、非负责人、合成 License 拒绝及缺部门游标信任源关闭 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：Windows 显式平台组合 PASS；正式信任源、Gate 3 与最终程序包未完成。
- Known Issues：Server 2025/HTTPS 与 Debian 13 本项未验证；合成许可不代表正式发行验收。
- Next：PRJ-04-A16 Department 停用前置核查。
