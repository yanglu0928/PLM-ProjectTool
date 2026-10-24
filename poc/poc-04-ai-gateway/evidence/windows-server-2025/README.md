# POC-04 Windows Server 2025 验证证据

## Environment

- Microsoft Windows Server 2025 Datacenter 10.0.26100，x86-64。
- 16 个逻辑处理器，16 GB 内存。
- Python 3.13.15。
- httpx 0.28.1，jsonschema 4.26.0。
- DeepSeek 真实调用需要在线网络；验证时 1 个物理网卡处于连接状态。

## Result

- 单元测试：11/11 PASS。
- 确定性协议与异常场景：11/11 PASS。
- 真实无效密钥：HTTP 401 正确映射为 `AI_AUTH_FAILED`，PASS。
- 真实文本、SSE 流式、结构化 JSON：3/3 PASS。

## Metrics

|指标|结果|
|---|---|
|真实 401 连通性|PASS，0.474 秒|
|真实文本|PASS，1.055 秒|
|真实 SSE 流式|PASS，0.804 秒|
|真实结构化 JSON|PASS，0.918 秒|
|验证包 SHA-256|`6b4339951d72a615d56079013c2507785cc801a7e5affaa2530f6d53137ee1bf`|
|原始证据归档 SHA-256|`f64b761fd5422612a2eba0b286c331f4135d74b1d3241c868bab3cf9964ea74c`|

## Security and Privacy

- 真实密钥仅通过来宾机临时文件传入，执行完成后已删除。
- 证据不记录 Secret 值，也不记录模型响应正文。
- 使用真实密钥扫描 6 个证据文件，匹配数为 0。
- 宿主机本地密钥文件、来宾机临时密钥和原始运行目录均不纳入 Git。

## Evidence Files

- `environment.json`：Python、依赖和平台采集。
- `unit-test-result.json`：单元测试结果。
- `validation-result.json`：11 个确定性场景结果。
- `live-invalid-key-result.json`：真实端点 401 映射结果。
- `live-validation-result.json`：真实文本、流式和结构化结果；不含响应正文。
- `overall-result.json`：平台、网络、验证包 Hash 和总判定。

## Known Issue

预检先后发现固定依赖清单漏项与相对输出目录清单路径错误；补齐 `typing_extensions` 并规范化输出绝对路径后重新制包，最终使用上述 SHA-256 对应归档完成验证。这些制包问题未进入最终 PASS 运行。
