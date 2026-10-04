# RAG-03-A04-P04 Embedding 统一发送边界

日期：2026-10-04；状态：`RAG_EMBEDDING_SEND_BOUNDARY_PASS`。

已实现当前路由事实仓储、Embedding pre-send/send-once、Scope感知Secret审计及RAG Batch fence桥接。固定执行顺序为“当前授权→精确Secret版本→再次授权→事实稳定→提交fence→单次Adapter”；两次授权分别执行事务内外License检查。fence后异常按Provider结果未知处理，不自动重放。

内部Envelope增加Index ID、batch ordinal和source first ordinal以生成精确RAG proof；这些身份不进入厂商请求正文。Windows11/PostgreSQL18.6真实事务验证得到`RAG_03_A04_P04_EMBEDDING_SEND_BOUNDARY_PASS`：活动Secret版本、PROJECT Audit、PENDING→RUNNING、一次合成Adapter、响应所有权与明文归零均通过，零真实Provider I/O。

验证：相关wheel隔离21项通过；后端全量2408项通过、3项既有条件跳过；wheel SHA-256 `16e3e4f1273606488b1913ea2b1bdca530c7c934df055e5a5c41a77a4bd639da`。首轮真实验证试图在Build启动后改写payload，被不可变守卫正确拒绝；改为计划前构造精确payload后使用全新临时库重跑通过，失败库均自动清理。

兼容与回滚：无Schema、公开API或新依赖；可回退新增编排使发送入口关闭。已有RUNNING Batch不得回退PENDING，继续由Schema0081/0082对账为UNKNOWN。下一项`RAG-03-A04-P05`实现成功/失败响应提交、EmbeddingRecord原子写入及未知结果保持不可重放；READY/ACTIVE、性能、Server2025/Debian13、Gate3/UAT与正式发行包仍未完成。
