
from asyncio import CancelledError, run
from threading import Event, Thread
from time import sleep

from httpx import RequestError, get

from src.config import Parameter, Settings
from src.custom import (
    COOKIE_UPDATE_INTERVAL,
    DISCLAIMER_TEXT,
    DOCUMENTATION_URL,
    LICENCE,
    MASTER,
    PROJECT_NAME,
    PROJECT_ROOT,
    RELEASES,
    REPOSITORY,
    SERVER_HOST,
    SERVER_PORT,
    TEXT_REPLACEMENT,
    VERSION_BETA,
    VERSION_MAJOR,
    VERSION_MINOR,
)
from src.manager import Database, DownloadRecorder
from src.module import Cookie, MigrateFolder
from src.record import BaseLogger, LoggerManager
from src.tools import (
    Browser,
    ColorfulConsole,
    DownloaderError,
    RenameCompatible,
    choose,
    remove_empty_directories,
    safe_pop,
)
from src.translation import _, switch_language

from .main_monitor import ClipboardMonitor
from .main_server import APIServer
from .main_terminal import TikTok

# from typing import Type
# from webbrowser import open

__all__ = ["TikTokDownloader"]


class TikTokDownloader:
    """
    抖音/TikTok 下载器主类
    
    用于管理整个下载器的功能模块，包括配置加载、用户界面、下载任务调度等。
    """

    VERSION_MAJOR = VERSION_MAJOR
    VERSION_MINOR = VERSION_MINOR
    VERSION_BETA = VERSION_BETA
    NAME = PROJECT_NAME
    WIDTH = 50
    LINE = ">" * WIDTH

    def __init__(
            self,
    ):
        """
        初始化 TikTokDownloader 实例
        
        设置兼容性重命名、控制台输出对象、日志记录器、数据库连接、配置参数等核心组件。
        """
        self.rename_compatible()
        self.console = ColorfulConsole(
            debug=self.VERSION_BETA,
        )
        self.logger = None
        self.recorder = None
        self.settings = Settings(PROJECT_ROOT, self.console)
        self.event_cookie = Event()
        self.cookie = Cookie(self.settings, self.console)
        self.params_task = None
        self.parameter = None
        self.running = True
        self.run_command = None
        self.database = Database()
        self.config = None
        self.option = None
        self.__function_menu = None

    @staticmethod
    def rename_compatible():
        """
        执行文件迁移以确保向后兼容性
        
        调用 RenameCompatible 类的方法来处理旧版本文件结构的迁移问题。
        """
        RenameCompatible.migration_file()

    async def read_config(self):
        """
        异步读取配置数据并格式化
        
        从数据库中读取配置和选项数据，并将其转换为字典形式存储在实例变量中。
        同时根据语言选项设置当前的语言环境。
        """
        self.config = self.__format_config(await self.database.read_config_data())
        self.option = self.__format_config(await self.database.read_option_data())
        self.set_language(self.option["Language"])

    @staticmethod
    def __format_config(config: list) -> dict:
        """
        将配置列表格式化为字典
        
        参数:
            config (list): 包含配置项的列表，每个元素是一个包含 'NAME' 和 'VALUE' 键的字典
            
        返回:
            dict: 格式化后的配置字典，键为配置名称，值为对应的配置值
        """
        return {i["NAME"]: i["VALUE"] for i in config}

    @staticmethod
    def set_language(language: str) -> None:
        """
        设置程序使用的语言
        
        参数:
            language (str): 目标语言代码（如 'zh_CN', 'en_US'）
        """
        switch_language(language)

    async def __aenter__(self):
        """
        异步上下文管理入口方法
        
        进入异步上下文时自动打开数据库连接并读取配置信息。
        
        返回:
            TikTokDownloader: 当前实例
        """
        await self.database.__aenter__()
        await self.read_config()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理退出方法
        
        退出异步上下文时自动关闭数据库连接及相关的客户端资源。
        
        参数:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪信息
        """
        await self.database.__aexit__(exc_type, exc_val, exc_tb)
        if self.parameter:
            await self.parameter.close_client()
            self.close()

    def __update_menu(self):
        """
        更新功能菜单选项
        
        构建一个包含所有可用功能及其对应回调函数的元组列表，供主菜单显示使用。
        """
        options = {
            1: _("禁用"),
            0: _("启用"),
        }
        self.__function_menu = (
            (_("从剪贴板读取 Cookie (抖音)"), self.write_cookie),
            (_("从浏览器读取 Cookie (抖音)"), self.browser_cookie),
            # (_("扫码登录获取 Cookie (抖音)"), self.auto_cookie),
            (_("从剪贴板读取 Cookie (TikTok)"), self.write_cookie_tiktok),
            (_("从浏览器读取 Cookie (TikTok)"), self.browser_cookie_tiktok),
            (_("终端交互模式"), self.complete),
            (_("后台监听模式"), self.monitor),
            (_("Web API 模式"), self.server),
            (_("Web UI 模式"), self.disable_function),
            # (_("Web API 模式"), self.__api_object),
            # (_("Web UI 模式"), self.__web_ui_object),
            (
                _("{}作品下载记录").format(options[self.config["Record"]]),
                self.__modify_record,
            ),
            (_("删除作品下载记录"), self.delete_works_ids),
            (
                _("{}运行日志记录").format(options[self.config["Logger"]]),
                self.__modify_logging,
            ),
            (_("检查程序版本更新"), self.check_update),
            (_("切换语言"), self._switch_language),
        )

    async def disable_function(
            self,
            *args,
            **kwargs,
    ):
        """
        禁用某个功能的占位符方法
        
        当某项功能尚未实现或被临时禁用时调用此方法提示用户。
        """
        self.console.warning(
            "该功能正在重构，未来开发完成重新开放！",
        )

    async def server(self):
        """
        启动 Web API 服务
        
        创建并启动基于 FastAPI 的 RESTful 接口服务器，提供对外的服务接口。
        """
        try:
            self.console.print(
                _(
                    "访问 http://127.0.0.1:5555/docs 或者 http://127.0.0.1:5555/redoc 可以查阅 API 模式说明文档！"
                ),
                highlight=True,
            )
            await APIServer(
                self.parameter,
                self.database,
            ).run_server(
                SERVER_HOST,
                SERVER_PORT,
            )
        except KeyboardInterrupt:
            self.running = False

    async def __modify_record(self):
        """
        修改作品下载记录状态
        
        切换是否启用作品下载记录功能的状态。
        """
        await self.change_config("Record")

    async def __modify_logging(self):
        """
        修改运行日志记录状态
        
        切换是否启用运行日志记录功能的状态。
        """
        await self.change_config("Logger")

    async def _switch_language(
            self,
    ):
        """
        切换程序语言
        
        在简体中文与英文之间进行语言切换。
        """
        if self.option["Language"] == "zh_CN":
            language = "en_US"
        elif self.option["Language"] == "en_US":
            language = "zh_CN"
        else:
            raise DownloaderError
        await self._update_language(language)

    async def _update_language(self, language: str) -> None:
        """
        更新语言设置
        
        参数:
            language (str): 新的语言代码
        """
        self.option["Language"] = language
        await self.database.update_option_data("Language", language)
        self.set_language(language)

    async def disclaimer(self):
        """
        显示免责声明并要求用户确认
        
        首次运行时展示免责声明文本，并等待用户的同意确认。
        
        返回:
            bool: 用户是否同意免责声明
        """
        if not self.config["Disclaimer"]:
            await self.__init_language()
            self.console.print(_(DISCLAIMER_TEXT), style=MASTER)
            if self.console.input(
                    _("是否已仔细阅读上述免责声明(YES/NO): ")
            ).upper() not in ("Y", "YES"):
                return False
            await self.database.update_config_data("Disclaimer", 1)
            self.console.print()
        return True

    async def __init_language(self):
        """
      初始化语言选择

      首次运行默认使用简体中文，无需用户选择
      """
        # 默认设置为简体中文，无需用户选择
        language = "zh_CN"
        await self._update_language(language)
        # """
        # 初始化语言选择
        #
        # 提供给首次运行的用户选择默认语言的交互流程。
        # """
        # languages = (
        #     (
        #         "简体中文",
        #         "zh_CN",
        #     ),
        #     (
        #         "English",
        #         "en_US",
        #     ),
        # )
        # language = choose(
        #     "请选择语言(Please Select Language)",
        #     [i[0] for i in languages],
        #     self.console,
        # )
        # try:
        #     language = languages[int(language) - 1][1]
        #     await self._update_language(language)
        # except ValueError:
        #     await self.__init_language()

    def project_info(self):
        """
        显示项目基本信息
        
        输出项目的名称、仓库地址、文档链接以及开源许可证等基础信息。
        """
        self.console.print(
            f"{self.LINE}\n\n\n{self.NAME.center(self.WIDTH)}\n\n\n{self.LINE}\n",
            style=MASTER,
        )
        self.console.print(_("项目地址: {}").format(REPOSITORY), style=MASTER)
        self.console.print(_("项目文档: {}").format(DOCUMENTATION_URL), style=MASTER)
        self.console.print(_("开源许可: {}\n").format(LICENCE), style=MASTER)

    def check_config(self):
        """
        检查并初始化配置相关组件
        
        根据配置决定是否启用下载记录和日志记录功能。
        """
        self.recorder = DownloadRecorder(
            self.database,
            self.config["Record"],
            self.console,
        )
        self.logger = {1: LoggerManager, 0: BaseLogger}[self.config["Logger"]]

    async def check_update(self):
        """
        检查是否有新的程序版本发布
        
        发起网络请求查询 GitHub 上最新的 Release 版本号并与本地版本比较。
        """
        try:
            response = get(
                RELEASES,
                timeout=5,
                follow_redirects=True,
            )
            latest_major, latest_minor = map(
                int, str(response.url).split("/")[-1].split(".", 1)
            )
            if latest_major > self.VERSION_MAJOR or latest_minor > self.VERSION_MINOR:
                self.console.warning(
                    _("检测到新版本: {major}.{minor}").format(
                        major=latest_major, minor=latest_minor
                    ),
                )
                self.console.print(RELEASES)
            elif latest_minor == self.VERSION_MINOR and self.VERSION_BETA:
                self.console.warning(
                    _("当前版本为开发版, 可更新至正式版"),
                )
                self.console.print(RELEASES)
            elif self.VERSION_BETA:
                self.console.warning(
                    _("当前已是最新开发版"),
                )
            else:
                self.console.info(
                    _("当前已是最新正式版"),
                )
        except RequestError:
            self.console.error(
                _("检测新版本失败"),
            )

    async def main_menu(
            self,
            mode=None,
    ):
        """
        主菜单循环
        
        展示功能菜单并根据用户输入执行相应的功能。
        
        参数:
            mode (str, optional): 默认选中的菜单项编号，默认为 None 表示由用户手动选择
        """
        """选择功能模式"""
        while self.running:
            self.__update_menu()
            if not mode:
                mode = choose(
                    _("DouK-Downloader 功能选项"),
                    [i for i, __ in self.__function_menu],
                    self.console,
                    separate=(
                        4,
                        8,
                    ),
                )
            await self.compatible(mode)
            mode = None

    async def complete(self):
        """
        终端交互模式
        
        启动命令行交互式的下载流程。
        """
        """终端交互模式"""
        example = TikTok(
            self.parameter,
            self.database,
        )
        try:
            await example.run(self.run_command)
            self.running = example.running
        except KeyboardInterrupt:
            self.running = False

    async def monitor(self):
        """
        后台监听模式
        
        启动剪贴板监控模式，持续监听剪贴板中的链接变化。
        """
        await self.monitor_clipboard()

    async def monitor_clipboard(self):
        """
        剪贴板监控逻辑
        
        使用 ClipboardMonitor 类监听剪贴板内容的变化并触发相应动作。
        """
        example = ClipboardMonitor(
            self.parameter,
            self.database,
        )
        try:
            await example.run(self.run_command)
        except (KeyboardInterrupt, CancelledError):
            await example.stop_listener()

    async def change_config(
            self,
            key: str,
    ):
        """
        更改配置项状态
        
        参数:
            key (str): 要更改的配置项名称（例如 "Record" 或 "Logger"）
        """
        self.config[key] = 0 if self.config[key] else 1
        await self.database.update_config_data(key, self.config[key])
        self.console.print(_("修改设置成功！"))
        self.check_config()
        await self.check_settings()

    async def write_cookie(self):
        """
        从剪贴板写入抖音 Cookie
        
        引导用户将抖音平台的 Cookie 复制到剪贴板后导入系统。
        """
        await self.__write_cookie(False)

    async def write_cookie_tiktok(self):
        """
        从剪贴板写入 TikTok Cookie
        
        引导用户将 TikTok 平台的 Cookie 复制到剪贴板后导入系统。
        """
        await self.__write_cookie(True)

    async def __write_cookie(self, tiktok: bool):
        """
        写入 Cookie 的通用方法
        
        参数:
            tiktok (bool): 是否是 TikTok 平台的 Cookie
        """
        self.console.print(
            _("Cookie 获取教程：")
            + "https://github.com/JoeanAmier/TikTokDownloader/blob/master/docs/Cookie%E8%8E%B7%E5%8F%96%E6"
              "%95%99%E7%A8%8B.md"
        )
        if self.console.input(
                _(
                    "复制 Cookie 内容至剪贴板后，按回车键确认继续；若输入任意内容并按回车，则取消操作："
                )
        ):
            return
        if self.cookie.run(tiktok):
            await self.check_settings()

    # async def auto_cookie(self):
    #     self.console.error(
    #         _(
    #             "该功能为实验性功能，仅适用于学习和研究目的；目前仅支持抖音平台，建议使用其他方式获取 Cookie，未来可能会禁用或移除该功能！"
    #         ),
    #     )
    #     if self.console.input(_("是否返回上一级菜单(YES/NO)")).upper() != "NO":
    #         return
    #     if cookie := await Register(
    #         self.parameter,
    #         self.settings,
    #     ).run():
    #         self.cookie.extract(cookie, platform=_("抖音"))
    #         await self.check_settings()
    #     else:
    #         self.console.warning(
    #             _("扫码登录失败，未写入 Cookie！"),
    #         )

    async def compatible(self, mode: str):
        """
        兼容不同输入模式的选择处理
        
        参数:
            mode (str): 用户输入的菜单选项字符串
        """
        if mode in {"Q", "q", ""}:
            self.running = False
        try:
            n = int(mode) - 1
        except ValueError:
            return
        if n in range(len(self.__function_menu)):
            await self.__function_menu[n][1]()

    async def delete_works_ids(self):
        """
        删除指定的作品下载记录
        
        允许用户通过输入作品 ID 来清除其下载历史记录。
        """
        if not self.config["Record"]:
            self.console.warning(
                _("作品下载记录功能已禁用！"),
            )
            return
        await self.recorder.delete_ids(self.console.input("请输入需要删除的作品 ID："))
        self.console.info(
            "删除作品下载记录成功！",
        )

    async def check_settings(self, restart=True):
        """
        检查并应用配置变更
        
        参数:
            restart (bool): 是否重启周期性任务，默认为 True
        """
        if restart:
            await self.parameter.close_client()
        self.parameter = Parameter(
            self.settings,
            self.cookie,
            logger=self.logger,
            console=self.console,
            **self.settings.read(),
            recorder=self.recorder,
        )
        MigrateFolder(self.parameter).compatible()
        self.parameter.set_headers_cookie()
        self.restart_cycle_task(
            restart,
        )
        # await self.parameter.update_params_offline()
        if not restart:
            self.run_command = self.parameter.run_command.copy()
        self.parameter.CLEANER.set_rule(TEXT_REPLACEMENT, True)

    async def run(self):
        """
        程序主运行入口
        
        完成初始化工作后进入主菜单循环。
        """
        self.project_info()
        self.check_config()
        await self.check_settings(
            False,
        )
        # if await self.disclaimer():
            # await self.main_menu(safe_pop(self.run_command))
        await self.server()

    def periodic_update_params(self):
        """
        周期性更新参数的任务
        
        在独立线程中定期刷新参数信息。
        """

        async def inner():
            while not self.event_cookie.is_set():
                await self.parameter.update_params()
                self.event_cookie.wait(COOKIE_UPDATE_INTERVAL)

        run(
            inner(),
        )

    def restart_cycle_task(
            self,
            restart=True,
    ):
        """
        重启周期性任务
        
        参数:
            restart (bool): 是否先停止当前任务再重启，默认为 True
        """
        if restart:
            self.event_cookie.set()
            while self.params_task.is_alive():
                # print("等待子线程结束！")  # 调试代码
                sleep(1)
        self.params_task = Thread(target=self.periodic_update_params)
        self.event_cookie.clear()
        self.params_task.start()

    def close(self):
        """
        关闭程序前清理资源
        
        结束所有后台任务并清理空目录。
        """
        self.event_cookie.set()
        if self.parameter.folder_mode:
            remove_empty_directories(self.parameter.ROOT)
            remove_empty_directories(self.parameter.root)
        self.parameter.logger.info(_("正在关闭程序"))

    async def browser_cookie(
            self,
    ):
        """
        从浏览器读取抖音 Cookie
        
        利用浏览器自动化工具提取抖音平台的 Cookie。
        """
        if Browser(self.parameter, self.cookie).run(
                select=safe_pop(self.run_command),
        ):
            await self.check_settings()

    async def browser_cookie_tiktok(
            self,
    ):
        """
        从浏览器读取 TikTok Cookie
        
        利用浏览器自动化工具提取 TikTok 平台的 Cookie。
        """
        if Browser(self.parameter, self.cookie).run(
                True,
                select=safe_pop(self.run_command),
        ):
            await self.check_settings()