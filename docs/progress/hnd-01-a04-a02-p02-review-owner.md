# HND-01-A04-A02-P02：Handover Subject Owner 与 Review 内部链

日期：2026-10-05。结论：`HND_01_A04_A02_P02_REVIEW_OWNER_PASS`。下一项：`HND-01-A04-A02-P03` Review HTTP合同与生产组合前置。

## 实施结果

- 新增真实`HND-02` PROJECT Subject Owner与PostgreSQL仓储，复用通用Review创建、开轮、决定、撤回事务内核，不新建第二套Review表或审批状态机。
- 创建限ACTIVE Analysis的最新DRAFT Version，返回固定`HANDOVER_ALL_V1`政策；送审重验当前全部评审人、Version内容指纹、项目DocumentVersion来源、Evidence资格、当前Approved Capability、AI Task provenance和敏感Item非取消Action覆盖。
- Review开轮后原子绑定Version为IN_REVIEW并推进Analysis强锁；非终态决定保持锁。只有全员APPROVE终态再次重验当前评审资格和全部业务事实，随后原子确认所有Item、批准Version、替换正式指针并在需要时SUPERSEDE旧正式版。
- RETURN/WITHDRAW终态把Version收敛为RETURNED，保留Item CANDIDATE和既有正式指针；撤回允许在来源漂移时释放锁，不把无法继续的Review永久卡死。
- 创建/开轮/决定/撤回重放继续由通用持久收据和当前Project权限控制；Owner重放仅验证固定Subject当前可访问性，不重做历史批准。

## 兼容偏差与修复

真实链发现并按`CR-HND-004`修复两项不兼容：Schema0101共享触发器跨表字段解析，以及批准后Version仓储错误要求正式指针为空。前者改为表名分支后访问字段；后者允许在保留正式指针、无IN_REVIEW且强锁匹配时创建下一Draft。两项均未扩大角色、跳过Review或改动冻结Operation。

## 验证证据

- Windows 11/PostgreSQL 18.6全新临时库完成Schema head/drift、真实Session/CSRF/Project成员、Review create/start/approve、批准后新建V2、第二次create/start/withdraw；最终V1 APPROVED/CONFIRMED且仍为正式指针，V2 RETURNED/CANDIDATE。
- 修正版P01 Schema验证再次全新库通过；P02标记`HND_01_A04_A02_P02_REVIEW_OWNER_PASS`。
- Handover/Review定向36项通过；后端全量2667项通过、3项既有条件跳过。
- 开发wheel构建并解包导入Owner/Repository/Schema0101通过，SHA-256 `3954fa5175350eb61ec36ea410d150f0e7ae56e4ccb1a5b014060922bc8e08eb`。

## 升级、回滚与剩余边界

无新Migration revision、表列、公开HTTP、依赖、网络、Secret或数据外发。Schema0101尚未发布，可在当前开发分支修正；已安装旧0101开发库须向前修复，不能依赖重复执行同revision。停止装配Owner可关闭新的Handover Review写入，但已提交历史不可删除。P03前尚未开放Handover Review HTTP或Windows生产组合；Gate 3继续BLOCKED。
