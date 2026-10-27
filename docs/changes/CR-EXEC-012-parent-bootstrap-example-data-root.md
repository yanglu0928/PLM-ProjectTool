# CR-EXEC-012：父包Windows bootstrap样例改用非C盘数据目录

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：PLT-PKG-01-A09-P51-A20、CR-EXEC-002、PR #55
- 范围：仅生成的 Windows 父包内 bootstrap example 与快速配置说明；不改后端默认值、数据库凭据来源或生产配置。

## 证据

A18父包由同run backend/frontend/Python/PG组件组装，但未包含 bootstrap sample/quick-start。仓库源样例 `apps/backend/config/bootstrap.example.yaml` 中的 `data_root` 默认是 `C:/PLMTool/data`，不符合用户2026-10-27对本机空间的明确偏好；A19已证明父包在 hosted runner D盘临时根的临时PG生命周期可运行，但没有应用启动或真实配置验收。

## 决策与差异

仅在父包装配时从受审源示例复制配置至 `payload/config/bootstrap.example.yaml`，将示例 `data_root` 设置为绝对路径 `D:/PLMTool/data`；源仓库原始示例保持不变。随包加入 `payload/README-FIRST.md`，明确这是示例而非已初始化配置，部署前必须按目标机器选择绝对数据目录并安全创建/授权。不得放入PG密码、API Key、License材料、MAC样例或AI外发策略。

## 风险、回滚与验证

- 部分Windows环境无D盘；说明要求先确认磁盘和目录权限，或改为目标机其他有空间的绝对目录。配置校验仍要求绝对路径。
- 配置样例不代表正式License信任、Windows Credential Manager数据库凭据、SCM账户/ACL、HTTPS代理或服务已配置。
- 回滚时可移除父包新增样例/说明，不改变服务代码与用户源配置。
- Hosted CI要校验样例数据根不是C盘、配置无禁止Secret键、敏感值或测试身份；父包全清单/摘要readback仍必须通过。
- 非发行和法律未放行边界不变；不能称内部Pilot已可用。
