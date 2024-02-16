from inspect import iscoroutinefunction as iscoro, isfunction as isfunc

import discord


async def empty_func(_, __):
    pass


class SelectPaginator(discord.ui.Select):
    def __init__(self):
        super().__init__()
        self.embeds = {}

    def add_paginator_option(self, *, embed: discord.Embed, option: discord.SelectOption):
        self.append_option(option)
        self.embeds[option.value.lower()] = embed

    async def callback(self, interaction):
        view = self.view
        await view.before_press(self, interaction)

        view.update_view()
        await view.edit_embed(interaction, embed=self.embeds[self.values[0].lower()])

        await view.after_press(self, interaction)


class prev_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view

        view.page -= 1
        if view.page < 0:
            view.page = len(view.embeds) - 1

        await view.before_press(self, interaction)

        view.update_view()
        await view.edit_embed(interaction)

        await view.after_press(self, interaction)


class first_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view

        view.page = 0

        await view.before_press(self, interaction)

        view.update_view()
        await view.edit_embed(interaction)

        await view.after_press(self, interaction)


class next_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view

        view.page += 1
        if view.page == len(view.embeds):
            view.page = 0

        await view.before_press(self, interaction)

        view.update_view()
        await view.edit_embed(interaction)

        await view.after_press(self, interaction)


class last_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view

        view.page = len(view.embeds) - 1

        await view.before_press(self, interaction)

        view.update_view()
        await view.edit_embed(interaction)

        await view.after_press(self, interaction)


class delete_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view

        await view.before_press(self, interaction)

        await interaction.message.delete()
        view.stop()

        await view.after_press(self, interaction)


class end_page(discord.ui.Button):
    def __init__(self, label, emoji, style, row):
        super().__init__(label=label, emoji=emoji, style=style, row=row)

    async def callback(self, interaction):
        view = self.view

        await view.before_press(self, interaction)

        for child in view.children:
            child.disabled = True

        await view.edit_embed(interaction)
        view.stop()

        await view.after_press(self, interaction)


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
            num = int(self.page_num.value) - 1

            if num in range(len(view.embeds)):
                view.page = num
            else:
                return await interaction.followup.send(content="Invalid number: aborting", ephemeral=True)

            await view.before_press(self.button, interaction)

            view.update_view()
            await view.edit_embed(interaction)

            await view.after_press(self.button, interaction)
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

        await view.before_press(self, interaction)

        view.clear_items()
        await view.edit_embed(interaction)
        view.stop()

        await view.after_press(self, interaction)


class Paginator(discord.ui.View):
    def __init__(self, bot, embeds, destination, /, *, interactionfailed=None, check=None, timeout=None,
                 before_press=empty_func, after_press=empty_func):
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
        self.message = None
        self.check = check
        self.bot = bot
        self.embeds = embeds
        self.page = 0
        self.destination = destination
        self.interactionfailed = interactionfailed
        self.page_button = None

        self.before_press = before_press
        self.after_press = after_press

    def default_pagination(self):
        self.add_button("first", label='first')
        self.add_button("back", label='back')
        self.add_button("page", label='page')
        self.add_button("next", label='next')
        self.add_button("last", label='last')
        self.add_button("delete", label='Close paginator')

    async def edit_embed(self, interaction: discord.Interaction, *, embed=None):
        current = embed or self.embeds[self.page]
        if isinstance(current, str):
            await interaction.response.edit_message(content=current, embed=None, attachments=[], view=self)
        elif isinstance(current, discord.Embed):
            await interaction.response.edit_message(content=None, embed=current, attachments=[], view=self)
        elif isinstance(current, discord.File):
            await interaction.response.edit_message(content=None, embed=None, attachments=[current], view=self)
        elif isinstance(current, tuple):
            dct = {}
            for item in current:
                if isinstance(item, str):
                    dct["content"] = item
                elif isinstance(item, discord.Embed):
                    dct["embed"] = item
                elif isinstance(item, discord.File):
                    dct["file"] = [item]
            if interaction and not interaction.response.is_done():
                await interaction.response.edit_message(content=dct.get("content", None), embed=dct.get("embed", None),
                                                        attachments=dct.get('file', None), view=self)
            else:
                await self.message.edit(content=dct.get("content", None), embed=dct.get("embed", None),
                                        attachments=dct.get('file', None), view=self)

    async def start(self):
        try:
            current = self.embeds[self.page]
            if isinstance(current, str):
                if isinstance(self.destination, discord.Interaction):
                    await self.destination.response.send_message(content=current, view=self)
                    self.message = await self.destination.original_response()
                else:
                    self.message = await self.destination.send(content=current, view=self)
            elif isinstance(current, discord.Embed):
                if isinstance(self.destination, discord.Interaction):
                    await self.destination.response.send_message(embed=current, view=self)
                    self.message = await self.destination.original_response()
                else:
                    self.message = await self.destination.send(embed=current, view=self)
            elif isinstance(current, discord.File):
                if isinstance(self.destination, discord.Interaction):
                    await self.destination.response.send_message(file=current, view=self)
                    self.message = await self.destination.original_response()
                else:
                    self.message = await self.destination.send(file=current, view=self)
            elif isinstance(current, tuple):
                dct = {}
                for item in current:
                    if isinstance(item, str):
                        dct["content"] = item
                    elif isinstance(item, discord.Embed):
                        dct["embed"] = item
                    elif isinstance(item, discord.File):
                        dct["file"] = item

                if isinstance(self.destination, discord.Interaction):
                    await self.destination.response.send_message(content=dct.get("content", None),
                                                                 embed=dct.get("embed", None),
                                                                 file=dct.get("file", None),
                                                                 view=self)
                    self.message = await self.destination.original_response()
                else:
                    self.message = await self.destination.send(content=dct.get("content", None),
                                                               embed=dct.get("embed", None), file=dct.get("file", None),
                                                               view=self)
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
            self.page_button.label = str(self.page + 1)
        except (NameError, AttributeError):
            pass

    def add_button(self, action, /, *, label="", emoji=None, style=discord.ButtonStyle.grey, row=None):
        action = action.strip().lower()
        if action not in ["first", "prev", "previous", "back", "delete", "next", "last", "end", "page", "show", "goto",
                          "lock"]:
            return
        elif action == "first":
            self.add_item(first_page(label, emoji, style, row))
        elif action in ["back", "prev", "previous"]:
            self.add_item(prev_page(label, emoji, style, row))
        elif action in ["page", "show"]:
            button = show_page("1", emoji, style, row)
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


def embed_creator(text, num, /, *, title='', prefix='', suffix='', color=None, colour=None):
    """A helper function which takes some string and returns a list of embeds"""
    if color != None and colour != None:
        raise ValueError

    return [discord.Embed(title=title, description=prefix + (text[i:i + num]) + suffix,
                          color=color or colour) for i in range(0, len(text), num)]
