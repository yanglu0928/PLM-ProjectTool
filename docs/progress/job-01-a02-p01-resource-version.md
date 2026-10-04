# JOB-01-A02-P01：持久化任务并发版本

2026-09-27/Phase2；CR-JOB-002先记录再实现，输入API-01要求真实强ETag与A01缺版本证据。不是以hash/弱ETag绕过冻结合同，原64cdf09/0042内容保留。

Changed/Files：Migration `20260927_0043_job_resource_version.py`新增Job.lock_version bigint>=0/default0与数据库统一UPDATE触发器；Jobs ORM/read事实和Repo包含严格0～bigint上限版本；迁移链契约与Schema unit更新。只排除lease_expires_at及version本身，所有其余实际变化（包括actor/payload/priority/state/attempt/fencing/取消字段）计版本；原写Repo无需逐个手工加一，纯heartbeat不递增，无变化不递增。Version不是Lease权或正文权。

Migration review：触发器比较参数无动态SQL，不调用跨模块表或添加外部依赖，原行锁/事务保证递增；手动UPDATE改版本拒绝，最大版本业务更新拒绝。新写入使用0默认；可信恢复INSERT可保历史版本。downgrade只移除新增trigger/function/check/column，不删除原Job/Lease/结果。数据库写权限能禁用trigger的部署管理员不作为应用攻击面豁免，生产角色与发布门禁仍须验证。

真实验证 `validation/job-01-a02-p01-version/verify.py`：空库全量up→down0042→up；实际原发布已有14Job及Lease/Attempt/Audit/Result/File的数据，down→0042数据快照保留后up0043全部版本0，六业务表旧字段不变。双Scope新接受v0、真实领取v1、实际heartbeat/capture/render版本稳定、发布SUCCEEDED v2；同值UPDATE稳定、手动版本改99 P0001/无改，可信最大版本插入后业务UPDATE溢出P0001整事务回滚六表不变。所有在独立临时库，未生产迁移。

失败记录：第一次数据快照比较失败；先纠正ORDER BY常数错误仍失败，再输出仅表名/数量/差异字段定位为测试SQL重载未显式text[]，导致未去除新列lock_version。加参数text[]类型后完整快照与全验通过，未为通过而改产品或删除业务比较。

API：本轮没有公开GET/If-Match/Router，冻结v<version>格式未改；后续使用实际资源版本。Tests/构建最终结果在本页后追加，未证实前不报整体通过。Known：完整JobView与Owner安全progress/error、GET、取消expected_version、其他Owner/列表/重试、正式材料/20Worker/性能/其他平台/完整包/Gate仍待。

最终Tests/Result：2新Schema unit与读取DTO严格版本边界、迁移head契约，后端1145无失败/2既有权限跳过；实际A01安全读取、P06提交前回滚/提交后lost-ack、混排持续Loop（仍两组25steps/12拒绝/12正常完成）、第三代实际耗尽安全收尾/旧字节和各自原发布回归通过。开发wheel640560 bytes，SHA256 `cde42ecee2ae0e9451b93cc6bab195ea9d6a74f506ecd6d421b24c44b444e539`。内部Schema/原路径验收PASS，非完整Installer/正式License/HTTP/20并发或生产迁移证明。

升级：人工备份→维护模式停API/Worker→0043→新版启动与检查；离线降级必须同时回旧代码、使旧ETag失效重新读取，版本列丢失不能假称保历史版本；不允许生产热降级。本轮只开发验证，原始业务历史保留。Next：JOB-01-A02-P02补完整JobView及可选GET合同，随后显式Windows装配与Audit提交POST。
