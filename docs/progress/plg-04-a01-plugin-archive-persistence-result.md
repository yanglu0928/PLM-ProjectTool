# PLG-04-A01 Hosted 验收结果

- 日期：2026-11-06
- Change Request：CR-PLG-015
- 结果：PASS_SCOPE_LIMITED
- 验收提交：`eebc0420720eb1677ada7314faa1c198115544b4`
- Hosted run：[42070621770](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42070621770)

## 通过项

- 后端4,071项、P51-A32 smoke 5项、合成Developer Workbench key tests 5项、wheel；前端测试/build；PG18/pgvector sidecar重建。
- Windows离线后端与父包候选构建；clean parent extraction/PG18 smoke；A35分块交接；P24/A50；A34替换与人工恢复演练。
- A17 packaged PlanVersion Edge/HTTPS/PG flow成功。其PLG-01-A08 synthetic package worker路径通过：验证后登记，精确原始ZIP字节进入私有包locator，且Job finish在存储之后；失败staging恢复重试保持通过。
- 独立单测覆盖包locator/尺寸、首次原子无覆盖写入、摘要绑定精确重放、已存字节篡改拒绝、导入Worker存储失败进入有限重试且不finish。

## 偏差轨迹

1. run [42063771396](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42063771396)：A17合成验证器构造Worker未注入新增archive_store Port；已先记CR-PLG-015，随后仅修验证器composition。
2. run [42067292485](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42067292485)：A17已有总文件数断言固定3，未计入新增私有Plugin包ZIP；已先记CR-PLG-015，随后保留原有3个上传对象断言并独立比较唯一归档字节。
3. 最终run [42070621770](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42070621770)：A17通过；工作流唯一失败是独立P25 HTTP/Edge。P25随包 `initdb.exe` 在创建数据目录前返回 `0xC0000135`，未启动真实HTTP/Edge，继续BLOCKED_DIAGNOSTIC，不是本WBS产品包存储断言。
4. 所有产品与测试执行均为GitHub hosted Windows Server 2025 runner D盘，不在用户本机/C盘运行。

## 限制与下一步

本次仅PASS_SCOPE_LIMITED；不表示Windows 11实机安装、Gate 3、Pilot、正式Release、生产publisher trust或插件运行通过。生产signer trust仍为空；无客户数据或真实插件执行。下一WBS为PLG-04-A02，将只读PackageArchiveEvidence接入InstallationOwner的事实记录前置；不执行解压/插件。
