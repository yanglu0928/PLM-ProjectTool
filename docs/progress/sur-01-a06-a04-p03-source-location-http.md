# SUR-01-A06-A04-P03：Survey 来源定位 HTTP 与 Windows 组合

日期：2026-10-06。结论：`SUR_01_A06_A04_P03_SOURCE_LOCATION_HTTP_PASS`。下一项：`SUR-01-A06-A05-P01` 前端来源定位客户端与点击交互。

## 实现

- 新增冻结的只读location GET；复用可信Host、Session、Trace和内部Owner的`SURVEY_VERSION_GET` Project权限重验。
- 路径仅接受规范小写非零UUID与`0..99`无前导零ordinal；拒绝query及GET body；成功响应`Cache-Control: no-store`。
- 将内部通用位置严格投影成Handover、Capability或Template互斥公共JSON；MANUAL/无权限/目标缺失返回受控200，不含内部`*_row_id`、正文、locator、文件路径或下载URL。
- location Router组合进既有Windows Survey reads Router，read-only和write模式均开放；未显式装配的默认应用继续404。

## 验证

- 定向46项通过：HTTP合同、投影、防御性错误、内部Owner、Windows组合及生产登录相关回归。
- Windows 11/PostgreSQL 18.6隔离库真实HTTP通过：四类固定来源、默认404、非法query/ordinal、未知question与跨Project隐藏、Handover状态漂移后仍可定位但不再当前合格、零Survey/Audit写入；Alembic head/check通过。
- 后端完整回归：2858项通过、3项跳过。
- wheel：1060 entries，包含HTTP和Windows组合；SHA-256 `7e2575f0fe62d221410fa5d6783195b28ee6c928afa7cfcb7ef42577e523cf1f`。

## 影响与剩余项

无Schema/Migration、既有四读JSON、角色、依赖、配置、Secret、网络或外发变化；删除Router注入即可回滚为404，历史数据不变。A05前端尚未调用该端点，真实浏览器点击定位、定义写UI、Round/Response/Conclusion、Gate 3/UAT及发行仍未通过。
