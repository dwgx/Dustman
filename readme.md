# Dustman（灰尘男人）

Dustman 是一个 Windows 清理与优化工具，基于 PyQt5 + Fluent 风格界面。目标是把常见的系统维护操作集中到一个面板里，减少手动点来点去。

## 主要功能

- 网络修复：DNS、网络栈、代理相关修复
- 垃圾清理：临时文件、缓存、回收站等
- 系统优化：内存/进程/电源策略等常见优化
- 文件工具：基础文件管理与常见操作
- 日志记录：每一步操作都有日志可查

## 使用前先看

- 部分操作需要管理员权限
- 本项目只面向 Windows（依赖 `netsh`、`ipconfig`、`powercfg` 等）
- 清理和优化前建议先备份重要数据

## 环境要求

- Python 3.8+
- 推荐 Python 3.12
- Windows 10/11

## 安装与运行

```bash
git clone https://github.com/dwgx/Dustman.git
cd Dustman
pip install -r requirements.txt
python main.py
```

## 依赖

`requirements.txt` 中当前主要依赖：

- PyQt5
- PyQt-Fluent-Widgets
- psutil

## 项目文件

- `main.py`：程序入口
- `config.json`：配置文件
- `readme.md`：说明文档

## 常见问题

### 启动后部分功能不可用

大概率是权限不足。请使用“以管理员身份运行”。

### 清理后发现某些数据不见了

请先确认是否误清理了缓存/临时目录。建议重要数据单独备份。

## 声明

本项目仅用于系统维护与学习交流，不保证适配所有 Windows 发行版本与第三方软件环境。
