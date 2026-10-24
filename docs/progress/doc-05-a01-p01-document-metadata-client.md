# DOC-05-A01-P01 Document 元数据只读客户端

- 日期：2026-09-29；Phase 2 Platform Core；状态：前端客户端 PASS，页面及真实浏览器/PG 验收待后续分项。
- 输入基线：Gate 2 冻结 API-02 `DOCUMENT_LIST`/`DOCUMENT_GET`；DOC-01-A02/A03-P01～P04 的授权读取、游标、HTTP 与 Windows 显式平台组合。仅前端 Document 模块，不改后端、权限、Schema、Migration 或依赖。
- 范围：固定 PROJECT/GLOBAL 两种路径，项目和文档 ID 规范化校验；同源 Session GET、50 条签名游标原样传递、10 秒超时和不缓存；响应只投影 Document 元数据，不透传正文、存储位置或服务端多余字段。详情校验 Document ID、Scope 与强 ETag 响应头；列表校验页形态、游标及本页去重。服务端继续独占授权裁决，客户端安全校验不替代服务端。
- 风险与处理：跨 Scope 错误响应、迟到结果或异常载荷不可当已授权数据。客户端发现范围/身份/ETag/响应不一致即失败关闭。页面后续分项必须在切项目/卸载时丢弃迟到结果；本项未实现或验证该页面行为。
- 验证：首轮定向测试因 UUID 正则缺组失败，修复后 46/46 通过；首轮全量测试 802/802，但类型检查发现 `scope` 仍为 unknown，修复为经校验的 Scope 后全量重跑：前端 802/802、typecheck、build PASS。未进行实际浏览器/PG 本项端到端验证；未覆盖正式信任锚、Server 2025/Debian 13、质量/性能 Gate。
- 回滚：撤 DocumentReadClient 及其测试即可，未对冻结 API/DB/现有页面做迁移；版本兼容当前 DB0049 与 `/api/v1`。
- 下一任务：DOC-05-A01-P02 将项目 Document 元数据历史列表接入受权项目 UI，再单列浏览器/PG 验收；GLOBAL UI 按明确授权入口另项。
