# PLT-PKG-01-A09-P51-A16：离线升级后应用启动整合前置

日期：2026-10-26。状态：`PRECHECK_READY`。

## 编码前检查

| 项目 | 结论 |
|---|---|
| Phase / WBS | Phase 2 / `PLT-PKG-01-A09-P51-A16`。A14文件级替换/人工恢复和A15新建隔离布局启动各自通过，但不是同一次升级会话。 |
| 输入基线 | 固定旧候选SHA `4f090636986c5c2173a5fde48eb161a94e5ee285ce73a8deb529c8682e048f46` 与新候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；`CR-PKG-011`、`CR-EXEC-002`；A02原子落地、A14升级恢复、A15包内HTTPS Ready/Live记录。 |
| 唯一问题 | 在一次隔离维护窗口中，能否把旧候选升级到新候选的真实安装目录映射（`runtime/`、`app/`、`plugins/`、`data/`、`config/`、`license/`），保留持久目录并在新应用布局上完成包内启动/健康检查，且失败时由独立人工恢复还原旧应用。 |
| 已知差异 | A14仅把整个ZIP payload放在测试根`app/`下，明确是文件替换原型，不是产品目录布局；A15的HTTPS smoke则从stage另建真实运行布局，与A14升级根未串接。不能把A14+A15两个独立PASS拼成升级后应用启动PASS。 |
| 范围 | 仅Windows11、两份已锁候选、一次性ASCII Temp根、合成data/config/license/plugins marker、包内Python/Caddy/PostgreSQL与合成凭据；loopback绑定。正式根、SCM、真实数据库/Vault数据、客户资料和真实License材料禁止接触。 |
| 验收 | 旧/新 payload 均在实际运行目录逐件哈希；仅允许本轮创建且有owner记录的根；停写/旧进程静止由本runner限定为未启动；先人工备份旧 `app/runtime`，再原子切换映射；新候选HTTPS Ready/Live与前端资源成功；注入切换后故障时不自动回滚，由显式恢复动作恢复旧目录并保留失败版；markers不变；候选状态/Secret/Vault/进程/PG/临时目录清理可审计。 |
| 风险 / 回滚 | 这是非发行测试流程，不具备真实维护锁、目标服务账户ACL、正式Migration/插件兼容策略，也不等于正式升级工具；如果A15 smoke无法安全复用已升级目标布局，先记录设计差距，拆分为runner适配子项，不伪报整合PASS。产品安装器/正式配置不在本WBS改动。 |
| 预计修改 | 独立validation runner、最小测试、进度/状态/版本说明；如发现现有测试工具边界缺陷，只改非发行验收工具。无产品API/Schema/Migration预期。 |

## 验证计划

1. 先复核 Current App payload映射及 `smoke_current_app_packaged_https` 的layout callback/清理契约，证明可以将升级后的同一目录交给 smoke，而不是从stage另外复制一份。
2. 编码前确认安装映射、源/目标根、owner记录、失败注入点、恢复动作和敏感目标只读拒绝行为。
3. 用小型单测覆盖布局映射/切换/恢复，再按固定SHA做Windows11真实包集成；完整检查API/HTTPS Ready/Live、静态资源、未授权拒绝、process/PG/Vault/目录清理与候选未变。

## 下一项

此整合成功后回到 `STATUS.md` 中未闭合的Windows11 Pilot安装/信任/完整业务链；任何PASS都仍是合成非发行证据，不关闭Gate 3～7或正式Release。
