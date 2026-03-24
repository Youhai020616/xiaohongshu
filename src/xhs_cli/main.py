"""
xhs — 小红书命令行工具主入口。

Usage:
    xhs search "AI创业"                     搜索笔记
    xhs search "美食" --sort 最多点赞        排序搜索
    xhs read 1                              读取搜索结果第 1 条
    xhs detail FEED_ID -t TOKEN             读取指定笔记
    xhs like 1                              点赞第 1 条
    xhs favorite 1                          收藏第 1 条
    xhs comment 1 -c "好文!"                评论第 1 条
    xhs reply 1 --comment-id X --user-id Y -c "回复"
    xhs publish -t "标题" -c "内容" -i 图片  发布笔记
    xhs me                                  我的信息
    xhs profile USER_ID -t TOKEN            用户主页
    xhs feeds                               首页推荐
    xhs analytics                           数据看板
    xhs notifications                       通知消息
    xhs login                               登录
    xhs server start|stop|status            服务管理
    xhs account list|add|remove             多账号
    xhs config show|set|get|reset           配置
"""
from __future__ import annotations

import click

from xhs_cli import __version__

BANNER = f"""
  ╔═══════════════════════════════╗
  ║   📕 xhs-cli v{__version__}        ║
  ║   小红书命令行工具            ║
  ╚═══════════════════════════════╝
"""


class AliasGroup(click.Group):
    """支持命令别名的 Click Group。"""

    ALIASES = {
        "pub": "publish",
        "s": "search",
        "r": "detail",
        "read": "detail",
        "fav": "favorite",
        "noti": "notifications",
        "stat": "status",
        "srv": "server",
        "acc": "account",
        "cfg": "config",
    }

    def get_command(self, ctx, cmd_name):
        resolved = self.ALIASES.get(cmd_name, cmd_name)
        return super().get_command(ctx, resolved)

    def format_help(self, ctx, formatter):
        formatter.write(BANNER)
        super().format_help(ctx, formatter)


@click.group(cls=AliasGroup, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="xhs-cli")
@click.pass_context
def cli(ctx):
    """📕 小红书命令行工具 — 搜索、发布、互动、数据分析"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ------------------------------------------------------------------
# 注册所有命令
# ------------------------------------------------------------------

# 发布
from xhs_cli.commands.publish import publish  # noqa: E402

cli.add_command(publish)

# 搜索 & 详情
from xhs_cli.commands.search import detail, search  # noqa: E402

cli.add_command(search)
cli.add_command(detail)

# 互动
from xhs_cli.commands.interact import comment, favorite, feeds, like, reply  # noqa: E402

cli.add_command(like)
cli.add_command(favorite)
cli.add_command(comment)
cli.add_command(reply)
cli.add_command(feeds)

# 用户
from xhs_cli.commands.profile import me, profile  # noqa: E402

cli.add_command(me)
cli.add_command(profile)

# 数据分析
from xhs_cli.commands.analytics import analytics, notifications  # noqa: E402

cli.add_command(analytics)
cli.add_command(notifications)

# 初始化
from xhs_cli.commands.init import init  # noqa: E402

cli.add_command(init)

# 认证
from xhs_cli.commands.auth import auth_status, login, logout, reset_login  # noqa: E402

cli.add_command(login)
cli.add_command(logout)
cli.add_command(reset_login)
cli.add_command(auth_status, "status")

# 服务管理
from xhs_cli.commands.server import server_group  # noqa: E402

cli.add_command(server_group, "server")

# 账号管理
from xhs_cli.commands.account import account_group  # noqa: E402

cli.add_command(account_group, "account")

# 配置管理
from xhs_cli.commands.config_cmd import config_group  # noqa: E402

cli.add_command(config_group, "config")

# REST API
from xhs_cli.commands.api_cmd import api_group  # noqa: E402

cli.add_command(api_group, "api")


def main():
    cli()


if __name__ == "__main__":
    main()
