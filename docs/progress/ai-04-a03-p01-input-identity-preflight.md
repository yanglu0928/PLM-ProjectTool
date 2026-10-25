# AI-04-A03-P01：AITask 输入身份前置核查

日期：2026-10-02。编码前对照冻结 API-01/03、DM-04、Schema0063及当前 Document Owner 解析能力，确认0063输入行缺少公开 `ResourceVersionRef.resource_id`，无法完整证明对象/版本归属。已登记 CR-AI-010/DEC-700，选择0065兼容增量：既有NULL仅保留历史且执行失败关闭，新引用强制完整ObjectId并由显式Owner Port同事务解析。

本项仅设计/记录，不修改运行代码、Schema、API或依赖，不执行新运行测试。无客户数据外发。Next：`AI-04-A03-P02` 实施0065 ORM/Migration和Win11隔离PG18空库/既有数据/约束/升降/漂移验证；随后再接Owner注册与内部AITask创建。
