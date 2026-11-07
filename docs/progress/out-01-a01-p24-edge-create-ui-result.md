# OUT-01-A01-P24 结果：DOCX 请求 UI 的 hosted Edge 集成验收

- 日期：2026-11-05
- 结果：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-020
- GitHub Actions：[run 41888874127](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41888874127)
- 执行环境：GitHub hosted Windows Server 2025，D: runner temp，Microsoft Edge headless；同run前端production build

## 验收结果

Run 41888874127 完成，14/14 jobs成功。全链包括前端、后端、PG18/pgvector、父包及A17/A34/A35/A50。

- 前端204/204测试文件、2,093/2,093测试、typecheck和production build通过。
- 后端4,022项测试及wheel构建通过。
- 浏览器打开实际production build中的需求固定版本详情；批准版本显示Output请求入口。
- 对受控API观察到精确固定的template/policy/operation/source version请求字段，CSRF头与单个Idempotency-Key存在；202受理后显示回执并能进入请求历史。
- 受控503服务拒绝显示安全错误提示；在500ms观察窗内没有自动发出第二次POST。
- 未批准版本没有Output请求操作入口。
- Edge专项仅发生两次合成POST：一次202受理、一次明确模拟的503。

## 隐私与范围

使用完全合成的Session、项目、需求版本和浏览器拦截/受控API。客户数据=false，外部API调用=0，插件执行=false，DOCX生成=false。GitHub hosted runner临时工作区位于D盘；用户本机与C盘未执行项目程序或测试。

PASS_SCOPE_LIMITED只代表P24验收的浏览器UI/API合同与页面状态。它不证明生产Publisher信任、真实DOCX生成/下载、Windows 11设备兼容、Gate 3、Pilot或正式Release。生产Create服务在正式Publisher信任缺失时仍按P19验证保持失败关闭。

## 变更与已知限制

按CR-OUT-020，修复了真实UI缺陷：SessionClient写请求期间暂时不可提交，旧组件门控导致整个操作区卸载、异步202回执被丢弃。现将区域渲染条件和提交资格拆开，忙态保留操作区并禁用按钮，收到响应后显示回执/错误。

P24多轮偏差包括：合成ETag/Requirement fixture不符、测试helper/trace引用错误、过严的503按钮断言、未批准场景等待不存在元素，以及上述真实组件缺陷。每项都先记入CR-OUT-020再修正，并由run 41888874127全链重验。

## 后续

P25编码前检查将评估把真实Windows Output Create HTTP组合、隔离PG18 synthetic数据与hosted Edge衔接，验证后端真实失败关闭在浏览器上的表现及无持久化副作用。真实Publisher未提供前，不创建OutputRequest、不生成文件、不执行插件。