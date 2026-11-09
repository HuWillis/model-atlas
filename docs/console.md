# 本地控制台

这是能实际操作 Ollama 的本地应用。启动、模型加载与释放、测试回答都调用本机接口；页面显示当前状态。

## 打开

需要 Windows、Python 3.10 或更新版本，以及已经安装的 Ollama。本控制台使用 Python 标准库，没有额外 pip 或 npm 运行依赖。

1. 下载或克隆本仓库到电脑。
2. 双击仓库根目录的 **`Start-Console.cmd`**。
3. 浏览器自动打开 **http://127.0.0.1:18765**。
4. 点击 **启动 Ollama**，再从列表选择已安装模型。
5. 点击 **加载模型**，或直接输入问题，点击 **发送测试**。发送问题会按需加载模型。

也可以从 PowerShell 启动：

```powershell
.\scripts\Start-Console.ps1
```

启动控制台本身不加载模型，也不自动启动 Ollama。打开时看到“未启动”是正常状态。不要双击 `console/index.html`，它需要本机控制服务。

## 页面上的操作

| 操作 | 实际效果 |
| --- | --- |
| 启动 Ollama | 后台运行本机 `ollama serve`，只监听 `127.0.0.1:11434` |
| 选择模型 | 从 `/api/tags` 读取本机模型列表；不会下载模型或切换 CC Switch |
| 加载模型 | 请求 `/api/generate` 预加载所选模型，空闲 10 分钟后释放 |
| 释放模型内存 | 设置 `keep_alive: 0` 卸载模型；保留硬盘文件 |
| 发送测试 | 请求 `/api/chat`，逐步显示真实回答及耗时、token 数、生成速度 |
| 停止服务 | 停止本控制台启动的 Ollama 及其推理进程；可能中断其他客户端对该服务的请求 |
| 退出控制台 | 退出本地页面服务，并停止它启动的 Ollama；其他程序启动的 Ollama 保留 |

控制台一次执行一项操作。测试期间不能从这里卸载模型或停止服务。若服务由 Ollama 桌面应用等其他程序启动，停止按钮不可用，应从该程序退出。

关闭浏览器标签页不会停止控制台或 Ollama；需要停止时使用页面按钮。

测试为单轮对话，不保留前一轮上下文；最多输入 12000 字、输出 1024 token，每次请求最长约 10 分钟。默认 8K 上下文，可选 4K–64K，仅作用于本次加载或测试，不修改模型配置文件或 Claude Code 配置。CPU 推理与首次加载可能较慢。

## 看懂状态

- **服务在线**：本机 Ollama 接口可连接。
- **模型驻留内存**：`/api/ps` 报告的模型内存总量，包含模型显存分配；不是整个电脑的内存使用率。
- **模型使用显存**：`/api/ps` 的 `size_vram`。显示 0 表示模型没有使用显存，不代表电脑没有显卡。
- **NVIDIA 硬件监测**：如果系统存在 `nvidia-smi`，显示实际显存占用和 GPU 利用率；没有该工具时明确显示不可用。
- **任务进度**：仅反映通过本控制台发起的任务，无法判断其他 Claude Code 会话是否正在生成。

模型可能与别名共享同一份权重，释放某一别名可能同时释放同权重的驻留实例。请在其他客户端结束任务后再卸载或停止服务。

## 用于 Claude Code

先在 CC Switch 中选好本地供应商，再在目标项目终端运行控制台提供的 `claude --model ...` 命令。控制台的模型选择仅影响页面内测试；不会编辑 CC Switch 数据库、凭据或 Claude Code 设置。完整步骤见 [操作手册](operation-manual.md)。

## 自定义路径

Ollama 可执行文件按 PATH、`D:\Software\Ollama\ollama.exe`、Windows 默认用户安装目录查找。模型目录读取当前进程或 Windows 用户环境中的 `OLLAMA_MODELS`；未设置时采用 Ollama 默认路径。

```powershell
.\scripts\Start-Console.ps1 -OllamaPath 'E:\Apps\Ollama\ollama.exe' -ModelsDirectory 'E:\AI\Models' -Port 18765
```

参数仅在新启动控制台时生效，已运行时会复用现有服务。修改参数前先在页面退出控制台。

## 访问与数据

服务仅绑定本机回环地址，没有远程访问模式。手机或其他电脑不能通过此地址访问。公开 GitHub 仓库只公开代码，不会公开你的模型服务。

控制接口限制 Host、Origin 和会话令牌；不启用跨站访问，不接受任意 shell 命令，只能操作已安装模型。模型信息标记为云端模型时会拒绝加载和测试，不向它发送问题。页面仅加载仓库内静态资源。测试回答仅保留在进程内存中的最近 8 项操作，退出后清除，问题与回答不写入 Git 仓库。Ollama 自己的日志由它管理。

## 故障排查

| 情况 | 处理 |
| --- | --- |
| 双击窗口提示找不到 Python | 安装 Python 3.10+ 并确保 `python` 可运行，再重新打开 |
| 控制台无法打开 | 查看 `work/console/server.stderr.log`，检查 18765 是否被占用；可通过 `-Port` 更换 |
| 找不到 Ollama | 用 `-OllamaPath` 指定实际 `ollama.exe` 路径 |
| 服务启动失败 | 查看 `work/console/ollama.log`；检查安装文件、模型路径、11434 端口 |
| 列表为空 | 确认模型目录正确；先按部署指南安装模型 |
| 测试等待较久 | CPU 推理需要等待；先试短问题、小模型、4K 或 8K 上下文 |
| 会话失效 | 控制台重启后令牌会变化，刷新网页即可 |
| 停止服务按钮不可用 | 服务由其他程序启动，或控制台正在执行任务 |

## 验证

```powershell
python -m unittest discover -s tests -v
```

自动测试使用独立的 Ollama 模拟接口，验证请求转发、加载/卸载、回答拼接、并发操作限制、错误反馈和访问边界；不会下载或加载实际模型。真实模型验证另见 [控制台实测记录](console-validation-2026-11-09.md)。

接口依据：[Ollama 模型列表](https://docs.ollama.com/api/tags)、[已加载模型](https://docs.ollama.com/api/ps)、[加载与生成](https://docs.ollama.com/api/generate)、[对话生成](https://docs.ollama.com/api/chat)。
