from discord.ext import commands
from discord.utils import get
import spotipy, urllib, re, discord, json, os, asyncio, configparser
from spotipy.oauth2 import SpotifyOAuth
from spotipy import util

client = discord.Client()
bot = commands.Bot(command_prefix='>')
bot.mapping = {}
bot.playlist = {}

config = configparser.ConfigParser()
config.read('config.ini')

def authenticate():
    scope = 'playlist-modify playlist-modify-private'
    token = util.prompt_for_user_token(
        username=config['spotify']['username'],
        scope=scope,
        client_id=config['spotify']['client_id'],
        client_secret=config['spotify']['client_secret'],
        redirect_uri=config['spotify']['redirect_uri']
    )
    return token


def addToPlaylist(authToken, username, playlistName, songName):
    if authToken:
        spotifyObject = spotipy.Spotify(authToken)
        spotifyObject.trace = False
        spotifyObject.user_playlist_add_tracks(username, playlistName, songName)


def lookupSong(authToken, *s):
    s = s[0]
    if authToken:
        song_uri_list = []
        spotifyObject = spotipy.Spotify(authToken)
        spotifyObject.trace = False
        if 'https://open.spotify.com' in s:
            song_uri = re.split('\w+:\/\/\w+.\w+.\w+\/\w+\/(\w+)',s)
            song_uri_list.append(song_uri[1])
        else:
            s_encode = urllib.parse.quote_plus(s)
            ret = spotifyObject.search(s_encode, limit=5)
            ret = ret['tracks']['items']
            if ret == []:
                ret = spotifyObject.search(s_encode, limit=5, market='GB')
                ret = ret['tracks']['items']
            for i in ret:
                song_url = ret[ret.index(i)]['external_urls']['spotify']
                song_uri = re.split('\w+:\/\/\w+.\w+.\w+\/\w+\/(\w+)',song_url)
                song_uri_list.append(song_uri[1])
        return song_uri_list


def createPlaylist(authToken, username, server):
    sp = spotipy.Spotify(auth=authToken)
    sp.user_playlist_create(username, name=str(server))


def setPlaylist(authToken,server,username):
    playlist_id = ''
    sp = spotipy.Spotify(authToken)
    playlists = sp.user_playlists(username)
    for playlist in playlists['items']:
        if playlist['name'] == server:
            playlist_id = playlist['id']
    sp.playlist_change_details(playlist_id,public=False, collaborative=True)
    return playlist_id


def deletePlaylist(authToken, playlist):
    sp = spotipy.Spotify(authToken)
    sp.user_playlist_unfollow(config['spotify']['username'],playlist)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('-----')
    activity = discord.Activity(name="type '>help' for help", type=discord.ActivityType.listening)
    await bot.change_presence(activity=activity)
    if os.path.isfile('playlist.json'):
        j = open('playlist.json', "r")
        bot.playlist = json.load(j)


@bot.command(brief='>resync',description='Forces the bot to resync with the local storage of users and playlists')
async def resync(ctx):
    if os.path.isfile('playlist.json'):
        f = open('playlist.json', "r")
        bot.playlist = json.load(f)


@bot.command(brief='>removePlaylist', description='Removes the currently created playlist')
@commands.has_guild_permissions(administrator=True)
async def removePlaylist(ctx):
    token = authenticate()
    try:
        deletePlaylist(token,bot.playlist[str(ctx.author.guild)])
    except KeyError:
        pass
    try:
        del bot.playlist[str(ctx.author.guild)]
        if os.path.isfile('playlist.json'):
            with open('playlist.json',"w") as outfile:
                json.dump(bot.playlist,outfile)
        await ctx.send('Playlist deleted!')
    except KeyError:
        await ctx.send('This server does not have a playlist')


@bot.command(brief='>playlist',description='Use to specify the playlist that songs should be added to')
@commands.has_guild_permissions(administrator=True)
async def playlist(ctx):
    try:
        bot.playlist[str(ctx.author.guild)]
    except KeyError:
        token = authenticate()
        createPlaylist(token, config['spotify']['username'],str(ctx.author.guild))
        bot.playlist[str(ctx.author.guild)] = setPlaylist(token,str(ctx.author.guild),config['spotify']['username'])
        with open('playlist.json',"w") as outfile:
            json.dump(bot.playlist,outfile)
        await ctx.send('Playlist https://open.spotify.com/playlist/' + bot.playlist[str(ctx.author.guild)]+' has been created!')
        return
    await ctx.send('This server already has a playlist')


@bot.command(brief='>addsong [song_name]',description='Allows a user to add a song to the playlist')
async def addsong(ctx, *song):
    if len(song) > 1:
        song = ' '.join(song)
    else:
        song = song[0]
    def check(m: discord.Message):  # m = discord.Message.
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
        authToken = authenticate()
    except KeyError:
        await ctx.send('You need to connect your account first with `>connect [account name]`')
        return
    uri_list = lookupSong(authToken,song)
    i = 1
    for uri in uri_list:
        await ctx.send(str(i)+': https://open.spotify.com/track/'+uri)
        i+=1
    await ctx.send(f"***Send the number of the song to add to the playlist***")
    try:
        msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout = 60.0)
    except asyncio.TimeoutError:
        # at this point, the check didn't become True, let's handle it.
        await ctx.send(f"**{ctx.author}**, you didn't send any message that meets the check in this channel for 60 seconds..")
        return
    else:
        if int(msg.content) == 1:
            uri = uri_list[0]
        elif int(msg.content) == 2:
            uri = uri_list[1]
        elif int(msg.content) == 3:
            uri = uri_list[2]
        elif int(msg.content) == 4:
            uri = uri_list[3]
        elif int(msg.content) == 5:
            uri = uri_list[4]
    try:
        addToPlaylist(authToken, config['spotify']['username'], bot.playlist[str(ctx.author.guild)], [uri])
    except KeyError:
        await ctx.send('Playlist must be set with `>playlist [spotify_url]`')
        return
    playlist_url = 'https://open.spotify.com/playlist/'+bot.playlist[str(ctx.author.guild)]
    await ctx.send('Playlist '+playlist_url+' has been updated!')


bot.run(config['discord']['bot_token'])
