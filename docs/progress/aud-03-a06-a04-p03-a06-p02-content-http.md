# P03-A06-P02 内容 HTTP 与资源生命周期

日期：2026-09-26；状态：PASS（可选内容 HTTP，非正式组合/发行验收）。

编码前检查：Phase2；WBS P03-A06-P02；输入CR-AUD-003/增量契约/P03-A05真实当前会话快照；前置PASS。涉及Audit API和入口可选Router，无新实体/DB/权限/依赖，PROJECT实际PM与DEPLOYMENT Admin、当前License/Session重核保持。

目标：两个可选内容GET、128MiB完整JSONL、安全附件头；限额从准备直到清理覆盖；拒绝query/Range/If-Range；正常、prepare故障、响应start/send失败、读失败和任务取消均关闭快照释放槽，取消未完成线程不提前释放容量。

风险/策略：StreamingResponse的background或未启动生成器finally不能单独覆盖response.start失败；专用Response外层finally拥有清理。准备线程取消不等于物理线程停止，显式资源所有权在worker完成前保留，避免孤儿快照和提前释放槽；线程读期间取消也等待该读完成再关闭，由线程最终释放。既有普通下载不顺手修改。

验收：契约/原始ASGI start/body断连及准备/读取消/容量竞争实际执行；真实PG成功来源/双Scope完整字节/复制后撤权/损坏文件最小Audit，默认404。正式Windows组合留P03，三平台/实际代理断网/性能/完整包未验。

## 结果

- Changed/Files：Audit `api/download_export.py` 有界资源Owner/专用Response外层finally和安全错误映射；入口独立opt-in Router；7项契约/ASGI测试、真实PG与文件HTTP验证脚本，以及CR/契约/状态/决策/版本记录。
- Migration/升级：无，head0042不变，无生产迁移；无新增依赖。仅两新增GET，默认404；Windows组合与POST仍未开放。卸载路由可回滚，保所有历史/文件。
- Tests：7新增测试实际执行，覆盖完整头/默认关闭/双路由、错误/query/Range/Host/Cookie、错误MIME/Length/读失败、响应start和body发送失败、response.start等待时取消/尚未启动生成器清理、准备线程取消及读取线程取消后不提前关闭或释放槽，线程结束快照close且槽可复用。
- 实际PG18隔离库/Windows11真实临时文件：完整原子发布来源，双Scope空/260 JSONL完整Hash/字节/头/快照close和七表无业务写；当前Session/PM或Admin/跨Scope/License拒绝不触发文件I/O；复制后真实Session撤销安全401且close/无写；损坏文件安全503 FILE_CONTENT_UNAVAILABLE+单次受权Audit，未知Session无Audit；恢复合成文件后同槽下载成功。附带原原子发布完整回归PASS。
- Windows11/Python3.13全后端962项无失败，2既有符号链接权限跳过。开发wheel成功，577073字节，SHA256 `ebe8772f1511ee1ce4e89e3c076c8fd9924bf29bf87aa736153970405b5d689b`。这是开发包，不是可用安装包。
- Result：本子任务PASS；没有用普通DocumentVersion或静态路径，未扩大权限、格式和Scope。最坏取消不会让仍工作的线程脱离名额；完整快照完成并二次授权后才响应。
- Known Issues：真实代理断网/目标运行账户/三平台/128MiB Worker性能未验证；License合成、系统身份临时Vault。Worker心跳、质量/Gate3/UAT/完整安装包仍待。
- Next：P03显式Windows平台组合、实际HTTP装配回归；保留完整交付目标。
