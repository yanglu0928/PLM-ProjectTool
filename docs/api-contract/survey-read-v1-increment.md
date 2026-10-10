# Survey 定义四读 HTTP V1 增量

日期：2026-10-06。基线：冻结 API-04、Schema0106 与 `SUR-01-A05-A02` 读取 Owner。

实现 `SURVEY_LIST`、`SURVEY_GET`、`SURVEY_VERSION_LIST`、`SURVEY_VERSION_GET` 四条冻结 GET 路径。Router 仅由 `create_app(survey_read_router=...)` 显式注入，默认404；只接受可信Host和当前Session，无CSRF写语义，所有响应 `no-store`，Survey详情返回强ETag。

两个列表只接受唯一的`page_size`/`cursor`，页长1～200。Survey cursor绑定会话、Project、页长和完整`updated_at + survey_id`位置；Version cursor另绑定Survey和`version_no`。均使用专用32字节HMAC密钥、规范Base64URL与规范载荷，篡改、跨会话/Project/父资源/页长重放返回400。

投影仅含Survey身份和不可变Version问题、选项、条件、类型化固定来源及目标部门引用；不读取或复制跨模块正文、文件路径和存储定位。资源/隔离失败404，License403，Project归档409，输入422，未知内部失败503。无Schema/Migration/依赖/Secret/外发变化，撤Router注入即可回滚。
