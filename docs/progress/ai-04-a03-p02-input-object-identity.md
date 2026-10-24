# AI-04-A03-P02：InputRef ObjectId Schema0065

日期：2026-10-02；版本：0.1.0.dev0。Changed：按CR-AI-010/DEC-700为AITask输入引用增加业务ObjectId、复合身份索引和新写强制守卫；0063遗留NULL只读保留且不可猜测回填。无API、依赖、AI调用或真实外发。

Migration：Win11隔离PostgreSQL18空库及0063遗留NULL历史up/down/re-up、drift=0，新写缺ObjectId/零UUID/跨项目拒绝，完整Owner/Object/ObjectId/Version身份写入后不可改删，遗留NULL不变，非NULL新历史拒降PASS。首轮夹具使用公开`DOC-02`作为内部ObjectType而被既有约束拒绝；修正为Owner解析后的`DOCUMENT_VERSION`并全量重跑PASS。

Tests：迁移/ORM定向7项、后端2100运行/3跳过PASS。开发wheel包含0065，SHA-256 `b0cd5c1288cb2ac278d755068124245b858270a2bd2a6cc53d06a864da7ab7ca`，非交付包。Known Issues：显式Owner注册与同事务证明、内部AITask创建/幂等/授权快照、统一AIService、正式信任、Server2025/Debian、Gate3/UAT/可用包待。Next：`AI-04-A03-P03` 实现输入ResourceVersionRef显式Owner解析边界与Document Owner桥接，保持未注册类型失败关闭。
