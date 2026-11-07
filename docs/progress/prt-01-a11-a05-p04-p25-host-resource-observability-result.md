# PRT-01-A11-A05-P04-P25：Hosted并发负载资源观测器结果

- 日期：2026-11-07
- 结果：BLOCKED_BY_HOSTED_INITDB_DATA_DIRECTORY_ACCESS；观测器单测通过，完整Prototype负载未执行。
- 变更请求：CR-PRT-006
- Hosted run：[42374803790](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42374803790)，PRT job 128411003199；独立观测器 run：[42374803580](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42374803580)。

## 结果

- 定向Windows Hosted job通过：CPU差值计算、计数器异常/不可用、聚合输出约束，以及Windows Server 2025原生系统计数读取均成功。
- 完整run共22 jobs、20成功、2失败。PRT负载job在 initdb.exe 初始化阶段停止，受限摘要类别为 DATA_DIRECTORY_ACCESS_DENIED；本轮PG18 sidecar来源已同run重建、SHA-256校验，完整运行目录与数据scratch均落在runner-owned D盘TEMP。
- Prototype 20并发请求和业务断言没有执行；没有生成新的响应P95或资源关联结论。既有500 ms门槛继续为FAIL。
- 同run独立 SUR-07-A08 失败于 initdb.exe exit 3221225781（0xC0000135）。不得将两项失败合并解释为产品缺陷或成功。
- 同run父包PG18生命周期与P40 live Edge下载以及其他作业按各自限定范围通过；整体workflow仍失败。

## 偏差与停止决定

CR-PRT-006此前已明确：若D盘runner-owned临时路径仍分类为权限拒绝，不更改产品目录、服务账户ACL、安装根、TEMP/PATH猜测或性能门槛，停止此单独初始化路径并转向独立WBS。本轮命中此条件，故不再重试该路径。资源观测器仍可复用，但此结果不完成P25业务验收。

## 兼容、安全与后续

本轮仅GitHub Hosted Windows Server 2025/D盘、合成数据；本机/C盘未运行。无客户数据/Secret外发，无产品API/Schema/Migration/连接池/安全语义变化。Windows 11设备性能、Pilot、Gate 3和正式Release均未通过。后续按STATUS进入GATE-3-A03，盘点当前证据并选择不依赖此initdb环境路径的工作。
