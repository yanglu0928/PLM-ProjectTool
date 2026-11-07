# PLT-PKG-01-A09-P51-A49：突出第一条 readiness 待办

- 日期：2026-11-02
- 状态：PASS_LIMITED
- Hosted 验收：[workflow run 41388401825](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41388401825)，12/12 jobs 成功。
- 源码 head：`c2dfcdbeeaded2de37432844fc61baad6e8873db`；PR merge commit：`daea9355f408a85ff6063657ef93af10858ac9db`。
- 用户本机未运行代码；仅GitHub hosted Windows Server 2025/D盘 runner temp。

## 变更与验收

JSON新增 `recommended_first_action`，与 `recommended_actions[0]` 完全一致。中文可读输出将其放在有序列表前。零待办时不显示“建议先处理”，而显示仍需独立核验；授权值继续为否。完整 smoke 覆盖不完整/完整 blocked/完整零阻断/无效登记；未知键和哨兵不回显，候选 manifest/checksum 不变。

- Hosted全12 jobs成功；后端3,849项、前端构建、固定来源重建、临时PG18.6/pgvector 0.8.6、父包、A17/A34组合通过。
- 父ZIP SHA-256：`07d74e91529ef35f3215dd6d5045a59152fc778345825df8aa37a0f49c88920c`，20,122 files。
- 父artifact ID `13116018572`，外层SHA-256 `18af359c4ad288ccaa85a2012e2a21efb51edb6fcca20819ed806b903d2330f1`，372,794,331 bytes。
- readiness smoke artifact `13116722754`：完整零阻断 synthetic manifest 下仍 `complete_zero_blockers_still_not_authorized=true`。
- A17 29次合成API，customer decisions=0，artifact `13116449940`，PASS_LIMITED。
- A34 旧/新20,119/20,122 files，显式手动恢复通过，artifact `13117120058`。

## 兼容性与限制

仅增加只读报告字段/文本，不变更API/DB/License及退出码，无数据迁移。未安装/启动产品，未产生Windows 11新实测。正式公钥/License、DB凭据身份、服务ACL、TLS和法务放行仍缺；Pilot/Gate 3/正式Release保持NOT_READY。
