# Model Atlas · 模型地图

记录模型从安装到实际使用的完整过程，积累可独立运行的脚本、配置和验证记录。

首个实践：在 Windows 上使用 **Ollama + Qwen3.5 4B + CC Switch + Claude Code** 本地编程。

```text
Claude Code：读文件、修改代码
    │ 读取 CC Switch 写入的供应商配置
    ▼
Ollama：http://127.0.0.1:11434
    ▼
qwen3.5-coding:4b：本地模型推理
```

这里使用 Claude Code 作为编程工具，实际回答由本机 Qwen 模型生成。CC Switch 负责切换配置；在直连模式下，请求直接进入 Ollama。

## 当前实践

| 项目 | 配置 |
| --- | --- |
| 基础模型 | `qwen3.5:4b` |
| 编程配置名 | `qwen3.5-coding:4b` |
| 上下文 / 温度 | `65536` / `0.2` |
| Ollama 安装目录 | `D:\Software\Ollama` |
| 模型存放目录 | `D:\AI\Models` |
| 接入方式 | 本机 Anthropic Messages 兼容接口 |

安装过程与日常使用见 [Windows 部署指南](docs/windows-ollama-claude.md)，本机验证状态见 [实践记录](docs/validation-2026-11-09.md)。

**2026-11-09 实测通过**：Claude Code 经本机 Ollama 调用 `Read`、`Edit` 修改 Python 文件，6 项功能测试全部通过。Ryzen 7 H 255 / 32 GB 环境下使用 CPU 推理，该小任务耗时约 95 秒。

## 从安装到使用

在 PowerShell 中，从仓库根目录执行：

```powershell
# 安装固定版本的官方 Ollama，验证 SHA256 与发布者签名
.\scripts\Install-Ollama.ps1

# 确认 Ollama 已在托盘运行，再下载模型、创建编程配置
.\scripts\Initialize-Model.ps1

# 检查本地服务、模型能力，并实际请求一次文本生成
.\scripts\Test-Ollama.ps1
```

随后按 [CC Switch 配置步骤](docs/windows-ollama-claude.md#cc-switch-配置) 添加本地供应商。在项目目录打开新终端，运行：

```powershell
claude --model qwen3.5-coding:4b
```

仓库中的脚本以 Windows PowerShell 5.1 / PowerShell 7 为目标，默认使用 D 盘；安装路径和模型路径可以通过参数调整。Claude Code 和 CC Switch 需先安装。

## 内容约定

- `scripts/`：安装、初始化与检查脚本。
- `models/`：模型配置文件，不存放模型权重。
- `configs/`：可复用的配置示例，不包含真实凭据。
- `docs/`：部署步骤、问题与验证结果。
- `examples/`：小型编程验证任务。
- `work/`：安装日志、下载和测试产物，已排除 Git 跟踪。

后续新增模型时，记录来源、版本或摘要、硬件需求、启动方法、实测任务及限制。小任务通过只代表基础链路可用，不能据此认定模型能可靠完成大型项目。

## 官方资料

- [Ollama Windows 安装](https://docs.ollama.com/windows)
- [Ollama 接入 Claude Code](https://docs.ollama.com/integrations/claude-code)
- [Qwen3.5 4B 模型页](https://ollama.com/library/qwen3.5:4b)
- [CC Switch](https://github.com/farion1231/cc-switch)
