# 2026-11-09 本机实践记录

## 环境

- Windows，AMD Ryzen 7 H 255，32 GB 内存，Radeon 780M 集成显卡。
- Ollama `0.40.15`，安装于 `D:\Software\Ollama`。
- CC Switch `4.0.27`，Claude Code `2.1.319`。
- 模型目录：`D:\AI\Models`。
- 模型：`qwen3.5:4b`；目标编程配置：`qwen3.5-coding:4b`，64K 上下文。

## 已验证

- 官方安装包 SHA256 与发布者签名校验通过，安装日志显示成功。
- 本机 `/api/version` 返回 `0.40.15`。
- CC Switch 已添加 Ollama 本地供应商并选中直连；默认模型及全部角色映射均为 `qwen3.5-coding:4b`。
- Claude Code 用户配置的请求地址为 `http://127.0.0.1:11434`。

## 模型与运行状态

| 项目 | 实测值 |
| --- | --- |
| 基础模型摘要 | `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` |
| 编程配置摘要 | `b572cfef927a4ff6e1d967c37033e96614c58146811aedac7b755241be639c96` |
| 参数 / 量化 | 4.2B / Q4_K_M |
| 基础模型文件总大小 | 3,324,173,934 字节，约 3.32 GB |
| 实际推理后端 | `llamacpp`，`100% CPU` |
| 已加载上下文 | 65,536 tokens |
| Ollama 报告的加载大小 | 约 5.7 GB；此值并非整个系统的总内存占用 |
| `size_vram` | 0，本次未使用集成显卡加速 |

基础模型与编程配置共用权重，不需要为两个名称各存一份大文件。

## 真实请求与文件编辑测试

1. `Test-Ollama.ps1`：本机 `/api/chat` 返回 `READY`，请求总耗时约 5.15 秒，包含首次加载。该请求只生成了两个 token，不将其用作吞吐性能基准。
2. `Test-ClaudeCode.ps1`：从 CC Switch 写入的用户配置读取本机端点，使用 `qwen3.5-coding:4b`，仅开放 `Read` 和 `Edit` 工具。
3. Claude Code 实际调用了 `Read`、`Edit`，修改独立测试目录中的 `strings.py`；最终返回成功，3 轮交互耗时 **95.015 秒**。
4. 检查生成代码后运行 `python test_strings.py -v`，**6 项测试全部通过**：空输入、空白处理、大小写去重、顺序保持、Unicode casefold、原输入不变。
5. Ollama 服务日志记录了来自本机的 `/v1/messages?beta=true` 请求，均返回 HTTP 200，确认 Claude Code 请求经过本地 Anthropic 兼容接口。

测试任务是实现一个字符串列表规范化函数。结果证明本机的模型推理、协议适配和文件工具链路可用；尚未测试大型仓库、多文件重构或长时间复杂任务。

Claude Code 对自定义模型名输出了 `unrecognized_model` 提示，但这次请求、工具调用和结果均成功。该提示本身不能作为连接失败的判断依据。

## 下载过程

原生 `ollama pull` 速度较慢。本次补充分段下载了官方 registry 中同一 manifest 指向的模型文件，分别验证完整 SHA256 后，通过本机 `/api/blobs/:digest` 导入，再使用原生 `ollama pull` 和 `ollama create` 完成初始化。

文件来源和校验值记录在 [source.json](../models/qwen3.5-4b/source.json)。普通复现仍可直接运行 `Initialize-Model.ps1`；分段下载不改变模型来源或配置，也不需要修改 Ollama 服务的代理设置。接口参考：[Ollama v0.40.15 API — Push a Blob](https://github.com/ollama/ollama/blob/v0.40.15/docs/api.md#push-a-blob)。

## 安装包记录

- 来源：<https://github.com/ollama/ollama/releases/tag/v0.40.15>
- 文件：`OllamaSetup.exe`
- SHA256：`106ef3d2a02437810fba6f574914b1413c512ea84ddd4f184c8e7f434b6f5564`

原始日志保留在本机 `work/`，不提交到 Git。本文只记录与复现有关的信息。
