# windowmanager/config_handler.py
"""
配置管理 Mixin - 包含 MainWindowTab 的配置管理方法
"""

import logging

logger = logging.getLogger(__name__)


class ConfigHandlerMixin:
    """配置管理 Mixin - 提供配置保存/加载能力"""

    def _load_selected_windows_from_config(self) -> None:
        """从配置中加载选中的窗口（根据进程名 + 标题查找当前句柄）"""
        if not self.config or not self.window_manager:
            return

        target_windows = getattr(self.config, "target_windows", [])
        for window_info in target_windows:
            if isinstance(window_info, dict):
                process_name = window_info.get("process_name", "")
                title = window_info.get("title", "")
                all_windows = self.window_manager.get_all_windows()
                for window in all_windows:
                    if window.process_name == process_name and title in window.title:
                        with self._lock:
                            self._selected_windows.add(window.hwnd)
                        logger.debug(
                            "从配置恢复选中窗口：%d - %s (%s)",
                            window.hwnd, window.title, process_name,
                        )
                        break

    def _save_selected_windows_to_config(self) -> None:
        """保存选中的窗口到配置"""
        if not self.config or not self.config_manager or not self.window_manager:
            return

        target_windows_info = []
        for hwnd in self._selected_windows:
            window = self.window_manager.get_window(hwnd)
            if window:
                target_windows_info.append({
                    "hwnd": hwnd,
                    "process_name": window.process_name,
                    "title": window.title,
                    "state": "visible",
                    "source": "manual",
                })

        self.config.target_windows = target_windows_info
        self.config_manager.save(self.config)

    def _add_window(self, hwnd: int) -> None:
        """添加窗口到选中窗口集合"""
        with self._lock:
            self._selected_windows.add(hwnd)
        self._save_selected_windows_to_config()
        self.refresh_windows()

    def _save_hidden_windows(self) -> None:
        """保存隐藏窗口列表到配置"""
        if not self.config or not self.window_manager:
            return

        target_windows = getattr(self.config, "target_windows", [])
        hidden_window_info = {}

        if hasattr(self.window_manager, "get_software_hidden_windows"):
            hidden_hwnds = self.window_manager.get_software_hidden_windows()
            for hwnd in hidden_hwnds:
                window = self.window_manager.get_window(hwnd)
                if window:
                    key = (window.process_name, window.title)
                    hidden_window_info[key] = {"hwnd": hwnd, "window": window}
        elif hasattr(self.window_manager, "_hidden_windows"):
            for hwnd, window in self.window_manager._hidden_windows.items():
                key = (window.process_name, window.title)
                hidden_window_info[key] = {"hwnd": hwnd, "window": window}

        updated_target_windows = []
        for entry in target_windows:
            if isinstance(entry, dict):
                key = (entry.get("process_name", ""), entry.get("title", ""))
                if key in hidden_window_info:
                    entry["state"] = "hidden"
                    entry["hwnd"] = hidden_window_info[key]["hwnd"]
                    updated_target_windows.append(entry)
                elif entry.get("state") != "hidden":
                    updated_target_windows.append(entry)

        for key, info in hidden_window_info.items():
            process_name, title = key
            exists = any(
                isinstance(entry, dict)
                and entry.get("process_name") == process_name
                and entry.get("title") == title
                for entry in updated_target_windows
            )
            if not exists:
                updated_target_windows.append({
                    "process_name": process_name, "title": title,
                    "hwnd": info["hwnd"], "state": "hidden", "source": "manual",
                })

        self.config.target_windows = updated_target_windows
        if self.config_manager:
            self.config_manager.save(self.config)

    def _save_hidden_columns_config(self) -> None:
        """保存隐藏列配置到config.ui"""
        if not self.config or not self.config_manager:
            return
        hidden_columns = []
        column_names = ["选择", "类型", "标题", "进程", "显示器"]
        header = self.selected_window_table.horizontalHeader()
        for i in range(self.selected_window_table.columnCount()):
            if header.isSectionHidden(i):
                hidden_columns.append(column_names[i])
        self.config.ui["hidden_columns"] = hidden_columns
        self.config_manager.save(self.config)

    def _apply_hidden_columns_from_config(self) -> None:
        """从配置中应用隐藏列状态"""
        if not self.config:
            return
        hidden_columns = self.config.ui.get("hidden_columns", [])
        column_names = ["选择", "类型", "标题", "进程", "显示器"]
        for table in [
            self.selected_window_table,
            self.foreground_window_table,
            self.switch_window_table,
        ]:
            header = table.horizontalHeader()
            for i in range(table.columnCount()):
                if i < len(column_names) and column_names[i] in hidden_columns:
                    header.hideSection(i)
                else:
                    header.showSection(i)
