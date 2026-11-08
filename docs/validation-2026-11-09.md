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

## 待验证

模型仍在下载。下载完成后记录模型摘要、推理设备、真实生成请求、Claude Code 文件编辑与代码测试结果。

## 安装包记录

- 来源：<https://github.com/ollama/ollama/releases/tag/v0.40.15>
- 文件：`OllamaSetup.exe`
- SHA256：`106ef3d2a02437810fba6f574914b1413c512ea84ddd4f184c8e7f434b6f5564`

原始日志保留在本机 `work/`，不提交到 Git。本文只记录与复现有关的信息。
