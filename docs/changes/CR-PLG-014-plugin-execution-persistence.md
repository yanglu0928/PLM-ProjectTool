undefined

## 第三轮 hosted PG smoke 偏差（2026-11-05，修复前登记）

- run [41970235945](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41970235945) 的后端全量测试、前端/build、wheel、父包组装、A35、A17 candidate、P24 与 A50 已通过。父包PG smoke在旧P01验证器的合成数据清理断言处停止：`plg_executions`已按PLG-03外键引用`plg_installations`，但既有TRUNCATE测试未把新Execution根及两个子表纳入同一语句，PostgreSQL因此先返回 `FeatureNotSupported`，未进入PLG-03专项迁移验收。该错误是测试夹具清理范围遗漏，不能判定Migration通过或失败；P25仍独立阻塞。
- 修复计划：将PLG-03三张新表列入既有schema presence inventory，并将execution root/result-file/state-event与安装历史相关表一起纳入“批量TRUNCATE必须由保护触发器拒绝”的负例语句；保持原断言、不可truncate约束与业务范围，不使用CASCADE、不删除验收；随后完整重跑GitHub hosted链。
