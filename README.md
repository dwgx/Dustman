# Dustman

> Windows maintenance utility — junk cleanup, network repair, performance optimization, file management. One panel, all local.
>
> Windows 系统维护工具 — 垃圾清理、网络修复、性能优化、文件管理。一个面板搞定，纯本地运行。

## Overview / 概述

Dustman is a single-window desktop tool for Windows that puts common system maintenance tasks in one Fluent-style panel: junk-file cleanup, network/DNS repair, performance optimization, and basic file management. Everything runs locally. Destructive actions are gated behind confirmation dialogs so you review before anything gets deleted or changed.

Dustman 是一个 Windows 桌面维护工具，把常见系统维护操作集中到一个 Fluent 风格面板里：垃圾清理、网络/DNS 修复、性能优化和文件管理。全部本地运行，不依赖任何远程服务。删除和修改操作都需要先确认，方便操作前复查。

## Features / 功能

### Network Repair / 网络修复

- Fix common network issues (`ipconfig /release`, `/renew`, `netsh int ip reset all`)
- Reset PAC / system proxy, protocol repair, flush DNS cache, reset Winsock
- DNS management: view adapter/IPv4/DNS info, set primary/secondary DNS from presets (Google, Cloudflare, 114, Aliyun, Tencent), or reset to automatic
- DNS speed test with per-server latency and packet-loss results

### PC Cleanup / 电脑清理

- Scan junk files across TEMP/TMP, Windows Temp, LocalAppData Temp, Recent, INetCache, Chrome cache, Prefetch
- One-click deep clean
- Targeted actions: clear browser cache, empty recycle bin, clean Windows Update temp files, clean DirectX shader cache

### PC Optimization / 电脑优化

- Optimize RAM, clear background processes, CPU/thread optimization, optimize VRAM, all-in-one optimize
- Set "Ultimate Performance" power plan via `powercfg`
- Live CPU and memory gauges (psutil background monitor)

### File Management / 文件管理

- Tree view of filesystem with folder-size calculation
- Open in Explorer, delete, in-app text editor

### Settings / 设置

- Theme switching (Light / Dark / Auto)
- In-app and Windows notification toggles
- Configurable rename/delete shortcut keys

### Other / 其他

- Operation log panel (操作日志)
- About panel (程序信息), v1.0.0

## Tech Stack / 技术栈

- **Python** — primary language
- **PyQt5** 5.15.11 — GUI framework
- **PyQt-Fluent-Widgets** 1.11.2 — Fluent Design widget library
- **psutil** 7.2.2 — process and system metrics
- Windows system tools: `ipconfig`, `netsh`, `ping`, `powercfg`, `reg`

## Project Structure / 项目结构

```
Dustman/
├── main.py              # 整个应用（UI、worker线程、清理/修复/优化逻辑）
├── config.json          # 本地设置（主题、快捷键、通知开关）
├── requirements.txt     # Python 依赖
├── LICENSE              # MIT
└── .github/workflows/ci.yml  # CI: push/PR 时编译检查
```

## Getting Started / 快速开始

**Prerequisites / 环境要求**

- Windows 10/11
- Python 3.8+（推荐 3.12）

**Install & Run / 安装与运行**

```bash
git clone https://github.com/dwgx/Dustman.git
cd Dustman
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

部分操作（网络修复、深度清理、电源计划切换）需要管理员权限，以管理员身份运行终端或程序即可。

Some actions (network repair, deep clean, power plan changes) require administrator privileges — run your terminal as administrator for full functionality.

## Configuration / 配置

Settings are stored in `config.json` (auto-created on first run):

| Key | Values | Description |
|-----|--------|-------------|
| `theme` | `LIGHT`, `DARK`, `AUTO` | 界面主题 |
| `shortcuts` | key codes | rename/delete 快捷键 |
| `program_notifications_enabled` | bool | 程序内通知 |
| `windows_notifications_enabled` | bool | Windows 系统通知 |

## Status / 状态

v1.0.0, actively maintained. Single-file architecture, designed to keep growing.

v1.0.0，持续维护中。单文件架构，持续迭代。

## License / 许可证

MIT License. Copyright (c) 2025 dwgx. See [LICENSE](LICENSE).
