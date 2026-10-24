# Windows API业务数据库池：受控档位

缺省`api_database_pool_profile: DEFAULT`，沿用API业务池5+10；不填写该字段也不改变旧部署。候选档位仅可在完成目标服务器资源核算后，于非Secret `bootstrap.yaml`显式配置：

```yaml
api_database_pool_profile: TWENTY_FIXED
```

该档位为单API Worker业务池20+0，不改变独立维护准入池、Audit/Parser/AI Provider Worker池，也不开放Prototype资格。启动会读取目标PostgreSQL 18版本号、最大连接与保留连接设置，普通连接名额不足80、读取失败或配置值非法则拒绝启动并清理Runtime；拒绝不代表自动回退，以免掩盖容量错误。调整前须逐项记录目标实例实际PG设置、所有API/Worker/维护/人工连接消费者、内存和负载余量，并运行20并发两项资格P95≤500ms重复验证。Windows11合成测试曾有超标轮次，Server2025尚未验证，不能将本档位称作发行推荐值。

回滚：将该项删除或设为`DEFAULT`并按正常维护窗口重启API，回到原5+10；不涉及数据库迁移或历史数据。禁止仅为达到数字目标而减少Review、授权、文件本体或Requirement当前性证明。正式部署还须满足License/信任源/SCM/Gate/UAT独立条件。
