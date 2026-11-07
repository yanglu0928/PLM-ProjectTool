# PLT-PKG-01-A09-P51-A34：父包离线替换与显式恢复演练结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（GitHub hosted Windows Server 2025 非发行候选隔离演练）
- GitHub Actions run：[41020308619](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41020308619)，11/11 jobs success。
- 分支/提交：`feature/p51-a33-launcher-checksum-recovery` / `58126461958fd79f86147e742eb5a8c6890902c9`。
- A34 job：`123949083574`；证据 Artifact `12961777833`，SHA-256 `d284a29542f01825da7375151449030c754f7a8cf63a48c37f897f9758b5e325`。
- 环境：GitHub hosted Windows Server 2025；项目执行及临时安装根均在 runner D:；未在用户本机运行项目代码。

## 验收结果

- 从旧父包 run `40995913354`（提交 `2e20a1f5f907ae88e5f194d1c2196fe1657bc2e5`）替换为本次 run 同提交的新父包。两份均为20,119个已核验文件；旧候选 SHA-256 `f4d417998ba18bb340fb3d39d83a5c356ac73109a894c1f214852f6b72ed4d49`，新候选 SHA-256 `887ec0d392e596565733200b10ae729f26cfead6ef2ab5f1aa6f27ec0992825a`。
- 完成隔离初装、整包替换、失败注入及显式手动恢复。失败候选已隔离，`provenance/` 留存；替换期间新候选保持活动，未自动回滚。
- data/config/license/plugins 四类合成持久化标记均保留（4/4）；显式恢复旧包通过。未接触用户安装目录、客户数据、系统服务或正式数据库。
- 恢复后的包 launcher 仍返回 `BLOCKED`/exit 1，六项阻断码与固定拒绝提示符合 A33；service、产品 API、listener 均未启动。未改变正式信任或放宽启动安全限制。
- A34 focused tests 4/4 通过；同 run 前端、后端、PG18、嵌入式 Python、父包组装、PG smoke、A17 PlanVersion packaged flow 及 A34 job 均成功。

## 偏差及修正

- 多轮复验发现并逐项记录后修正：旧 A16 工具布局不兼容；workflow job-level `runner.temp` 解析失败；runner PowerShell 执行策略限制合成 launcher；父包 `provenance/` 清单被误拒；stderr 固定提示漏写 `production`。修复仅调整 A34 验收工具、fixture 和 workflow TEMP/TMP 边界，不更改产品安装器或安全语义。未通过的历史 run 保留为失败证据，未追改为成功。

## 边界与后续

- 该结果只覆盖 hosted Windows Server 2025 上非发行父包的 D 盘隔离替换/恢复演练，不代表 Windows 11 实机安装、重启、升级或用户验收。
- `release_eligible=false`、`legal_clearance=false`；正式产品公钥/License trust、数据库凭据、服务账户 ACL、TLS、Windows 11 实机、Gate 3～7、Pilot 和正式 Release 仍未通过。
- 后续优先检查 Windows 11 Pilot 包清洁离线落地/重启验证的可执行路径；若 hosted 环境不能代表 Windows 11，则保留为明确设备验收缺口，不以 Server 2025 结果推定兼容。
