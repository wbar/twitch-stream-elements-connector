#!/usr/bin/env python
"""
    This file is part of twitch-stream-elements-connector (TSEC).

    TSEC is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License, or
    (at your option) any later version.

    TSEC is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with TSEC. If not, see <http://www.gnu.org/licenses/>.
"""
import json

import requests
import asyncio
import itertools
from decouple import config
from twitchio import Topic, Context
from twitchio.ext import commands


# noinspection PyPep8Naming
class settings:
    TWITCH_OAUTH_TOKEN = config('TWITCH_OAUTH_TOKEN')
    TWITCH_APP_SECRET = config('TWITCH_APP_SECRET')
    TWITCH_APP_CLIENT_ID = config('TWITCH_APP_CLIENT_ID')
    TWITCH_BOT_NICK = config('TWITCH_BOT_NICK')
    TWITCH_BOT_PREFIX = config('TWITCH_BOT_PREFIX')
    TWITCH_CHANNEL = config('TWITCH_CHANNEL')
    TWITCH_CHANNEL_ID = config('TWITCH_CHANNEL_ID')
    SE_OAUTH2_TOKEN = config('SE_OAUTH2_TOKEN')
    SE_CHANNEL_ID = config('SE_CHANNEL_ID')

    _POINTS_MATRIX = None

    @property
    def POINTS_MATRIX(self):
        if self._POINTS_MATRIX is None:
            lst = config('SE_GIVE_POINTS_MATRIX').split(';')
            assert len(lst) % 2 == 0
            it = iter(lst)
            self._POINTS_MATRIX = dict(
                iter(lambda: tuple(itertools.islice(it, 2)), ())
            )
        return self._POINTS_MATRIX



settings = settings()

bot = commands.Bot(
    # set up the bot
    irc_token=settings.TWITCH_OAUTH_TOKEN,
    client_id=settings.TWITCH_APP_CLIENT_ID,
    nick=settings.TWITCH_BOT_NICK,
    prefix=settings.TWITCH_BOT_PREFIX,
    initial_channels=[settings.TWITCH_CHANNEL]
)


@bot.event
async def event_ready():
    print(f"{settings.TWITCH_BOT_NICK} is online!")
    # noinspection PyProtectedMember
    ws = bot._ws  # this is only needed to send messages within event_ready
    await ws.send_privmsg(settings.TWITCH_CHANNEL, f"/me The twitch connector has landed!")
    await bot.pubsub_subscribe(settings.TWITCH_OAUTH_TOKEN.split(':')[1], f"channel-points-channel-v1.{settings.TWITCH_CHANNEL_ID}")


# noinspection PyUnusedLocal
@bot.event
async def event_raw_pubsub(*args, **kwargs):
    obj = args[0]
    if obj.get('type') != 'MESSAGE':
        print(f"Ignoring wrong type - {obj.get('type')}")
        return
    data = json.loads(obj.get('data').get('message'))
    if data.get('type').lower() != 'reward-redeemed':
        print(f'Wrong type: {data.get("type")} != reward-redeemed')
        return
    user_login = data.get('data').get('redemption').get('user').get('login')
    assert user_login, 'user_login can not be none'
    product_id = data.get('data').get('redemption').get('reward').get('id')
    if product_id not in settings.POINTS_MATRIX:
        print(f'Skipping {product_id} not found in matrix!')
    se_handle_top_up(product_id, user_login)


@bot.event
async def event_message(ctx):
    if not ctx.content.startswith(settings.TWITCH_BOT_PREFIX) or ctx.author.name.lower() != settings.TWITCH_BOT_NICK.lower():
        return
    await bot.handle_commands(ctx)


@bot.command(name='test')
async def test(ctx: Context):
    await ctx.send('Test passed!')


def se_handle_top_up(product_id, username):
    amount = settings.POINTS_MATRIX.get(product_id)
    if amount is None:
        print("Amount is NULL - no mapping found?")
        return

    top_up_url = f"https://api.streamelements.com/kappa/v2/points/{settings.SE_CHANNEL_ID}/{username}/{amount}"
    say_url = f"https://api.streamelements.com/kappa/v2/bot/{settings.SE_CHANNEL_ID}/say"
    token = f"Bearer {settings.SE_OAUTH2_TOKEN}"
    headers = {
        'accept': 'application/json',
        'authorization': token
    }
    response = requests.request(
        "PUT",
        top_up_url,
        headers=headers,
    )
    assert 200 <= response.status_code < 299, response.text
    response = requests.request(
        "POST",
        say_url,
        headers=headers,
        json={"message": f"Otrzymałeś {amount} pepega points."}
    )

    assert 200 <= response.status_code < 299


if __name__ == "__main__":
    bot.run()


