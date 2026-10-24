# AI-04-A03-P03：输入版本显式Owner解析

日期：2026-10-02；版本：0.1.0.dev0。Changed：新增AI输入三字段公开引用、Owner解析查询/结果和显式注册Resolver；先完整校验/去重再调用Owner，未注册类型、跨项目、Owner返回身份不一致或意外异常均失败关闭。新增DocumentVersion桥接，复用Document同事务授权固定版本解析，并映射为`document/DOCUMENT_VERSION/ObjectId/VersionId`；Project授权矩阵加入冻结`AI_TASK_CREATE`的ProjectManager/ImplementationMember写权限。无HTTP、Schema、依赖或AI外发。

Tests：Resolver/Document桥接/错误掩码/重复输入/跨项目/授权矩阵定向13项PASS；首轮重复引用在第二项才发现，已调整为调用Owner前先完成全组校验，重跑PASS。后端2106运行/3跳过PASS。开发wheel SHA-256 `895c2b4de673045ceb3db79e21edca79d850a61fcecdf2ad7f46c94f13991e46`，非交付包。

Known Issues：当前只显式实现DocumentVersion Owner；Requirement/Solution/Plan等模块尚未落地时保持未注册拒绝。内部AITask创建、外发授权源、Job/AIService、公开API、正式信任、Server2025/Debian、Gate3/UAT/可用包待。Next：`AI-04-A03-P04` 核对并实现内部AITask创建的持久幂等、授权快照来源与Job入队事务边界；缺少可信外发授权Owner时不得伪造。
