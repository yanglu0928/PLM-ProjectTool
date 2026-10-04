# EVD-01-A04-P03-A06：资格裁定并发单赢家证明

日期：2026-10-01；Phase 2 Platform Core；结论：`ISOLATED_WINDOWS11_PG18_CONCURRENCY_PASS`。

输入为 A05 隔离 PG18 实证及 Evidence `FOR UPDATE` + CANDIDATE/lock_version 条件更新。范围仅扩展合成验收脚本，不改变业务实现或生产组合。

两个独立线程/事务在访问边界处 Barrier 同步后，用不同幂等键和理由同时裁定同一 Evidence v0；访问替身仅用于移除无关 Session 行锁，以直接检验真实 Evidence 行锁。两次完整隔离重跑均恰好一项 ELIGIBLE/v1 成功、一项 CONFLICT_VERSION；SQL 读回同一行仅v1，整组成功操作 Audit/收据各4条（含其它三条成功资格），失败事务不留下收据。A05 的实际 Session/角色/Document/HTTP 链验证仍独立保留，不能把此访问替身当成权限证明。

两次临时PG均停止并删除自有数据目录；无旧集群或客户数据接触。正式平台组合、压力/性能、Server2025/Debian和Gate3仍未验。
