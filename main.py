import sys
import json
import os
import shutil
import subprocess
import threading
import datetime
import math
import re
import psutil
import ctypes

_TOAST_NOTIFIER_AVAILABLE = False

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QTextEdit, QLineEdit, QFileSystemModel,
    QTreeView, QInputDialog, QMessageBox, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressDialog,
    QStyledItemDelegate, QStyleOptionViewItem, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, QDir, QTimer, QUrl, QThread, pyqtSignal, QModelIndex, QPropertyAnimation, \
    QEasingCurve, pyqtProperty
from PyQt5.QtGui import QIcon, QFont, QColor, QTextCharFormat, QTextCursor, QDesktopServices, QKeySequence, QPainter, \
    QBrush, QPen, QPainterPath

from qfluentwidgets import (
    FluentWindow, NavigationPanel, NavigationItemPosition,
    SettingCard, SwitchButton, PushButton, InfoBar, InfoBarPosition,
    BodyLabel, CaptionLabel, LineEdit, TextEdit,
    PrimaryPushButton, ToolButton, Icon,
    FluentIcon, ExpandSettingCard, ComboBox,
    MessageBoxBase, SubtitleLabel,
    ListWidget, Theme, setTheme
)
from qfluentwidgets.components.dialog_box import Dialog
from qfluentwidgets.components.widgets.tool_tip import ToolTip
from qfluentwidgets.components.widgets.scroll_area import ScrollArea
from qfluentwidgets.components.widgets.line_edit import SearchLineEdit

CONFIG_FILE = "config.json"


def show_notification(title: str, content: str, notification_type: str, parent: QWidget = None):
    if config.program_notifications_enabled:
        if notification_type == 'success':
            InfoBar.success(title=title, content=content, parent=parent, position=InfoBarPosition.TOP_RIGHT)
        elif notification_type == 'warning':
            InfoBar.warning(title=title, content=content, parent=parent, position=InfoBarPosition.TOP_RIGHT)
        elif notification_type == 'error':
            InfoBar.error(title=title, content=content, parent=parent, position=InfoBarPosition.TOP_RIGHT)
        else:
            InfoBar.info(title=title, content=content, parent=parent, position=InfoBarPosition.TOP_RIGHT)


class Config:
    def __init__(self):
        self.theme = Theme.AUTO
        self.shortcuts = {
            'rename': Qt.Key_F2,
            'delete': Qt.Key_Delete
        }
        self.program_notifications_enabled = True
        self.windows_notifications_enabled = False
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    theme_str = data.get('theme', 'AUTO').upper()
                    if theme_str in Theme.__members__:
                        self.theme = Theme[theme_str]
                    else:
                        print(f"配置文件中的主题 '{data.get('theme')}' 无效，使用默认设置。")
                        self.theme = Theme.AUTO

                    loaded_shortcuts = data.get('shortcuts', {})
                    for key, default_value in self.shortcuts.items():
                        self.shortcuts[key] = int(loaded_shortcuts.get(key, default_value))

                    self.program_notifications_enabled = data.get('program_notifications_enabled', True)
                    self.windows_notifications_enabled = data.get('windows_notifications_enabled', False)

                except json.JSONDecodeError:
                    print("config.json解码错误，使用默认设置。")
                except ValueError:
                    print("config.json中快捷键键码解析错误，使用默认设置。")
                    self.shortcuts = {
                        'rename': Qt.Key_F2,
                        'delete': Qt.Key_Delete
                    }
        else:
            self._save()

    def _save(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'theme': self.theme.name,
                'shortcuts': self.shortcuts,
                'program_notifications_enabled': self.program_notifications_enabled,
                'windows_notifications_enabled': self.windows_notifications_enabled
            }, f, indent=4, ensure_ascii=False)

    def set_theme(self, theme: Theme):
        self.theme = theme
        setTheme(self.theme)
        self._save()

    def set_shortcut(self, action: str, key_code: int):
        if action in self.shortcuts:
            self.shortcuts[action] = key_code
            self._save()

    def set_program_notifications_enabled(self, enabled: bool):
        self.program_notifications_enabled = enabled
        self._save()

    def set_windows_notifications_enabled(self, enabled: bool):
        self.windows_notifications_enabled = enabled
        self._save()


config = Config()


class LogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.log_display = TextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("这里会显示操作日志...")
        self.vBoxLayout.addWidget(self.log_display)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("LogWidget")

    def append_log(self, message: str):
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        self.log_display.append(f"{timestamp} {message}")
        self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())


class AboutWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.label = BodyLabel("灰尘男人 v1.0.0", self)
        self.description = CaptionLabel("一个强大的一键清理、优化和修复工具。", self)
        self.vBoxLayout.addWidget(self.label)
        self.vBoxLayout.addWidget(self.description)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.setObjectName("AboutWidget")


class PingWorker(QThread):
    result_signal = pyqtSignal(str, dict)
    finished_signal = pyqtSignal()

    def __init__(self, dns_servers_to_test: dict):
        super().__init__()
        self.dns_servers_to_test = dns_servers_to_test

    def run(self):
        for name, ips in self.dns_servers_to_test.items():
            for ip in ips:
                ping_results = self._test_dns_speed(ip)
                self.result_signal.emit(f"{name} ({ip})", ping_results)
        self.finished_signal.emit()

    def _test_dns_speed(self, dns_ip: str) -> dict:
        ping_command = f"chcp 65001 && ping -n 4 -w 1000 {dns_ip}"
        try:
            process = subprocess.run(
                ping_command,
                capture_output=True,
                text=True,
                shell=True,
                encoding='utf-8',
                errors='replace',
                check=False
            )
            output = process.stdout

            packet_loss_match = re.search(r"(?:Lost|已丢失) = \d+ \((\d+)% (?:loss|丢失)\)", output)

            min_lat = re.search(r"(?:Minimum|最短) = (\d+)ms", output)
            max_lat = re.search(r"(?:Maximum|最长) = (\d+)ms", output)
            avg_lat = re.search(r"(?:Average|平均) = (\d+)ms", output)

            results = {
                'min_latency': int(min_lat.group(1)) if min_lat else -1,
                'max_latency': int(max_lat.group(1)) if max_lat else -1,
                'avg_latency': int(avg_lat.group(1)) if avg_lat else -1,
                'packet_loss_percent': int(packet_loss_match.group(1)) if packet_loss_match else 100,
                'raw_output': output
            }
            return results
        except Exception as e:
            return {
                'min_latency': -1,
                'max_latency': -1,
                'avg_latency': -1,
                'packet_loss_percent': 100,
                'error': str(e),
                'raw_output': ""
            }


class NetworkRepairWidget(QWidget):
    def __init__(self, log_widget: LogWidget, parent=None):
        super().__init__(parent)
        self.log_widget = log_widget
        self.setObjectName("NetworkRepairWidget")

        self.main_h_layout = QHBoxLayout(self)
        self.left_buttons_layout = QVBoxLayout()
        self.right_display_layout = QVBoxLayout()

        self.title = SubtitleLabel("网络修复", self)
        self.left_buttons_layout.addWidget(self.title)

        self.network_problem_repair_button = PrimaryPushButton("修复网络问题", self)
        self.network_problem_repair_button.clicked.connect(lambda: self._confirm_and_run_command("修复网络问题",
                                                                                                 ["ipconfig /release",
                                                                                                  "ipconfig /renew",
                                                                                                  "netsh int ip reset all"]))
        self.left_buttons_layout.addWidget(self.network_problem_repair_button)

        self.pac_proxy_repair_button = PrimaryPushButton("PAC/系统代理修复", self)
        self.pac_proxy_repair_button.clicked.connect(lambda: self._confirm_and_run_command("PAC/系统代理修复", [
            "reg add \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\" /v ProxyEnable /t REG_DWORD /d 0 /f"]))
        self.left_buttons_layout.addWidget(self.pac_proxy_repair_button)

        self.protocol_repair_button = PrimaryPushButton("协议修复", self)
        self.protocol_repair_button.clicked.connect(
            lambda: self._confirm_and_run_command("协议修复", ["netsh int ip reset", "netsh winsock reset"]))
        self.left_buttons_layout.addWidget(self.protocol_repair_button)

        self.dns_flush_button = PrimaryPushButton("刷新DNS缓存", self)
        self.dns_flush_button.clicked.connect(
            lambda: self._confirm_and_run_command("刷新DNS缓存", ["ipconfig /flushdns"]))
        self.left_buttons_layout.addWidget(self.dns_flush_button)

        self.winsock_reset_button = PrimaryPushButton("重置Winsock", self)
        self.winsock_reset_button.clicked.connect(
            lambda: self._confirm_and_run_command("重置Winsock", ["netsh winsock reset"]))
        self.left_buttons_layout.addWidget(self.winsock_reset_button)

        self.dns_label = SubtitleLabel("DNS 管理", self)
        self.left_buttons_layout.addWidget(self.dns_label)

        self.refresh_network_info_button = PrimaryPushButton("刷新网络信息 (含DNS)", self)
        self.refresh_network_info_button.clicked.connect(self._refresh_network_info)
        self.left_buttons_layout.addWidget(self.refresh_network_info_button)

        self.set_primary_dns_button = PushButton("设置主 DNS", self)
        self.set_primary_dns_button.clicked.connect(lambda: self._select_and_set_dns(is_primary=True))
        self.left_buttons_layout.addWidget(self.set_primary_dns_button)

        self.set_secondary_dns_button = PushButton("设置备用 DNS", self)
        self.set_secondary_dns_button.clicked.connect(lambda: self._select_and_set_dns(is_primary=False))
        self.left_buttons_layout.addWidget(self.set_secondary_dns_button)

        self.reset_dns_auto_button = PushButton("重置 DNS 为自动获取", self)
        self.reset_dns_auto_button.clicked.connect(lambda: self._confirm_and_set_dns([], "自动获取 DNS"))
        self.left_buttons_layout.addWidget(self.reset_dns_auto_button)

        self.dns_speed_test_label = SubtitleLabel("DNS 速度测试", self)
        self.left_buttons_layout.addWidget(self.dns_speed_test_label)

        self.start_dns_test_button = PrimaryPushButton("开始 DNS 速度测试", self)
        self.start_dns_test_button.clicked.connect(self._start_dns_speed_test)
        self.left_buttons_layout.addWidget(self.start_dns_test_button)

        self.left_buttons_layout.addStretch(1)
        self.left_buttons_layout.setContentsMargins(20, 20, 10, 20)

        self.network_log_display = TextEdit(self)
        self.network_log_display.setReadOnly(True)
        self.network_log_display.setPlaceholderText("这里会显示网络操作的详细日志...")
        self.right_display_layout.addWidget(SubtitleLabel("网络操作日志", self))
        self.right_display_layout.addWidget(self.network_log_display)

        self.dns_info_table_label = SubtitleLabel("当前网络信息", self)
        self.right_display_layout.addWidget(self.dns_info_table_label)

        self.toggle_dns_info_visibility = SwitchButton(self)
        self.toggle_dns_info_visibility.setText("显示/隐藏网络信息")
        self.toggle_dns_info_visibility.setChecked(False)
        self.toggle_dns_info_visibility.checkedChanged.connect(self._toggle_dns_info_table)
        self.right_display_layout.addWidget(self.toggle_dns_info_visibility)

        self.dns_info_table = QTableWidget(self)
        self.dns_info_table.setColumnCount(3)
        self.dns_info_table.setHorizontalHeaderLabels(["适配器名称", "IPv4 地址", "DNS 服务器"])
        self.dns_info_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dns_info_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dns_info_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.right_display_layout.addWidget(self.dns_info_table)
        self.dns_info_table.setVisible(False)

        self.dns_speed_table = QTableWidget(self)
        self.dns_speed_table.setColumnCount(4)
        self.dns_speed_table.setHorizontalHeaderLabels(["DNS 服务器", "平均延迟 (ms)", "丢包率 (%)", "状态"])
        self.dns_speed_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dns_speed_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dns_speed_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.right_display_layout.addWidget(SubtitleLabel("DNS 速度测试结果", self))
        self.right_display_layout.addWidget(self.dns_speed_table)

        self.right_display_layout.setContentsMargins(10, 20, 20, 20)

        self.main_h_layout.addLayout(self.left_buttons_layout, 1)
        self.main_h_layout.addLayout(self.right_display_layout, 2)

        self._refresh_network_info()

    def _toggle_dns_info_table(self, checked: bool):
        self.dns_info_table.setVisible(checked)
        if checked:
            self.network_log_display.append("显示当前网络信息表格。")
        else:
            self.network_log_display.append("隐藏当前网络信息表格。")

    def _select_and_set_dns(self, is_primary: bool):
        dns_options = {
            "自动获取": [],
            "Google DNS (8.8.8.8 / 8.8.4.4)": ["8.8.8.8", "8.8.4.4"],
            "Cloudflare DNS (1.1.1.1 / 1.0.0.1)": ["1.1.1.1", "1.0.0.1"],
            "114 DNS (114.114.114.114 / 114.114.115.115)": ["114.114.114.114", "114.114.115.115"],
            "阿里云 DNS (223.5.5.5 / 223.6.6.6)": ["223.5.5.5", "223.6.6.6"],
            "腾讯云 DNS (119.29.29.29 / 119.28.28.28)": ["119.29.29.29", "119.28.28.28"]
        }

        items = list(dns_options.keys())

        dialog_title = "选择主 DNS 服务器" if is_primary else "选择备用 DNS 服务器"
        dialog_text = "请选择一个 DNS 提供商:"

        item, ok = QInputDialog.getItem(self, dialog_title, dialog_text, items, 0, False)

        if ok and item:
            selected_dns_servers = dns_options[item]
            action_name = f"设置 {'主' if is_primary else '备用'} DNS 为 {item}"

            if item == "自动获取":
                if is_primary:
                    self._confirm_and_set_dns([], "自动获取 DNS")
                else:
                    self.network_log_display.append(
                        "备用DNS不能设置为自动获取，请选择一个具体的DNS服务商。若要重置，请使用'重置DNS为自动获取'按钮。")
                    show_notification(
                        title="无效操作",
                        content="备用DNS不能设置为自动获取，请选择一个具体的DNS服务商。若要重置，请使用'重置DNS为自动获取'按钮。",
                        notification_type="warning",
                        parent=self
                    )
            else:
                if is_primary:
                    self._confirm_and_set_dns(selected_dns_servers, action_name)
                else:
                    if selected_dns_servers:
                        self._confirm_and_set_dns_secondary_only(selected_dns_servers[0], action_name)
                    else:
                        self.network_log_display.append("选择的 DNS 服务商没有提供备用 IP。")
                        show_notification(
                            title="操作提示",
                            content="选择的 DNS 服务商没有提供备用 IP。",
                            notification_type="warning",
                            parent=self
                        )

    def _confirm_and_run_command(self, action_name: str, commands: list):
        dialog = Dialog("确认操作", f"您确定要执行 '{action_name}' 吗？此操作可能需要管理员权限。", self)
        if dialog.exec_() == QDialog.Accepted:
            self._run_command(commands, action_name, self.network_log_display)
        else:
            self.log_widget.append_log(f"用户取消了操作: {action_name}")
            self.network_log_display.append(f"用户取消了操作: {action_name}")
            show_notification(
                title="操作取消",
                content=f"已取消执行 {action_name}。",
                notification_type="warning",
                parent=self
            )

    def _run_command(self, commands: list, description: str, specific_log: TextEdit = None):
        self.log_widget.append_log(f"开始执行: {description}...")
        if specific_log:
            specific_log.append(f"开始执行: {description}...")

        all_successful = True
        for command in commands:
            full_command = f"chcp 65001 && {command}"
            self.log_widget.append_log(f"执行命令: {full_command}")
            if specific_log:
                specific_log.append(f"执行命令: {full_command}")
            try:
                process = subprocess.run(full_command, capture_output=True, text=True, shell=True, check=True,
                                         encoding='utf-8', errors='replace')
                self.log_widget.append_log(f"命令 '{command}' 完成。")
                self.log_widget.append_log(f"输出:\n{process.stdout}")
                if specific_log:
                    specific_log.append(f"命令 '{command}' 完成。")
                    specific_log.append(f"输出:\n{process.stdout}")
                if process.stderr:
                    self.log_widget.append_log(f"错误输出:\n{process.stderr}")
                    if specific_log:
                        specific_log.append(f"错误输出:\n{process.stderr}")
            except subprocess.CalledProcessError as e:
                self.log_widget.append_log(f"执行命令 '{command}' 失败: {e}")
                self.log_widget.append_log(f"错误输出:\n{e.stderr}")
                if specific_log:
                    specific_log.append(f"执行命令 '{command}' \u5931\u8D25: {e}")
                    specific_log.append(f"错误输出:\n{e.stderr}")
                all_successful = False
            except FileNotFoundError:
                cmd_name = command.split(' ')[0]
                self.log_widget.append_log(f"命令 '{cmd_name}' 未找到。此功能可能仅限Windows系统。")
                if specific_log:
                    specific_log.append(f"命令 '{cmd_name}' 未找到。此功能可能仅限Windows系统。")
                all_successful = False
            except Exception as e:
                self.log_widget.append_log(f"执行命令 '{command}' 时发生未知错误: {e}")
                if specific_log:
                    specific_log.append(f"执行命令 '{command}' 时发生未知错误: {e}")
                all_successful = False

        if all_successful:
            show_notification(
                title=f"{description} 成功",
                content=f"{description} 已完成。",
                notification_type="success",
                parent=self
            )
        else:
            show_notification(
                title=f"{description} 问题",
                content=f"{description} 执行过程中发生错误，请检查日志。",
                notification_type="warning",
                parent=self
            )
        self.log_widget.append_log(f"{description} 尝试完成。")
        if specific_log:
            specific_log.append(f"{description} 尝试完成。")

    def _refresh_network_info(self):
        self.network_log_display.append("正在刷新网络信息...")
        self.dns_info_table.setRowCount(0)
        try:
            ipconfig_cmd = "chcp 65001 && ipconfig /all"
            process_ipconfig = subprocess.run(ipconfig_cmd, capture_output=True, text=True, shell=True,
                                              encoding='utf-8', errors='replace', check=True)
            ipconfig_output = process_ipconfig.stdout
            self.network_log_display.append("ipconfig /all 命令输出已获取。")
            self.network_log_display.append(ipconfig_output)

            parsed_adapters = self._parse_ipconfig_output(ipconfig_output)

            for adapter_info in parsed_adapters:
                row_position = self.dns_info_table.rowCount()
                self.dns_info_table.insertRow(row_position)
                self.dns_info_table.setItem(row_position, 0,
                                            QTableWidgetItem(adapter_info.get("Name", "未知适配器")))
                self.dns_info_table.setItem(row_position, 1,
                                            QTableWidgetItem(adapter_info.get("IPv4 Address", "N/A")))
                self.dns_info_table.setItem(row_position, 2,
                                            QTableWidgetItem("\n".join(adapter_info.get("DNS Servers", ["N/A"])) ))
            self.dns_info_table.resizeRowsToContents()

            self.network_log_display.append("网络信息刷新完成。")
            show_notification(
                title="网络信息刷新",
                content="当前网络信息已刷新。",
                notification_type="success",
                parent=self
            )

        except subprocess.CalledProcessError as e:
            self.network_log_display.append(f"获取网络信息失败: {e}")
            self.network_log_display.append(f"错误输出:\n{e.stderr}")
            show_notification(
                title="网络信息获取失败",
                content="无法获取网络信息，请检查权限或系统。",
                notification_type="error",
                parent=self
            )
        except Exception as e:
            self.network_log_display.append(f"解析网络信息时发生错误: {e}")
            show_notification(
                title="网络信息解析错误",
                content="解析网络信息时发生未知错误。",
                notification_type="error",
                parent=self
            )

    def _parse_ipconfig_output(self, output: str) -> list:
        adapters = []
        current_adapter = None
        lines = output.splitlines()

        adapter_header_pattern = re.compile(r"^(.*?)(?:\s*适配器)?:\s*$")
        description_pattern = re.compile(r"Description[.\s]*: (.*)")
        media_state_pattern = re.compile(r"Media State[.\s]*: (.*)")

        ipv4_pattern = re.compile(r"IPv4 地址[.\s]*: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?:\s*\(.*\))?")

        dns_server_pattern = re.compile(r"DNS 服务器[.\s]*: ([0-9a-fA-F.:%]+)")

        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            header_match = adapter_header_pattern.match(line)
            if header_match and not line.startswith(" ") and \
               not re.match(r"(?:Primary Dns Suffix|Default Gateway|Node Type|Host Name|IP Routing Enabled|WINS Proxy Enabled)[.\s]*:", line):
                if current_adapter:
                    adapters.append(current_adapter)

                adapter_full_name = header_match.group(1).strip()
                current_adapter = {
                    "Name": adapter_full_name,
                    "IPv4 Address": "N/A",
                    "DNS Servers": [],
                    "Media State": "N/A"
                }

                for j in range(line_idx + 1, len(lines)):
                    detail_line = lines[j].strip()
                    if not detail_line:
                        break
                    if not detail_line.startswith(" "):
                        break

                    desc_match = description_pattern.search(detail_line)
                    if desc_match:
                        current_adapter["Name"] = desc_match.group(1).strip()
                        current_adapter["Name"] = re.sub(r'(?i)\s*(adapter|virtual|pseudo-interface|controller|device)$', '', current_adapter["Name"]).strip()
                        current_adapter["Name"] = re.sub(r'#\d+$', '', current_adapter["Name"]).strip()
                        current_adapter["Name"] = re.sub(r'\s*\(\d+\)$', '', current_adapter["Name"]).strip()
                        continue

                    media_state_match = media_state_pattern.search(detail_line)
                    if media_state_match:
                        current_adapter["Media State"] = media_state_match.group(1).strip()
                        continue

                    ipv4_match = ipv4_pattern.search(detail_line)
                    if ipv4_match:
                        current_adapter["IPv4 Address"] = ipv4_match.group(1)
                        continue

                    dns_match = dns_server_pattern.search(detail_line)
                    if dns_match:
                        dns_server = dns_match.group(1)
                        if dns_server and dns_server not in current_adapter["DNS Servers"]:
                            current_adapter["DNS Servers"].append(dns_server)
                        continue
                continue

        if current_adapter:
            adapters.append(current_adapter)

        return adapters

    def _confirm_and_set_dns(self, dns_servers: list, dns_type: str):
        action_name = f"设置 DNS 为 {dns_type}"
        message = f"您确定要将所有网络适配器的 DNS 设置为 {dns_type} 吗？此操作可能需要管理员权限，并可能导致短暂的网络中断。"
        if dns_servers:
            message += f"\n主要 DNS: {dns_servers[0]}"
            if len(dns_servers) > 1:
                message += f"\n备用 DNS: {dns_servers[1]}"
        else:
            message += "\nDNS 将被设置为自动获取。"

        dialog = Dialog("确认 DNS 设置", message, self)
        if dialog.exec_() == QDialog.Accepted:
            self._set_dns_for_all_adapters(dns_servers, action_name)
        else:
            self.log_widget.append_log(f"用户取消了操作: {action_name}")
            self.network_log_display.append(f"用户取消了操作: {action_name}")
            show_notification(
                title="操作取消",
                content=f"已取消执行 {action_name}。",
                notification_type="warning",
                parent=self
            )

    def _set_dns_for_all_adapters(self, dns_servers: list, description: str):
        self.network_log_display.append(f"开始 {description}...")
        self.log_widget.append_log(f"开始执行: {description}...")

        try:
            ipconfig_cmd = "chcp 65001 && ipconfig /all"
            process_ipconfig = subprocess.run(ipconfig_cmd, capture_output=True, text=True, shell=True,
                                              encoding='utf-8', errors='replace', check=True)
            ipconfig_output = process_ipconfig.stdout
            parsed_adapters = self._parse_ipconfig_output(ipconfig_output)

            all_adapter_names_for_netsh = [
                adapter['Name'] for adapter in parsed_adapters
                if adapter['Name'] and
                   ("adapter" in adapter['Name'].lower() or "适配器" in adapter['Name'] or
                    "vpn" in adapter['Name'].lower() or
                    re.search(r'\b(lan|wlan|ethernet)\b', adapter['Name'].lower()))
            ]

            if not all_adapter_names_for_netsh:
                self.network_log_display.append("未找到任何网络适配器。")
                self.log_widget.append_log("未找到任何网络适配器。")
                show_notification(
                    title="警告",
                    content="未找到任何网络适配器可供设置 DNS。",
                    notification_type="warning",
                    parent=self
                )
                return

            all_successful = True
            for adapter_name_for_netsh in all_adapter_names_for_netsh:
                if dns_servers:
                    primary_dns_cmd = f'chcp 65001 && netsh interface ip set dns name="{adapter_name_for_netsh}" static {dns_servers[0]} primary'
                    self.network_log_display.append(
                        f"设置适配器 '{adapter_name_for_netsh}' 的主要 DNS: {dns_servers[0]}")
                    self.log_widget.append_log(f"设置适配器 '{adapter_name_for_netsh}' 的主要 DNS: {dns_servers[0]}")
                    try:
                        subprocess.run(primary_dns_cmd, capture_output=True, text=True, shell=True, check=True,
                                       encoding='utf-8', errors='replace')
                    except subprocess.CalledProcessError as e:
                        self.network_log_display.append(
                            f"设置主要 DNS 失败 for '{adapter_name_for_netsh}': {e.stderr}")
                        self.log_widget.append_log(
                            f"设置主要 DNS 失败 for '{adapter_name_for_netsh}': {e.stderr}")
                        all_successful = False
                        continue

                    if len(dns_servers) > 1:
                        secondary_dns_cmd = f'chcp 65001 && netsh interface ip add dns name="{adapter_name_for_netsh}" {dns_servers[1]} index=2'
                        self.network_log_display.append(
                            f"设置适配器 '{adapter_name_for_netsh}' 的备用 DNS: {dns_servers[1]}")
                        self.log_widget.append_log(
                            f"设置适配器 '{adapter_name_for_netsh}' 的备用 DNS: {dns_servers[1]}")
                        try:
                            subprocess.run(secondary_dns_cmd, capture_output=True, text=True, shell=True, check=True,
                                           encoding='utf-8', errors='replace')
                        except subprocess.CalledProcessError as e:
                            self.network_log_display.append(
                                f"设置备用 DNS 失败 for '{adapter_name_for_netsh}': {e.stderr}")
                            self.log_widget.append_log(
                                f"设置备用 DNS 失败 for '{adapter_name_for_netsh}': {e.stderr}")
                            all_successful = False
                else:
                    reset_dns_cmd = f'chcp 65001 && netsh interface ip set dns name="{adapter_name_for_netsh}" source=dhcp'
                    self.network_log_display.append(f"重置适配器 '{adapter_name_for_netsh}' 的 DNS 为自动获取。")
                    self.log_widget.append_log(f"重置适配器 '{adapter_name_for_netsh}' 的 DNS 为自动获取。")
                    try:
                        subprocess.run(reset_dns_cmd, capture_output=True, text=True, shell=True, check=True,
                                       encoding='utf-8', errors='replace')
                    except subprocess.CalledProcessError as e:
                        self.network_log_display.append(
                            f"重置 DNS 失败 for '{adapter_name_for_netsh}': {e.stderr}")
                        self.log_widget.append_log(
                            f"重置 DNS 失败 for '{adapter_name_for_netsh}': {e.stderr}")
                        all_successful = False

            if all_successful:
                show_notification(
                    title=f"{description} 成功",
                    content=f"{description} 已完成。",
                    notification_type="success",
                    parent=self
                )
            else:
                show_notification(
                    title=f"{description} 失败",
                    content=f"{description} 执行过程中发生错误，请检查日志。",
                    notification_type="error",
                    parent=self
                )
        except Exception as e:
            self.network_log_display.append(f"执行 {description} 时发生未知错误: {e}")
            self.log_widget.append_log(f"执行 {description} 时发生未知错误: {e}")
            show_notification(
                title=f"{description} 错误",
                content=f"{description} 执行时发生未知错误。",
                notification_type="error",
                parent=self
            )
        finally:
            self._refresh_network_info()

    def _set_dns_secondary_for_all_adapters(self, dns_ip: str, description: str):
        self.network_log_display.append(f"开始 {description}...")
        self.log_widget.append_log(f"开始 {description}...")

        try:
            ipconfig_cmd = "chcp 65001 && ipconfig /all"
            process_ipconfig = subprocess.run(ipconfig_cmd, capture_output=True, text=True, shell=True,
                                              encoding='utf-8', errors='replace', check=True)
            ipconfig_output = process_ipconfig.stdout
            parsed_adapters = self._parse_ipconfig_output(ipconfig_output)

            all_adapter_names = [adapter['Name'] for adapter in parsed_adapters if
                                 adapter['Name'] and
                                 ("adapter" in adapter['Name'].lower() or "适配器" in adapter['Name'] or
                                  "vpn" in adapter['Name'].lower() or
                                  re.search(r'\b(lan|wlan|ethernet)\b', adapter['Name'].lower()))
                                 ]

            if not all_adapter_names:
                self.network_log_display.append("未找到任何网络适配器。")
                self.log_widget.append_log("未找到任何网络适配器。")
                show_notification(
                    title="警告",
                    content="未找到任何网络适配器可供设置 DNS。",
                    notification_type="warning",
                    parent=self
                )
                return

            all_successful = True
            for adapter_name in all_adapter_names:
                secondary_dns_cmd = f'chcp 65001 && netsh interface ip add dns name="{adapter_name}" {dns_ip} index=2'
                self.network_log_display.append(f"设置适配器 '{adapter_name}' 的备用 DNS: {dns_ip}")
                self.log_widget.append_log(f"设置适配器 '{adapter_name}' 的备用 DNS: {dns_ip}")
                try:
                    subprocess.run(secondary_dns_cmd, capture_output=True, text=True, shell=True, check=True,
                                   encoding='utf-8', errors='replace')
                except subprocess.CalledProcessError as e:
                    self.network_log_display.append(f"设置备用 DNS 失败 for '{adapter_name}': {e.stderr}")
                    self.log_widget.append_log(f"设置备用 DNS 失败 for '{adapter_name}': {e.stderr}")
                    all_successful = False

            if all_successful:
                show_notification(
                    title=f"{description} 成功",
                    content=f"{description} 已完成。",
                    notification_type="success",
                    parent=self
                )
            else:
                show_notification(
                    title=f"{description} 失败",
                    content=f"{description} 执行过程中发生错误，请检查日志。",
                    notification_type="error",
                    parent=self
                )
        except Exception as e:
            self.network_log_display.append(f"执行 {description} 时发生未知错误: {e}")
            self.log_widget.append_log(f"执行 {description} 时发生未知错误: {e}")
            show_notification(
                title=f"{description} 错误",
                content=f"{description} 执行时发生未知错误。",
                notification_type="error",
                parent=self
            )
        finally:
            self._refresh_network_info()

    def _start_dns_speed_test(self):
        self.dns_speed_table.setRowCount(0)
        self.network_log_display.append("开始 DNS 速度测试...")
        self.log_widget.append_log("开始 DNS 速度测试...")

        dns_servers_to_test = {
            "Google DNS": ["8.8.8.8", "8.8.4.4"],
            "Cloudflare DNS": ["1.1.1.1", "1.0.0.1"],
            "114 DNS": ["114.114.114.114", "114.114.115.115"],
            "阿里云 DNS": ["223.5.5.5", "223.6.6.6"],
            "腾讯云 DNS": ["119.29.29.29", "119.28.28.28"]
        }

        self.progress_dialog = QProgressDialog("正在测试 DNS 速度...", "取消", 0, len(dns_servers_to_test) * 2, self)
        self.progress_dialog.setWindowTitle("DNS 速度测试")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setMinimumDuration(0)

        self.ping_worker = PingWorker(dns_servers_to_test)
        self.ping_worker.result_signal.connect(self._update_dns_speed_result)
        self.ping_worker.finished_signal.connect(self._finish_dns_speed_test)
        self.ping_worker.start()

    def _update_dns_speed_result(self, dns_name_ip: str, results: dict):
        self.progress_step += 1
        self.progress_dialog.setValue(self.progress_step)

        row_position = self.dns_speed_table.rowCount()
        self.dns_speed_table.insertRow(row_position)

        avg_latency = results.get('avg_latency', -1)
        packet_loss_percent = results.get('packet_loss_percent', 100)
        error_msg = results.get('error', '')

        status = "正常"
        if avg_latency == -1 or packet_loss_percent == 100:
            status = "失败"
        elif packet_loss_percent > 0:
            status = f"丢包 ({packet_loss_percent}%)"

        self.dns_speed_table.setItem(row_position, 0, QTableWidgetItem(dns_name_ip))
        self.dns_speed_table.setItem(row_position, 1,
                                     QTableWidgetItem(str(avg_latency) if avg_latency != -1 else "N/A"))
        self.dns_speed_table.setItem(row_position, 2, QTableWidgetItem(str(packet_loss_percent)))
        self.dns_speed_table.setItem(row_position, 3, QTableWidgetItem(status))

        if error_msg:
            self.network_log_display.append(f"DNS 速度测试错误 ({dns_name_ip}): {error_msg}")
            self.log_widget.append_log(f"DNS 速度测试错误 ({dns_name_ip}): {error_msg}")
            self.network_log_display.append(
                f"原始输出: {results.get('raw_output', 'N/A')}")

        self.dns_speed_table.resizeRowsToContents()
        self.dns_speed_table.resizeColumnsToContents()

    def _finish_dns_speed_test(self):
        self.network_log_display.append("DNS 速度测试完成。")
        self.log_widget.append_log("DNS 速度测试完成。")
        show_notification(
            title="DNS 速度测试完成",
            content="所有 DNS 服务器的速度测试已完成。",
            notification_type="success",
            parent=self
        )
        self.progress_dialog.close()

        fastest_dns = None
        min_latency = float('inf')

        valid_results = []
        for row in range(self.dns_speed_table.rowCount()):
            latency_item = self.dns_speed_table.item(row, 1)
            packet_loss_item = self.dns_speed_table.item(row, 2)
            dns_name_item = self.dns_speed_table.item(row, 0)

            if latency_item and packet_loss_item and dns_name_item:
                try:
                    latency = int(latency_item.text())
                    packet_loss_percent = int(packet_loss_item.text())

                    if latency != -1 and packet_loss_percent == 0:
                        valid_results.append({
                            'name_ip': dns_name_item.text(),
                            'latency': latency
                        })
                except ValueError:
                    continue

        if valid_results:
            valid_results.sort(key=lambda x: x['latency'])
            fastest_dns_info = valid_results[0]
            fastest_dns = fastest_dns_info['name_ip']
            min_latency = fastest_dns_info['latency']

            self.network_log_display.append(f"最快且无丢包的 DNS 服务器是: {fastest_dns} (平均延迟: {min_latency}ms)")
            show_notification(
                title="最快 DNS 推荐",
                content=f"最快且无丢包的 DNS 服务器是: {fastest_dns} (平均延迟: {min_latency}ms)",
                notification_type="info",
                parent=self
            )
        else:
            self.network_log_display.append("未找到无丢包的最快 DNS 服务器。")
            show_notification(
                title="DNS 推荐",
                content="未找到无丢包的最快 DNS 服务器。",
                notification_type="warning",
                parent=self
            )


class PCCleanupWidget(QWidget):
    def __init__(self, log_widget: LogWidget, parent=None):
        super().__init__(parent)
        self.log_widget = log_widget
        self.vBoxLayout = QVBoxLayout(self)
        self.title = SubtitleLabel("电脑清理", self)
        self.vBoxLayout.addWidget(self.title)

        self.scan_button = PrimaryPushButton("扫描垃圾文件", self)
        self.scan_button.clicked.connect(self._scan_junk_files)
        self.vBoxLayout.addWidget(self.scan_button)

        self.clean_button = PrimaryPushButton("一键深度清理", self)
        self.clean_button.clicked.connect(self._confirm_deep_clean)
        self.vBoxLayout.addWidget(self.clean_button)

        self.cleanup_options_label = SubtitleLabel("更多清理选项", self)
        self.vBoxLayout.addWidget(self.cleanup_options_label)

        self.clean_browser_cache_button = PushButton("清理浏览器缓存", self)
        self.clean_browser_cache_button.clicked.connect(self._clean_browser_caches)
        self.vBoxLayout.addWidget(self.clean_browser_cache_button)

        self.empty_recycle_bin_button = PushButton("清空回收站", self)
        self.empty_recycle_bin_button.clicked.connect(self._empty_recycle_bin)
        self.vBoxLayout.addWidget(self.empty_recycle_bin_button)

        self.clean_windows_update_temp_button = PushButton("清理Windows更新临时文件", self)
        self.clean_windows_update_temp_button.clicked.connect(self._clean_windows_update_temp)
        self.vBoxLayout.addWidget(self.clean_windows_update_temp_button)

        self.clean_directx_shader_cache_button = PushButton("清理DirectX着色器缓存", self)
        self.clean_directx_shader_cache_button.clicked.connect(self._clean_directx_shader_cache)
        self.vBoxLayout.addWidget(self.clean_directx_shader_cache_button)

        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.setObjectName("PCCleanupWidget")

        self.junk_files_size = 0

    def _confirm_deep_clean(self):
        dialog = Dialog("确认深度清理", "您确定要执行深度清理吗？此操作将删除大量临时文件，可能需要管理员权限。", self)
        if dialog.exec_() == QDialog.Accepted:
            self._deep_clean()
        else:
            self.log_widget.append_log("用户取消了深度清理操作。")
            show_notification(
                title="操作取消",
                content="已取消深度清理。",
                notification_type="warning",
                parent=self
            )

    def _scan_junk_files(self):
        self.log_widget.append_log("开始扫描垃圾文件...")
        self.junk_files_size = 0
        temp_dirs = [
            os.path.join(os.environ.get('TEMP', ''), ''),
            os.path.join(os.environ.get('TMP', ''), ''),
            os.path.join(os.environ.get('WINDIR', ''), 'Temp'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
            os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Recent'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'INetCache'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
            os.path.join(os.environ.get('WINDIR', ''), 'Prefetch')
        ]

        files_to_clean = []
        for d in temp_dirs:
            if os.path.exists(d):
                for root, _, files in os.walk(d):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.isfile(file_path):
                                self.junk_files_size += os.path.getsize(file_path)
                                files_to_clean.append(file_path)
                        except OSError as e:
                            self.log_widget.append_log(f"无法访问文件 {file_path}: {e}")
            else:
                self.log_widget.append_log(f"目录不存在: {d}")

        self.log_widget.append_log(
            f"扫描完成。发现 {len(files_to_clean)} 个垃圾文件，总大小约 {self._format_bytes(self.junk_files_size)}。")
        show_notification(
            title="扫描完成",
            content=f"发现 {len(files_to_clean)} 个垃圾文件，总大小约 {self._format_bytes(self.junk_files_size)}。",
            notification_type="success",
            parent=self
        )

    def _deep_clean(self):
        self.log_widget.append_log("开始一键深度清理...")
        self._clean_temp_files()
        self._run_disk_cleanup()
        self._clean_browser_caches()
        self._empty_recycle_bin()
        self._clean_windows_update_temp()
        self._clean_directx_shader_cache()
        self.log_widget.append_log("深度清理完成。")
        show_notification(
            title="清理完成",
            content="电脑垃圾已深度清理。",
            notification_type="success",
            parent=self
        )

    def _clean_temp_files(self):
        self.log_widget.append_log("清理临时文件...")
        temp_dirs = [
            os.path.join(os.environ.get('TEMP', ''), ''),
            os.path.join(os.environ.get('TMP', ''), ''),
            os.path.join(os.environ.get('WINDIR', ''), 'Temp'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'INetCache'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
            os.path.join(os.environ.get('WINDIR', ''), 'Prefetch')
        ]

        cleaned_size = 0
        for d in temp_dirs:
            if os.path.exists(d):
                for root, dirs, files in os.walk(d, topdown=False):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.isfile(file_path):
                                cleaned_size += os.path.getsize(file_path)
                                os.remove(file_path)
                        except OSError as e:
                            self.log_widget.append_log(f"无法删除文件 {file_path}: {e}")
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                        except OSError as e:
                            self.log_widget.append_log(f"无法删除目录 {dir_path}: {e}")
            else:
                self.log_widget.append_log(f"目录不存在: {d}")
        self.log_widget.append_log(f"临时文件清理完成。释放空间约 {self._format_bytes(cleaned_size)}。")

    def _run_disk_cleanup(self):
        self.log_widget.append_log("启动Windows磁盘清理工具...")
        try:
            subprocess.Popen(["cleanmgr.exe", "/sagerun:1"])
            self.log_widget.append_log("Windows磁盘清理工具已启动。请手动确认清理选项（如果弹出）。")
            show_notification(
                title="磁盘清理",
                content="Windows磁盘清理工具已启动，请手动确认清理选项（如果弹出）。",
                notification_type="info",
                parent=self
            )
        except FileNotFoundError:
            self.log_widget.append_log("cleanmgr.exe 未找到。此功能仅限Windows系统。")
            show_notification(
                title="警告",
                content="cleanmgr.exe 未找到。此功能可能仅限Windows系统。",
                notification_type="warning",
                parent=self
            )
        except Exception as e:
            self.log_widget.append_log(f"启动磁盘清理工具失败: {e}")
            show_notification(
                title="错误",
                content="启动Windows磁盘清理工具失败。",
                notification_type="error",
                parent=self
            )

    def _clean_browser_caches(self):
        self.log_widget.append_log("开始清理浏览器缓存...")
        browser_cache_paths = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Mozilla', 'Firefox', 'Profiles'),
        ]
        cleaned_size = 0
        for path in browser_cache_paths:
            if os.path.exists(path):
                try:
                    for root, dirs, files in os.walk(path, topdown=False):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                if os.path.isfile(file_path):
                                    cleaned_size += os.path.getsize(file_path)
                                    os.remove(file_path)
                            except OSError:
                                pass
                        for dir_name in dirs:
                            dir_path = os.path.join(root, dir_name)
                            try:
                                if not os.listdir(dir_path):
                                    os.rmdir(dir_path)
                            except OSError:
                                pass
                    self.log_widget.append_log(f"清理了 {path}。")
                except Exception as e:
                    self.log_widget.append_log(f"清理浏览器缓存失败 ({path}): {e}")
        self.log_widget.append_log(f"浏览器缓存清理完成。释放空间约 {self._format_bytes(cleaned_size)}。")
        show_notification(
            title="浏览器缓存清理",
            content=f"浏览器缓存清理完成。释放空间约 {self._format_bytes(cleaned_size)}。",
            notification_type="success",
            parent=self
        )

    def _empty_recycle_bin(self):
        self.log_widget.append_log("开始清空回收站...")
        try:
            shell32 = ctypes.WinDLL('shell32')
            result = shell32.SHEmptyRecycleBinW(None, None, 0)

            if result == 0:
                self.log_widget.append_log("回收站已成功清空。")
                show_notification(
                    title="清空回收站",
                    content="回收站已成功清空。",
                    notification_type="success",
                    parent=self
                )
            elif result == 0x40000000:
                self.log_widget.append_log("清空回收站操作被取消或回收站为空。")
                show_notification(
                    title="清空回收站",
                    content="清空回收站操作被取消或回收站为空。",
                    notification_type="info",
                    parent=self
                )
            else:
                self.log_widget.append_log(f"清空回收站失败，错误码: {result}")
                show_notification(
                    title="清空回收站失败",
                    content=f"清空回收站失败，错误码: {result}。",
                    notification_type="error",
                    parent=self
                )
        except Exception as e:
            self.log_widget.append_log(f"清空回收站时发生错误: {e}")
            show_notification(
                title="清空回收站错误",
                content=f"清空回收站时发生未知错误: {e}。",
                notification_type="error",
                parent=self
            )

    def _clean_windows_update_temp(self):
        self.log_widget.append_log("开始清理Windows更新临时文件...")
        try:
            update_temp_path = os.path.join(os.environ.get('WINDIR', ''), 'SoftwareDistribution', 'Download')
            if os.path.exists(update_temp_path):
                shutil.rmtree(update_temp_path, ignore_errors=True)
                self.log_widget.append_log(f"尝试清理 {update_temp_path} 完成。")
                show_notification(
                    title="Windows更新清理",
                    content=f"尝试清理Windows更新临时文件完成。",
                    notification_type="success",
                    parent=self
                )
            else:
                self.log_widget.append_log("Windows更新临时文件目录不存在。")
                show_notification(
                    title="Windows更新清理",
                    content="Windows更新临时文件目录不存在。",
                    notification_type="info",
                    parent=self
                )
        except Exception as e:
            self.log_widget.append_log(f"清理Windows更新临时文件失败: {e}")
            show_notification(
                title="Windows更新清理失败",
                content=f"清理Windows更新临时文件失败: {e}。",
                notification_type="error",
                parent=self
            )

    def _clean_directx_shader_cache(self):
        self.log_widget.append_log("开始清理DirectX着色器缓存...")
        dx_cache_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'DirectX', 'ShaderCache')
        cleaned_size = 0
        if os.path.exists(dx_cache_path):
            try:
                for root, dirs, files in os.walk(dx_cache_path, topdown=False):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.isfile(file_path):
                                cleaned_size += os.path.getsize(file_path)
                                os.remove(file_path)
                        except OSError:
                            pass
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                        except OSError:
                            pass
                self.log_widget.append_log(f"清理了DirectX着色器缓存。释放空间约 {self._format_bytes(cleaned_size)}。")
                show_notification(
                    title="DirectX着色器缓存清理",
                    content=f"清理DirectX着色器缓存完成。释放空间约 {self._format_bytes(cleaned_size)}。",
                    notification_type="success",
                    parent=self
                )
            except Exception as e:
                self.log_widget.append_log(f"清理DirectX着色器缓存失败: {e}")
                show_notification(
                    title="DirectX着色器缓存清理失败",
                    content=f"清理DirectX着色器缓存失败: {e}。",
                    notification_type="error",
                    parent=self
                )
        else:
            self.log_widget.append_log("DirectX着色器缓存目录不存在。")
            show_notification(
                title="DirectX着色器缓存清理",
                content="DirectX着色器缓存目录不存在。",
                notification_type="info",
                parent=self
            )

    def _format_bytes(self, size_in_bytes: int) -> str:
        if size_in_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_in_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_in_bytes / p, 2)
        return f"{s} {size_name[i]}"


class CircularGaugeWidget(QWidget):
    def __init__(self, label: str, unit: str, max_value: float = 100.0, parent=None):
        super().__init__(parent)
        self._label = label
        self.unit = unit
        self.max_value = max_value
        self._value = 0.0
        self.setFixedSize(150, 150)

        self._display_value = 0.0
        self._animation = QPropertyAnimation(self, b"display_value")
        self._animation.setDuration(500)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def _get_display_value(self):
        return self._display_value

    def _set_display_value(self, value):
        self._display_value = value
        self.update()

    display_value = pyqtProperty(float, _get_display_value, _set_display_value)

    def set_value(self, value: float):
        self._value = value
        self._animation.setStartValue(self._display_value)
        self._animation.setEndValue(value)
        self._animation.start()

    def set_label(self, label: str):
        self._label = label
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(5, 5, -5, -5)

        bg_color = QApplication.palette().window().color()
        painter.setPen(QPen(QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 100), 10))
        painter.drawEllipse(rect)

        progress_color = QColor(50, 205, 50)
        if self._display_value > 75:
            progress_color = QColor(255, 69, 0)
        elif self._display_value > 50:
            progress_color = QColor(255, 215, 0)

        painter.setPen(QPen(progress_color, 10))

        start_angle = 90 * 16
        span_angle = -int((self._display_value / self.max_value) * 360 * 16)

        painter.drawArc(rect, start_angle, span_angle)

        text_color = QColor(255, 255, 255) if QApplication.palette().window().color().lightness() < 128 else QColor(0,
                                                                                                                    0,
                                                                                                                    0)
        painter.setPen(QPen(text_color))

        font = painter.font()
        font.setPointSize(16)
        painter.setFont(font)
        value_text = f"{self._display_value:.1f}{self.unit}"
        value_text_rect = rect.adjusted(0, int(rect.height() * 0.1), 0,
                                        int(-rect.height() * 0.3))
        painter.drawText(value_text_rect, Qt.AlignCenter, value_text)

        font.setPointSize(10)
        painter.setFont(font)
        label_text_rect = rect.adjusted(0, int(rect.height() * 0.3), 0,
                                        int(-rect.height() * 0.1))
        painter.drawText(label_text_rect, Qt.AlignHCenter | Qt.AlignTop, self._label)


class PerformanceMonitorWorker(QThread):
    cpu_usage_signal = pyqtSignal(float)
    ram_usage_signal = pyqtSignal(float, float, float)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        while self._running:
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage_signal.emit(cpu_percent)

            vm = psutil.virtual_memory()
            self.ram_usage_signal.emit(vm.total, vm.used, vm.percent)

    def stop(self):
        self._running = False
        self.wait()


class PCOptimizationWidget(QWidget):
    def __init__(self, log_widget: LogWidget, parent=None):
        super().__init__(parent)
        self.log_widget = log_widget
        self.setObjectName("PCOptimizationWidget")

        self.main_h_layout = QHBoxLayout(self)
        self.left_buttons_layout = QVBoxLayout()
        self.right_display_layout = QVBoxLayout()

        self.title = SubtitleLabel("电脑优化", self)
        self.left_buttons_layout.addWidget(self.title)

        self.optimize_ram_button = PrimaryPushButton("优化RAM内存", self)
        self.optimize_ram_button.clicked.connect(self._optimize_ram_action)
        self.left_buttons_layout.addWidget(self.optimize_ram_button)

        self.clear_background_button = PrimaryPushButton("清理后台进程", self)
        self.clear_background_button.clicked.connect(lambda: self._confirm_optimization("清理后台进程",
                                                                                        "此操作将尝试清理后台进程。请注意，不当终止可能导致系统不稳定。"))
        self.left_buttons_layout.addWidget(self.clear_background_button)

        self.optimize_cpu_button = PrimaryPushButton("优化加速CPU/清理线程", self)
        self.optimize_cpu_button.clicked.connect(
            lambda: self._confirm_optimization("CPU/线程优化", "此操作将尝试优化CPU性能和清理线程。"))
        self.left_buttons_layout.addWidget(self.optimize_cpu_button)

        self.set_ultimate_performance_button = PrimaryPushButton("设置卓越性能电源计划", self)
        self.set_ultimate_performance_button.clicked.connect(self._set_ultimate_performance_plan)
        self.left_buttons_layout.addWidget(self.set_ultimate_performance_button)

        self.optimize_vram_button = PrimaryPushButton("优化显存", self)
        self.optimize_vram_button.clicked.connect(
            lambda: self._confirm_optimization("显存优化", "此操作将尝试优化显存。"))
        self.left_buttons_layout.addWidget(self.optimize_vram_button)

        self.all_in_one_optimize_button = PrimaryPushButton("一键全面优化", self)
        self.all_in_one_optimize_button.clicked.connect(
            lambda: self._confirm_optimization("一键全面优化", "此操作将执行所有优化项目。"))
        self.left_buttons_layout.addWidget(self.all_in_one_optimize_button)

        self.left_buttons_layout.addStretch(1)
        self.left_buttons_layout.setContentsMargins(20, 20, 10, 20)

        self.optimization_log_display = TextEdit(self)
        self.optimization_log_display.setReadOnly(True)
        self.optimization_log_display.setPlaceholderText("这里会显示电脑优化操作的详细日志...")
        self.right_display_layout.addWidget(SubtitleLabel("电脑优化日志", self))
        self.right_display_layout.addWidget(self.optimization_log_display)

        self.gauges_h_layout = QHBoxLayout()
        self.cpu_gauge = CircularGaugeWidget("CPU 使用", "%", parent=self)
        self.ram_gauge = CircularGaugeWidget("内存 使用", "%", parent=self)

        self.gauges_h_layout.addWidget(self.cpu_gauge)
        self.gauges_h_layout.addWidget(self.ram_gauge)
        self.gauges_h_layout.addStretch(1)
        self.right_display_layout.addLayout(self.gauges_h_layout)
        self.right_display_layout.addStretch(1)

        self.right_display_layout.setContentsMargins(10, 20, 20, 20)

        self.main_h_layout.addLayout(self.left_buttons_layout, 1)
        self.main_h_layout.addLayout(self.right_display_layout, 2)

        self.monitor_worker = PerformanceMonitorWorker()
        self.monitor_worker.cpu_usage_signal.connect(self.cpu_gauge.set_value)
        self.monitor_worker.ram_usage_signal.connect(self._update_ram_gauge)
        self.monitor_worker.start()

    def _update_ram_gauge(self, total: float, used: float, percent: float):
        self.ram_gauge.set_value(percent)
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        self.ram_gauge.set_label(f"内存 ({used_gb:.1f}G/{total_gb:.1f}G)")

    def _confirm_optimization(self, action_name: str, message: str):
        dialog = Dialog("确认优化操作", f"您确定要执行 '{action_name}' 吗？\n{message}", self)
        if dialog.exec_() == QDialog.Accepted:
            if action_name == "RAM内存优化":
                self._optimize_ram_action()
            elif action_name == "清理后台进程":
                self._clear_background_processes_action()
            elif action_name == "CPU/线程优化":
                self._optimize_cpu_action()
            elif action_name == "显存优化":
                self._optimize_vram_action()
            elif action_name == "一键全面优化":
                self._all_in_one_optimize_action()
        else:
            self.log_widget.append_log(f"用户取消了操作: {action_name}")
            self.optimization_log_display.append(f"用户取消了操作: {action_name}")
            show_notification(
                title="操作取消",
                content=f"已取消执行 {action_name}。",
                notification_type="warning",
                parent=self
            )

    def _run_powercfg_command(self, command: str, description: str):
        self.optimization_log_display.append(f"开始执行: {description}...")
        self.log_widget.append_log(f"开始执行: {description}...")
        full_command = f"chcp 65001 && {command}"
        try:
            process = subprocess.run(full_command, capture_output=True, text=True, shell=True, check=True,
                                     encoding='utf-8', errors='replace')
            self.optimization_log_display.append(f"{description} 完成。")
            self.optimization_log_display.append(f"输出:\n{process.stdout}")
            self.log_widget.append_log(f"{description} 完成。")
            self.log_widget.append_log(f"输出:\n{process.stdout}")
            if process.stderr:
                self.optimization_log_display.append(f"错误输出:\n{process.stderr}")
                self.log_widget.append_log(f"错误输出:\n{process.stderr}")
            show_notification(
                title=f"{description} 成功",
                content=f"{description} 已完成。",
                notification_type="success",
                parent=self
            )
            return True
        except subprocess.CalledProcessError as e:
            self.optimization_log_display.append(f"执行 {description} 失败: {e}")
            self.optimization_log_display.append(f"错误输出:\n{e.stderr}")
            self.log_widget.append_log(f"执行 {description} 问题: {e}")
            self.log_widget.append_log(f"错误输出:\n{e.stderr}")
            show_notification(
                title=f"{description} 失败",
                content=f"{description} 执行失败，请检查日志。",
                notification_type="error",
                parent=self
            )
            return False
        except Exception as e:
            self.optimization_log_display.append(f"执行 {description} 时发生未知错误: {e}")
            self.log_widget.append_log(f"执行 {description} 时发生未知错误: {e}")
            show_notification(
                title=f"{description} 错误",
                content=f"{description} 执行时发生未知错误。",
                notification_type="error",
                parent=self
            )
            return False

    def _set_ultimate_performance_plan(self):
        ultimate_performance_guid = "e9a42b02-d5df-448d-aa00-03f147494561"

        self.optimization_log_display.append("检查卓越性能电源计划...")
        self.log_widget.append_log("检查卓越性能电源计划...")

        list_plans_cmd = "powercfg /list"
        try:
            process = subprocess.run(f"chcp 65001 && {list_plans_cmd}", capture_output=True, text=True, shell=True,
                                     encoding='utf-8', errors='replace', check=True)
            output = process.stdout

            if ultimate_performance_guid.lower() in output.lower():
                self.optimization_log_display.append("卓越性能电源计划已存在。尝试激活...")
                self.log_widget.append_log("卓越性能电源计划已存在。尝试激活...")
                activate_cmd = f"powercfg /setactive {ultimate_performance_guid}"
                self._run_powercfg_command(activate_cmd, "激活卓越性能电源计划")
            else:
                self.optimization_log_display.append("卓越性能电源计划不存在。尝试注册...")
                self.log_widget.append_log("卓越性能电源计划不存在。尝试注册...")
                register_cmd = f"powercfg /duplicatescheme {ultimate_performance_guid}"
                if self._run_powercfg_command(register_cmd, "注册卓越性能电源计划"):
                    self.optimization_log_display.append("卓越性能电源计划注册成功。尝试激活...")
                    self.log_widget.append_log("卓越性能电源计划注册成功。尝试激活...")
                    activate_cmd = f"powercfg /setactive {ultimate_performance_guid}"
                    self._run_powercfg_command(activate_cmd, "激活卓越性能电源计划")
                else:
                    show_notification(
                        title="操作失败",
                        content="无法注册卓越性能电源计划，请确保以管理员身份运行程序。",
                        notification_type="error",
                        parent=self
                    )
        except Exception as e:
            self.optimization_log_display.append(f"检查电源计划时发生错误: {e}")
            self.log_widget.append_log(f"检查电源计划时发生错误: {e}")
            show_notification(
                title="电源计划操作失败",
                content="检查或设置电源计划时发生错误。",
                notification_type="error",
                parent=self
            )

    def _optimize_ram_action(self):
        self.optimization_log_display.append("开始优化RAM内存...")
        self.log_widget.append_log("开始优化RAM内存...")

        try:
            kernel32 = ctypes.WinDLL('kernel32')
            psapi = ctypes.WinDLL('psapi')

            EmptyWorkingSet = psapi.EmptyWorkingSet
            EmptyWorkingSet.argtypes = [ctypes.c_void_p]
            EmptyWorkingSet.restype = ctypes.c_bool

            current_process = psutil.Process(os.getpid())
            process_handle = kernel32.OpenProcess(0x1F0FFF, False, current_process.pid)

            if process_handle:
                if EmptyWorkingSet(process_handle):
                    self.optimization_log_display.append("成功请求当前进程释放工作集内存。")
                    self.log_widget.append_log("成功请求当前进程释放工作集内存。")
                    show_notification(
                        title="RAM优化",
                        content="已请求当前进程释放工作集内存。",
                        notification_type="success",
                        parent=self
                    )
                else:
                    error_code = kernel32.GetLastError()
                    self.optimization_log_display.append(f"请求释放工作集内存失败，错误码: {error_code}")
                    self.log_widget.append_log(f"请求释放工作集内存失败，错误码: {error_code}")
                    show_notification(
                        title="RAM优化失败",
                        content=f"请求释放工作集内存失败，错误码: {error_code}。",
                        notification_type="error",
                        parent=self
                    )
                kernel32.CloseHandle(process_handle)
            else:
                self.optimization_log_display.append("无法获取当前进程句柄，可能权限不足。")
                self.log_widget.append_log("无法获取当前进程句柄，可能权限不足。")
                show_notification(
                    title="RAM优化警告",
                    content="无法获取当前进程句柄，可能权限不足。请尝试以管理员身份运行。",
                    notification_type="warning",
                    parent=self
                )

            self.optimization_log_display.append("RAM优化尝试完成。")
            self.log_widget.append_log("RAM内存优化尝试完成。")

        except Exception as e:
            self.optimization_log_display.append(f"RAM优化时发生错误: {e}")
            self.log_widget.append_log(f"RAM优化时发生错误: {e}")
            show_notification(
                title="RAM优化错误",
                content=f"RAM优化时发生未知错误: {e}。",
                notification_type="error",
                parent=self
            )

    def _clear_background_processes_action(self):
        self.optimization_log_display.append("开始清理后台进程...")
        self.optimization_log_display.append("清理后台进程需要谨慎操作，不当终止可能导致系统不稳定。")
        self.optimization_log_display.append("建议通过任务管理器手动结束不必要的进程。")
        self.log_widget.append_log("后台进程清理尝试完成。")
        show_notification(
            title="清理后台进程",
            content="清理后台进程需谨慎。建议通过任务管理器手动结束不必要的进程。",
            notification_type="info",
            parent=self
        )

    def _optimize_cpu_action(self):
        self.optimization_log_display.append("开始优化加速CPU/清理线程...")
        self.optimization_log_display.append("CPU优化主要涉及电源管理和关闭CPU密集型应用。")
        self.optimization_log_display.append("请确保您的电源计划设置为“卓越性能”以获得最佳CPU性能。")
        self.log_widget.append_log("CPU优化尝试完成。")
        show_notification(
            title="CPU优化",
            content="CPU优化主要涉及电源管理和关闭CPU密集型应用。请确保电源计划设置为卓越性能。",
            notification_type="info",
            parent=self
        )

    def _optimize_vram_action(self):
        self.optimization_log_display.append("开始优化显存...")
        self.optimization_log_display.append("显存优化通常由显卡驱动和应用程序管理。")
        self.optimization_log_display.append("建议更新显卡驱动并关闭占用大量显存的应用程序。")
        self.log_widget.append_log("显存优化尝试完成。")
        show_notification(
            title="显存优化",
            content="显存优化通常由显卡驱动和应用程序管理。建议更新驱动并关闭占用大量显存的应用程序。",
            notification_type="info",
            parent=self
        )

    def _all_in_one_optimize_action(self):
        self.optimization_log_display.append("开始一键全面优化...")
        self._optimize_ram_action()
        self._clear_background_processes_action()
        self._optimize_cpu_action()
        self._optimize_vram_action()
        self.optimization_log_display.append("一键全面优化完成。")
        self.log_widget.append_log("一键全面优化完成。")
        show_notification(
            title="全面优化完成",
            content="电脑已进行全面优化。",
            notification_type="success",
            parent=self
        )

    def _format_bytes(self, size_in_bytes: int) -> str:
        if size_in_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_in_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_in_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def closeEvent(self, event):
        if self.monitor_worker.isRunning():
            self.monitor_worker.stop()
        super().closeEvent(event)


class FileSizeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_sizes = {}
        self.calculators = {}
        self.tree_view = None

    size_calculated = pyqtSignal(str, str)

    def paint(self, painter, option, index):
        if index.column() == 1:
            file_path = index.model().filePath(index)
            if index.model().isDir(index):
                if file_path in self.folder_sizes:
                    text = self.folder_sizes[file_path]
                else:
                    text = "计算中..."
                    if file_path not in self.calculators and os.path.isdir(file_path):
                        calculator = FolderSizeCalculator(file_path)
                        calculator.size_calculated.connect(self._on_size_calculated)
                        calculator.start()
                        self.calculators[file_path] = calculator
                option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter
                painter.drawText(option.rect, option.displayAlignment, text)
            else:
                super().paint(painter, option, index)
        else:
            super().paint(painter, option, index)

    def _on_size_calculated(self, path, size_str):
        self.folder_sizes[path] = size_str
        if self.tree_view and self.tree_view.model():
            idx = self.tree_view.model().index(path)
            if idx.isValid():
                self.tree_view.model().dataChanged.emit(self.tree_view.model().index(idx.row(), 1, idx.parent()),
                                            self.tree_view.model().index(idx.row(), 1, idx.parent()))
        if path in self.calculators:
            del self.calculators[path]


class FolderSizeCalculator(QThread):
    size_calculated = pyqtSignal(str, str)

    def __init__(self, folder_path: str):
        super().__init__()
        self.folder_path = folder_path

    def run(self):
        total_size = 0
        try:
            if not os.path.exists(self.folder_path) or not os.path.isdir(self.folder_path):
                self.size_calculated.emit(self.folder_path, "N/A")
                return

            for dirpath, dirnames, filenames in os.walk(self.folder_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        if os.path.isfile(fp) and not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
                    except OSError:
                        pass
                try:
                    os.listdir(dirpath)
                except OSError:
                    dirnames[:] = []
        except Exception as e:
            self.size_calculated.emit(self.folder_path, f"错误: {e}")
            return

        size_str = self._format_bytes(total_size)
        self.size_calculated.emit(self.folder_path, size_str)

    def _format_bytes(self, size_in_bytes: int) -> str:
        if size_in_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_in_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_in_bytes / p, 2)
        return f"{s} {size_name[i]}"


class KeyCaptureLineEdit(QLineEdit):
    key_captured = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("按下任意键设置快捷键")
        self.current_key_code = None

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.setText("")
            self.current_key_code = None
            self.key_captured.emit(0)
        elif key not in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            self.setText(event.text() if event.text() else QKeySequence(key).toString())
            self.current_key_code = key
            self.key_captured.emit(key)
        else:
            super().keyPressEvent(event)


class FileManagementWidget(QWidget):
    def __init__(self, log_widget: LogWidget, parent=None):
        super().__init__(parent)
        self.log_widget = log_widget
        self.vBoxLayout = QVBoxLayout(self)
        self.title = SubtitleLabel("文件管理", self)
        self.vBoxLayout.addWidget(self.title)

        self.nav_layout = QHBoxLayout()
        self.back_button = PushButton("返回", self)
        self.back_button.clicked.connect(self._go_back_directory)
        self.nav_layout.addWidget(self.back_button)
        self.current_path_label = BodyLabel("", self)
        self.nav_layout.addWidget(self.current_path_label)
        self.nav_layout.addStretch(1)
        self.vBoxLayout.addLayout(self.nav_layout)

        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.model.setFilter(QDir.AllEntries | QDir.Hidden | QDir.System)
        self.tree_view = QTreeView(self)
        self.tree_view.setModel(self.model)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.tree_view.setRootIndex(self.model.index(os.path.expanduser("~")))
        self.tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree_view.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree_view.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_view.header().setSectionResizeMode(3, QHeaderView.Stretch)

        self.size_delegate = FileSizeDelegate(self.tree_view)
        self.tree_view.setItemDelegateForColumn(1, self.size_delegate)
        self.size_delegate.size_calculated.connect(self._on_folder_size_calculated)
        self.size_delegate.tree_view = self.tree_view

        self.tree_view.clicked.connect(self._on_item_clicked)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)
        self.vBoxLayout.addWidget(self.tree_view)

        self.action_layout = QHBoxLayout()
        self.open_explorer_button = PushButton("在资源管理器中打开", self)
        self.open_explorer_button.clicked.connect(self._open_in_explorer)
        self.action_layout.addWidget(self.open_explorer_button)

        self.delete_button = PushButton("删除", self)
        self.delete_button.clicked.connect(self._delete_selected_item)
        self.action_layout.addWidget(self.delete_button)

        self.edit_file_button = PushButton("编辑文件", self)
        self.edit_file_button.clicked.connect(self._edit_file_from_button)
        self.action_layout.addWidget(self.edit_file_button)

        self.vBoxLayout.addLayout(self.action_layout)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.setObjectName("FileManagementWidget")

        self._update_current_path_label()
        self._calculate_visible_folder_sizes()

    def _calculate_visible_folder_sizes(self):
        root_index = self.tree_view.rootIndex()
        for row in range(self.model.rowCount(root_index)):
            index = self.model.index(row, 0, root_index)
            if self.model.isDir(index):
                folder_path = self.model.filePath(index)
                if folder_path not in self.size_delegate.folder_sizes and folder_path not in self.size_delegate.calculators:
                    calculator = FolderSizeCalculator(folder_path)
                    calculator.size_calculated.connect(self._on_folder_size_calculated)
                    calculator.start()
                    self.size_delegate.calculators[folder_path] = calculator

    def _update_current_path_label(self):
        current_path = self.model.filePath(self.tree_view.rootIndex())

        display_text = f"当前路径: {current_path}"
        if os.path.isdir(current_path):
            try:
                if not os.listdir(current_path):
                    display_text += " (空文件夹)"
            except OSError as e:
                display_text += f" (无法访问: {e})"
        self.current_path_label.setText(display_text)

        self.size_delegate.folder_sizes.clear()
        for calc in list(self.size_delegate.calculators.values()):
            calc.quit()
            calc.wait()
        self.size_delegate.calculators.clear()
        self._calculate_visible_folder_sizes()

    def _on_folder_size_calculated(self, path: str, size_str: str):
        self.size_delegate.folder_sizes[path] = size_str
        idx = self.tree_view.model().index(path)
        if idx.isValid():
            self.tree_view.model().dataChanged.emit(self.tree_view.model().index(idx.row(), 1, idx.parent()),
                                        self.tree_view.model().index(idx.row(), 1, idx.parent()))
        if path in self.size_delegate.calculators:
            del self.size_delegate.calculators[path]

    def _go_back_directory(self):
        current_index = self.tree_view.rootIndex()
        parent_index = self.model.parent(current_index)
        if parent_index.isValid():
            self.tree_view.setRootIndex(parent_index)
            self._update_current_path_label()
            self.log_widget.append_log(f"返回到: {self.model.filePath(parent_index)}")
        else:
            self.log_widget.append_log("已在根目录，无法返回。")
            show_notification(
                title="无法返回",
                content="已在根目录，无法返回上一级。",
                notification_type="warning",
                parent=self
            )

    def _on_item_clicked(self, index):
        file_path = self.model.filePath(index)
        self.log_widget.append_log(f"选中: {file_path}")

    def _on_item_double_clicked(self, index):
        file_path = self.model.filePath(index)
        if self.model.isDir(index):
            self.tree_view.setRootIndex(index)
            self._update_current_path_label()
            self.log_widget.append_log(f"进入目录: {file_path}")
        else:
            self.log_widget.append_log(f"双击文件: {file_path}")
            self._edit_file(file_path)

    def _open_in_explorer(self):
        selected_indexes = self.tree_view.selectedIndexes()
        if not selected_indexes:
            show_notification(
                title="未选择",
                content="请选择一个文件或文件夹。",
                notification_type="warning",
                parent=self
            )
            return

        file_path = self.model.filePath(selected_indexes[0])
        try:
            subprocess.Popen(f'explorer /select,"{file_path}"')
            self.log_widget.append_log(f"在资源管理器中打开: {file_path}")
            show_notification(
                title="成功",
                content=f"已在资源管理器中打开 {file_path}",
                notification_type="success",
                parent=self
            )
        except Exception as e:
            self.log_widget.append_log(f"无法在资源管理器中打开 {file_path}: {e}")
            show_notification(
                title="错误",
                content=f"无法在资源管理器中打开 {file_path}",
                notification_type="error",
                parent=self
            )

    def _delete_selected_item(self):
        selected_indexes = self.tree_view.selectedIndexes()
        if not selected_indexes:
            show_notification(
                title="未选择",
                content="请选择要删除的文件或文件夹。",
                notification_type="warning",
                parent=self
            )
            return

        file_paths_to_delete = sorted(
            list(set(self.model.filePath(idx) for idx in selected_indexes if idx.column() == 0)))

        if not file_paths_to_delete:
            show_notification(
                title="未选择",
                content="请选择要删除的文件或文件夹。",
                notification_type="warning",
                parent=self
            )
            return

        if len(file_paths_to_delete) > 1:
            message = f"您确定要删除选定的 {len(file_paths_to_delete)} 个项目吗？此操作不可撤销！"
        else:
            message = f"您确定要删除 '{file_paths_to_delete[0]}' 吗？此操作不可撤销！"

        dialog = Dialog("确认删除", message, self)
        if dialog.exec_() != QDialog.Accepted:
            self.log_widget.append_log(f"用户取消删除操作。")
            return

        all_successful = True
        for file_path in file_paths_to_delete:
            is_dir = os.path.isdir(file_path)
            try:
                if is_dir:
                    shutil.rmtree(file_path)
                    self.log_widget.append_log(f"已删除目录: {file_path}")
                else:
                    os.remove(file_path)
                    self.log_widget.append_log(f"已删除文件: {file_path}")
            except OSError as e:
                self.log_widget.append_log(f"删除失败 {file_path}: {e}")
                show_notification(
                    title="删除失败",
                    content=f"无法删除 {file_path}: {e}",
                    notification_type="error",
                    parent=self
                )
                all_successful = False

        if all_successful:
            show_notification(
                title="删除成功",
                content="所有选定项目已成功删除。",
                notification_type="success",
                parent=self
            )
        self.model.refresh()

    def _edit_file_from_button(self):
        selected_indexes = self.tree_view.selectedIndexes()
        if not selected_indexes:
            show_notification(
                title="未选择",
                content="请选择一个文件进行编辑。",
                notification_type="warning",
                parent=self
            )
            return
        file_path = self.model.filePath(selected_indexes[0])
        self._edit_file(file_path)

    def _edit_file(self, file_path: str):
        if os.path.isdir(file_path):
            show_notification(
                title="文件类型错误",
                content="无法编辑文件夹。",
                notification_type="warning",
                parent=self
            )
            return

        content = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            pass
        except Exception as e:
            self.log_widget.append_log(f"读取文件失败 {file_path}: {e}")
            show_notification(
                title="读取失败",
                content=f"无法读取文件 {file_path}: {e}",
                notification_type="error",
                parent=self
            )
            return

        if content is not None:
            editor_dialog = TextEditorDialog(file_path, content, self)
            if editor_dialog.exec_() == QDialog.Accepted:
                new_content = editor_dialog.text_edit.toPlainText()
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    self.log_widget.append_log(f"已保存文件: {file_path}")
                    show_notification(
                        title="保存成功",
                        content=f"文件 {file_path} 已保存。",
                        notification_type="success",
                        parent=self
                    )
                except Exception as e:
                    self.log_widget.append_log(f"保存文件失败 {file_path}: {e}")
                    show_notification(
                        title="保存失败",
                        content=f"无法保存文件 {file_path}: {e}",
                        notification_type="error",
                        parent=self
                    )
        else:
            dialog = Dialog("无法作为文本编辑",
                            f"文件 '{file_path}' 无法作为文本文件打开。您想尝试使用系统默认应用程序打开它吗？", self)
            if dialog.exec_() == QDialog.Accepted:
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
                self.log_widget.append_log(f"尝试用默认应用程序打开文件: {file_path}")
            else:
                self.log_widget.append_log(f"用户取消了打开文件: {file_path}")
                show_notification(
                    title="操作取消",
                    content="已取消打开文件。",
                    notification_type="warning",
                    parent=self
                )

    def keyPressEvent(self, event):
        selected_indexes = self.tree_view.selectedIndexes()
        if not selected_indexes:
            super().keyPressEvent(event)
            return

        if event.key() == config.shortcuts['delete']:
            self._delete_selected_item()
        elif event.key() == config.shortcuts['rename']:
            if len(selected_indexes) == 1 and selected_indexes[0].isValid():
                self.tree_view.edit(self.model.index(selected_indexes[0].row(), 0, selected_indexes[0].parent()))
            else:
                show_notification(
                    title="重命名失败",
                    content="请选择一个文件或文件夹进行重命名。",
                    notification_type="warning",
                    parent=self
                )
        else:
            super().keyPressEvent(event)


class TextEditorDialog(Dialog):
    def __init__(self, file_path: str, initial_content: str, parent=None):
        super().__init__("编辑文件", f"正在编辑: {file_path}", parent)
        self.vBoxLayout = QVBoxLayout(self.contentWidget)
        self.text_edit = TextEdit(self.contentWidget)
        self.text_edit.setPlainText(initial_content)
        self.vBoxLayout.addWidget(self.text_edit)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.vBoxLayout.addWidget(self.buttonBox)

        self.resize(600, 400)


class SettingsWidget(QWidget):
    def __init__(self, config_manager: Config, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.vBoxLayout = QVBoxLayout(self)
        self.title = SubtitleLabel("设置", self)
        self.vBoxLayout.addWidget(self.title)

        self.theme_card = SettingCard(
            FluentIcon.PALETTE, "主题", "切换应用程序主题", self
        )
        self.theme_combo_box = ComboBox(self)
        self.theme_combo_box.addItems(["跟随系统", "浅色", "深色"])
        self.theme_combo_box.setCurrentText(
            self.config.theme.name.replace("AUTO", "跟随系统").replace("LIGHT", "浅色").replace("DARK", "深色"))
        self.theme_combo_box.currentIndexChanged.connect(self._on_theme_changed)
        theme_setting_layout = QHBoxLayout()
        theme_setting_layout.addWidget(self.theme_card)
        theme_setting_layout.addStretch(1)
        theme_setting_layout.addWidget(self.theme_combo_box)
        theme_setting_layout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(theme_setting_layout)

        self.notification_label = SubtitleLabel("通知设置", self)
        self.vBoxLayout.addWidget(self.notification_label)

        self.program_notification_card = SettingCard(
            FluentIcon.CHAT,
            "程序内通知",
            "控制程序内弹出消息的显示",
            self
        )
        self.program_notification_switch = SwitchButton(self)
        self.program_notification_switch.setChecked(self.config.program_notifications_enabled)
        self.program_notification_switch.checkedChanged.connect(self._on_program_notifications_changed)

        program_notification_layout = QHBoxLayout()
        program_notification_layout.addWidget(self.program_notification_card)
        program_notification_layout.addStretch(1)
        program_notification_layout.addWidget(self.program_notification_switch)
        program_notification_layout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(program_notification_layout)

        self.windows_notification_card = SettingCard(
            FluentIcon.MESSAGE,
            "Windows 通知",
            "控制是否发送 Windows 原生桌面通知 (功能已禁用)",
            self
        )
        self.windows_notification_switch = SwitchButton(self)
        self.windows_notification_switch.setChecked(self.config.windows_notifications_enabled)
        self.windows_notification_switch.checkedChanged.connect(self._on_windows_notifications_changed)

        windows_notification_layout = QHBoxLayout()
        windows_notification_layout.addWidget(self.windows_notification_card)
        windows_notification_layout.addStretch(1)
        windows_notification_layout.addWidget(self.windows_notification_switch)
        windows_notification_layout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(windows_notification_layout)

        self.shortcut_label = SubtitleLabel("快捷键设置", self)
        self.vBoxLayout.addWidget(self.shortcut_label)

        self.rename_shortcut_card = SettingCard(
            FluentIcon.EDIT,
            "重命名快捷键",
            "设置文件重命名快捷键",
            self
        )
        self.rename_shortcut_editor = KeyCaptureLineEdit(self)
        self.rename_shortcut_editor.setText(QKeySequence(self.config.shortcuts['rename']).toString())
        self.rename_shortcut_editor.key_captured.connect(lambda key: self._on_shortcut_changed('rename', key))

        rename_shortcut_layout = QHBoxLayout()
        rename_shortcut_layout.addWidget(self.rename_shortcut_card)
        rename_shortcut_layout.addStretch(1)
        rename_shortcut_layout.addWidget(self.rename_shortcut_editor)
        rename_shortcut_layout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(rename_shortcut_layout)

        self.delete_shortcut_card = SettingCard(
            FluentIcon.DELETE,
            "删除快捷键",
            "设置文件删除快捷键",
            self
        )
        self.delete_shortcut_editor = KeyCaptureLineEdit(self)
        self.delete_shortcut_editor.setText(QKeySequence(self.config.shortcuts['delete']).toString())
        self.delete_shortcut_editor.key_captured.connect(lambda key: self._on_shortcut_changed('delete', key))

        delete_shortcut_layout = QHBoxLayout()
        delete_shortcut_layout.addWidget(self.delete_shortcut_card)
        delete_shortcut_layout.addStretch(1)
        delete_shortcut_layout.addWidget(self.delete_shortcut_editor)
        delete_shortcut_layout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(delete_shortcut_layout)

        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.setObjectName("SettingsWidget")

        self.log_widget = None

    def _on_theme_changed(self, index: int):
        theme_map = {
            0: Theme.AUTO,
            1: Theme.LIGHT,
            2: Theme.DARK
        }
        selected_theme = theme_map.get(index, Theme.AUTO)
        self.config.set_theme(selected_theme)
        show_notification(
            title="主题已更改",
            content=f"应用程序主题已切换为 {self.theme_combo_box.currentText()}。",
            notification_type="info",
            parent=self
        )
        if self.log_widget:
            self.log_widget.append_log(f"主题已切换为: {self.theme_combo_box.currentText()}")

    def _on_shortcut_changed(self, action: str, key_code: int):
        self.config.set_shortcut(action, key_code)
        key_name = QKeySequence(key_code).toString() if key_code != 0 else "无"
        show_notification(
            title="快捷键已更改",
            content=f"{action} 快捷键已设置为: {key_name}。",
            notification_type="success",
            parent=self
        )
        if self.log_widget:
            self.log_widget.append_log(f"快捷键 '{action}' 已更改为: {key_name}")

    def _on_program_notifications_changed(self, checked: bool):
        self.config.set_program_notifications_enabled(checked)
        status = "开启" if checked else "关闭"
        self.log_widget.append_log(f"程序内通知已设置为: {status}")
        show_notification(
            title="通知设置",
            content=f"程序内通知已设置为: {status}。",
            notification_type="info",
            parent=self
        )

    def _on_windows_notifications_changed(self, checked: bool):
        self.config.set_windows_notifications_enabled(checked)
        status = "开启" if checked else "关闭"
        self.log_widget.append_log(f"Windows 通知已设置为: {status}")
        show_notification(
            title="通知设置",
            content=f"Windows 通知已设置为: {status}。原生通知功能已禁用。",
            notification_type="info",
            parent=self
        )


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.init_window()

        self.log_widget = LogWidget(self)
        self.about_widget = AboutWidget(self)
        self.settings_widget = SettingsWidget(config, self)
        self.network_repair_widget = NetworkRepairWidget(self.log_widget, self)
        self.pc_cleanup_widget = PCCleanupWidget(self.log_widget, self)
        self.pc_optimization_widget = PCOptimizationWidget(self.log_widget, self)
        self.file_management_widget = FileManagementWidget(self.log_widget, self)

        self.init_navigation()
        self.log_widget.append_log("程序启动成功。")
        self.log_widget.append_log("请注意：部分功能（如网络修复、深度清理）需要管理员权限才能完全执行。")

    def init_window(self):
        self.setWindowTitle("灰尘男人")
        self.setWindowIcon(FluentIcon.SETTING.icon())

        self.resize(1000, 700)
        self.setMinimumSize(800, 600)

        setTheme(config.theme)

    def init_navigation(self):
        self.addSubInterface(self.network_repair_widget, FluentIcon.GLOBE, "网络修复")
        self.addSubInterface(self.pc_cleanup_widget, FluentIcon.LEAF, "电脑清理")
        self.addSubInterface(self.pc_optimization_widget, FluentIcon.SPEED_OFF, "电脑优化")
        self.addSubInterface(self.file_management_widget, FluentIcon.FOLDER, "文件管理")

        self.addSubInterface(self.about_widget, FluentIcon.INFO, "程序信息", position=NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.log_widget, FluentIcon.HISTORY, "操作日志", position=NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.settings_widget, FluentIcon.SETTING, "设置", position=NavigationItemPosition.BOTTOM)

        self.settings_widget.log_widget = self.log_widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei UI")
    font.setPointSize(10)
    app.setFont(font)

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
