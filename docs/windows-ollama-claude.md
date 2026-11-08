# Windows：Ollama 本地编程

## 1. 安装 Ollama

本实践将软件和模型放在 D 盘：

```powershell
.\scripts\Install-Ollama.ps1 `
  -InstallDirectory 'D:\Software\Ollama' `
  -ModelsDirectory 'D:\AI\Models'
```

脚本下载 Ollama 官方 `0.40.15` Windows 安装程序，并在运行前校验 SHA256 和有效的 Ollama 发布者签名。已下载安装包时，可以传入 `-InstallerPath '路径\OllamaSetup.exe'`。

用户环境变量 `OLLAMA_MODELS` 决定模型目录。若安装前已有 Ollama 在运行，修改变量后需从系统托盘退出并重新启动 Ollama，使新进程读到新目录。重新打开终端后，才能可靠使用新加入 PATH 的 `ollama` 命令。

此脚本用于首次安装；迁移已有模型时，先确认旧目录与可用空间，再单独处理迁移。脚本不会搬动已有权重。

## 2. 下载并配置模型

确保 Ollama 已启动，执行：

```powershell
.\scripts\Initialize-Model.ps1
```

对应的核心命令是：

```powershell
& 'D:\Software\Ollama\ollama.exe' pull qwen3.5:4b
& 'D:\Software\Ollama\ollama.exe' create qwen3.5-coding:4b -f .\models\qwen3.5-4b\Modelfile
```

下载中断可以重新执行。Ollama 会复用已下载的数据。模型配置继承官方模型的模板与工具调用能力，另外设置 `num_ctx 65536` 和 `temperature 0.2`。同一份权重由基础模型和编程配置共用。

64K 是配置的上下文容量；实际内存占用和速度取决于硬件、输入长度及推理后端。Ollama 的 Claude Code 指南建议至少 64K 上下文。

## CC Switch 配置

在 CC Switch 中选择 **Claude Code → 添加供应商 → 本地 → Ollama**：

| 字段 | 值 |
| --- | --- |
| 名称 | `Ollama · Qwen3.5 4B 本地` |
| 请求地址 | `http://127.0.0.1:11434` |
| API Key | `ollama`，本机接口的占位值 |
| 上游格式 | `Anthropic Messages（原生）` |
| 认证字段 | `ANTHROPIC_AUTH_TOKEN` |
| 连接模式 | 直连 |
| 默认兜底模型 | `qwen3.5-coding:4b` |
| Sonnet / Opus / Haiku / Fable / Subagent 映射 | 全部为 `qwen3.5-coding:4b` |

先填写 Sonnet 的实际模型，再用“一键设置”复制其他档位；**默认兜底模型需要单独核对**。不要保留预设中的不带大小标签的 `qwen3.5`。

保存后选中该供应商。`configs/claude-ollama.json` 给出了对应的环境变量示例。通常由 CC Switch 管理 Claude Code 配置即可；切换后重新启动 Claude Code 会话。

这些档位都是同一个本地 Qwen 模型，名称来自 Claude Code 的角色菜单，并不代表在本地运行了 Anthropic 的模型。

## 3. 开始写代码

```powershell
Set-Location '你的项目目录'
claude --model qwen3.5-coding:4b
```

第一次使用项目时，按 Claude Code 提示确认可信目录与编辑权限。可以先交给它范围明确的小任务，例如：

> 阅读 strings.py，实现 normalize_names：去除首尾空格、删除空字符串、忽略大小写去重，保留首次出现的大小写和顺序。只修改这个文件。

若要直接和模型对话，可运行：

```powershell
& 'D:\Software\Ollama\ollama.exe' run qwen3.5-coding:4b
```

直接对话不会自动获得 Claude Code 的文件编辑工具。

## 4. 验证和排查

```powershell
.\scripts\Test-Ollama.ps1
.\scripts\Test-ClaudeCode.ps1
```

第一个脚本检查本机服务、模型配置，并发送真实生成请求。第二个脚本在 `work/` 下创建独立的小任务，让 Claude Code 使用文件工具修改代码。测试产物中包含模型响应和待检查的代码；先检查代码，再运行生成目录中的 `test_strings.py`。

常见情况：

- **连接被拒绝**：先确认托盘中的 Ollama 正在运行，再检查 `http://127.0.0.1:11434/api/version`。
- **model not found**：执行初始化脚本，确认 `ollama list` 包含 `qwen3.5-coding:4b`。
- **仍连接远端供应商**：检查 CC Switch 当前选择；重开 Claude Code，并检查终端是否残留 `ANTHROPIC_BASE_URL` 等环境变量覆盖。
- **第一次回答慢**：首次需要加载模型，Claude Code 还会发送工具说明和系统提示。结合 `ollama ps` 查看真实处理器分配；不要仅依据显卡名称判断是否已启用加速。
- **工具调用不稳定**：缩小任务，减少一次处理的文件，检查改动并运行项目测试。4B 模型的实际能力需按任务验证。

## 版本和更新

安装脚本固定 Ollama 安装包版本与摘要。升级时一并更新版本号、官方 SHA256，并重新验证签名与本地链路。模型标签可能随上游更新，重新 `pull` 之前可先记录 `ollama list` / `/api/tags` 返回的摘要。

参考：[Windows 安装与环境变量](https://docs.ollama.com/windows)、[Claude Code 接入](https://docs.ollama.com/integrations/claude-code)、[CC Switch 项目](https://github.com/farion1231/cc-switch)。
