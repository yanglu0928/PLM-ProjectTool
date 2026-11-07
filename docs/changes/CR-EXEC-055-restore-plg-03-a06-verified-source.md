# CR-EXEC-055：恢复 PLG-03-A06 已验收源码与 Hosted 验收接线

- 日期：2026-11-07
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A06 recovery
- 状态：偏差及恢复方案预先登记；恢复与Hosted复验待执行
- 发现提交：481e4bf335ea20b716144a075654398246f134da
- 受影响基线：CR-EXEC-053、A06结果记录、验收源提交 e51389455c165e5081a9d72f61b800c13dbe549a

## 发现与影响

PR head 的源码树缺失 A06 的 `execution_start.py`、`execution_start_repository.py`、单元测试、PG18验收器和独立workflow job。GitHub提交差异确认这些文件/job在481e4bf被删除；该提交同时保留A06 PASS_SCOPE_LIMITED及run 42348507961的历史记录。因此历史云端证据仍有效，但当前分支无法从源码复现对应Owner/专项验收，A06不能作为A07的当前可执行前置条件。

## 编码前恢复检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：A06恢复：找回已验收实现和云端验收接线
输入基线：CR-EXEC-053、A06验收run 42348507961、其验收源提交e51389455；当前缺失文件已由481e4bf删除补丁证明。
范围：仅恢复原验收文件与workflow job；另增加本CR、状态和变更日志。不得顺手重写Owner或拓展A07。
Schema/API/Migration/默认Worker/ProcessHost/生产信任：不变。
验收：恢复文件与e51389455逐内容一致（除本WBS必要的新后续文档）；Hosted Windows Server 2025 D盘运行A06专项PG18与Backend全量/wheel；提交前Secret扫描0命中；准确记录A08独立失败。
风险：树恢复可能遗漏已由后续提交引入的变更。恢复通过3-way比较确认仅覆盖A06原文件及job，并基于当前head非强推提交。
回滚：移除A06专用Owner/Repository/测试/验证器/job及本CR/进度记录；无业务数据或迁移。
```

## 处理计划

- 先恢复A06实现、测试、验证器和Hosted job原文；保留481e4bf之后其余PR内容。
- Hosted A06与全量回归复验通过后，继续已完成预检查的PLG-03-A07；若失败先记录证据并修复A06恢复本身。
- 不运行本机项目代码；所有验收只用GitHub Hosted合成数据。
