import settings
import discord
from discord.ext import commands
import random

logger = settings.logging.getLogger("bot")


class Slapper(commands.Converter):
    def __init__(self, *, use_nicknames):
        self.use_nicknames = use_nicknames

    async def convert(self, ctx, argument):
        someone = random.choice(ctx.guild.members)

        nickname = ctx.author
        if self.use_nicknames:
            nickname = ctx.author.nick
            nickname = "hi"
        return f"{nickname} slaps {someone} with {argument}"


def run():
    intents = discord.Intents.default()
    intents.message_content = True  # Allows talking to bot

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print("Bot Online!")
        logger.info(f"User: {bot.user} id: {bot.user.id}")
        print("______________")

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"ERROR: {error}")

    @bot.command(
        aliases=["p"],
        help="This is help",
        despription="This is description",
        brief="This is brief",
    )
    async def ping(ctx) -> str:
        """Answer with pong"""
        await ctx.send("Denar")

    @bot.command()
    async def joined(ctx, who: discord.Member) -> str:
        """Answer with pong"""
        await ctx.send(who.joined_at)

    @bot.command()
    async def slap(ctx, reason: Slapper(use_nicknames=True)) -> str:
        """Answer with pong"""
        await ctx.send(reason)

    bot.run(settings.DISCORD_API_SECRET, root_logger=True)


if __name__ == "__main__":
    run()
