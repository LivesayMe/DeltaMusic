import spotipy
import spotipy.util as util
import os
import requests
import numpy as np
import pickle
import random
import flask
from flask import request, send_file, jsonify
from flask_cors import CORS

#variable initialization for spotify model
#-----------------------------------------------------------------------------#

lookback = 3       # Number of previous tracks to consider (default 3)
size = 10          #@param {type:"integer"}
creativity = 0.5   #@param {type:"slider", min:0, max:1, step:0.01}
noise = 0          #@param {type:"slider", min:0, max:1, step:0.01}

#@markdown (Optional) If you want to be able to load your playlists into Spotify, you will need to get credentials from [here](https://developer.spotify.com/dashboard/applications)
scope = 'playlist-modify-public'
username = ''      #@param {type: "string"}
playlist_name = '' #@param {type: "string"}
#@markdown (Playlist must already exist. Uncheck the box if you want to extend it.)
replace = True     #@param {type:"boolean"}
client_id ='194086cb37be48ebb45b9ba4ce4c5936'      #@param {type: "string"}
client_secret ='fb9fb4957a9841fcb5b2dbc7804e1e85'  #@param {type: "string"}
redirect_uri ='https://www.attentioncoach.es/'   #@param {type: "string"}

#-----------------------------------------------------------------------------#

#Flask server initialization
#-----------------------------------------------------------------------------#

app = flask.Flask(__name__)
app.config["DEBUG"] = True
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return send_file("index.html")

@app.route('/files', methods=['GET'])
def getFile():
    return send_file(request.args['file'])

@app.route('/song', methods=['GET'])
def requestSongs():
    global mp3tovecs, tracktovecs, tracks, track_ids
    user_input = request.args['song']
    ids = sorted([track for track in mp3tovecs
                      if all(word in tracks[track].lower()
                             for word in user_input.lower().split())],
                     key = lambda x: tracks[x])
    return jsonify({"ids": ids, 'tracks': [tracks[i] for i in ids]})  

@app.route('/playlist', methods=['GET'])
def requestSimilarPlaylist():
    global mp3tovecs, tracktovecs, tracks, track_ids    
    return jsonify({"html": make_playlist(None, '', None, [mp3tovecs, tracktovecs], \
                                 [creativity, 1-creativity], [request.args['song']], tracks, track_ids, \
                                 size=size, lookback=lookback, noise=noise, replace=replace)})

# Music Player Stuff
@app.route('/v1/test-song-player/')
def generate_audioplayer_page():
    try:
        song_list = ["response.wav", "Hunter_Fav.wav", "piano.wav"]
        song_choice = "response.wav"#random.choice(song_list)
        path = "audio\\" + song_choice
        print("asking file", path)
        with open("Audioplayerpt1.txt", "r") as first_half, open("Audioplayerpt2.txt", "r") as second_half:
            return (first_half.read() + f'<audio controls id="myAudio" src="http://localhost:5000/v1/return-file?path={path}"'
            + f' crossorigin="anonymous" autoplay></audio><p id="currentSong">{song_choice}' + second_half.read())
    except Exception as e:
        return str(e)

@app.route('/v1/return-file', methods=['GET'])
def return_files():
    # request.args is all the &__=__&**=__&^^=__
    query_parameters = request.args
    path = query_parameters.get('path')
    print("returning file", path)
    try:
        return send_file(path)
    except Exception as e:
        return str(e)

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404
#-----------------------------------------------------------------------------#



def download_file_from_google_drive(id, destination):
    if os.path.isfile(destination):
        return None
    print(f'Downloading {destination}')
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params = { 'id' : id }, stream = True)
    token = get_confirm_token(response)
    if token:
        params = { 'id' : id, 'confirm' : token }
        response = session.get(URL, params = params, stream = True)
    save_response_content(response, destination)    

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None

def save_response_content(response, destination):
    CHUNK_SIZE = 32768
    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)

def most_similar(mp3tovecs, weights, positive=[], negative=[], noise=0):
    if isinstance(positive, str):
        positive = [positive] # broadcast to list
    if isinstance(negative, str):
        negative = [negative] # broadcast to list
    similar = np.zeros((len(mp3tovecs[0]), 2, len(weights)), dtype=np.float64)
    for k, mp3tovec in enumerate(mp3tovecs):
        mp3_vec_i = np.sum([mp3tovec[i] for i in positive] +
                           [-mp3tovec[i] for i in negative], axis=0)
        mp3_vec_i += np.random.normal(0, noise, len(mp3_vec_i))
        mp3_vec_i = mp3_vec_i / np.linalg.norm(mp3_vec_i)
        for j, track_j in enumerate(mp3tovec):
            if track_j in positive or track_j in negative:
                continue
            mp3_vec_j = mp3tovec[track_j]
            similar[j, 0, k] = j
            similar[j, 1, k] = np.dot(mp3_vec_i, mp3_vec_j)
    return sorted(similar, key=lambda x:-np.dot(x[1], weights))    

def most_similar_by_vec(mp3tovecs, weights, positives=None, negatives=None, noise=0):
    similar = np.zeros((len(mp3tovecs[0]), 2, len(weights)), dtype=np.float64)
    positive = negative = []
    for k, mp3tovec in enumerate(mp3tovecs):
        if positives is not None:
            positive = positives[k]
        if negatives is not None:
            negative = negatives[k]
        if isinstance(positive, str):
            positive = [positive] # broadcast to list
        if isinstance(negative, str):
            negative = [negative] # broadcast to list
        mp3_vec_i = np.sum([i for i in positive] + [-i for i in negative], axis=0)
        mp3_vec_i += np.random.normal(0, noise, len(mp3_vec_i))
        mp3_vec_i = mp3_vec_i / np.linalg.norm(mp3_vec_i)
        for j, track_j in enumerate(mp3tovec):
            mp3_vec_j = mp3tovec[track_j]
            similar[j, 0, k] = j
            similar[j, 1, k] = np.dot(mp3_vec_i, mp3_vec_j)
    return sorted(similar, key=lambda x:-np.dot(x[1], weights))

def add_track_to_playlist(sp, username, playlist_id, track_id, replace=False):
    if sp is not None and username is not None and playlist_id is not None:
        try:
            if replace:
                sp.user_playlist_replace_tracks(username, playlist_id, [track_id])
            else:
                sp.user_playlist_add_tracks(username, playlist_id, [track_id])
        except spotipy.client.SpotifyException:
            # token has probably gone stale
            token = util.prompt_for_user_token(username, scope, client_id, client_secret, redirect_uri)
            sp = spotipy.Spotify(token)
            if replace:
                sp.user_playlist_replace_tracks(username, playlist_id, [track_id])
            else:
                sp.user_playlist_add_tracks(username, playlist_id, [track_id])

def make_playlist(sp, username, playlist_id, mp3tovecs, weights, seed_tracks, \
                  tracks, track_ids, size=10, lookback=3, noise=0, replace=True):
    playlist = seed_tracks
    playlist_tracks = [tracks[_] for _ in playlist]
    html_playlist = []
    print("Generating playlist")
    for i in range(0, len(seed_tracks)):
        add_track_to_playlist(sp, username, playlist_id, playlist[i], replace and len(playlist) == 1)
        html_playlist.append((f'<iframe src="https://open.spotify.com/embed/track/{playlist[i]}" \
                     width="100%" height="80" frameborder="0" allowtransparency="true" \
                     allow="encrypted-media"></iframe>'))
    for i in range(len(seed_tracks), size):
        candidates = most_similar(mp3tovecs, weights, positive=playlist[-lookback:], noise=noise)
        for candidate in candidates:
            track_id = track_ids[int(candidate[0][0])]
            if track_id not in playlist and tracks[track_id] not in playlist_tracks:
                break
        playlist.append(track_id)
        playlist_tracks.append(tracks[track_id])
        add_track_to_playlist(sp, username, playlist_id, playlist[-1])
        html_playlist.append((f'<iframe src="https://open.spotify.com/embed/track/{playlist[-1]}" \
                     width="100%" height="80" frameborder="0" allowtransparency="true" \
                     allow="encrypted-media"></iframe>'))
    #for i in html_playlist:
    #    print(i)
    return html_playlist

# create a musical journey between given track "waypoints"
def join_the_dots(sp, username, playlist_id, mp3tovecs, weights, ids, \
                  tracks, track_ids, n=5, noise=0, replace=True):
    playlist = []
    playlist_tracks = [tracks[_] for _ in ids]
    end = start = ids[0]
    start_vec = [mp3tovec[start] for k, mp3tovec in enumerate(mp3tovecs)]
    html_playlist = []
    for end in ids[1:]:
        end_vec = [mp3tovec[end] for k, mp3tovec in enumerate(mp3tovecs)]
        playlist.append(start)
        add_track_to_playlist(sp, username, playlist_id, playlist[-1], replace and len(playlist) == 1)
        html_playlist.append((f'<iframe src="https://open.spotify.com/embed/track/{playlist[-1]}" \
                     width="100%" height="80" frameborder="0" allowtransparency="true" \
                     allow="encrypted-media"></iframe>'))
        for i in range(n):
            candidates = most_similar_by_vec(mp3tovecs, weights,
                                             [[(n-i+1)/n * start_vec[k] +
                                               (i+1)/n * end_vec[k]]
                                              for k in range(len(mp3tovecs))],
                                             noise=noise)
            for candidate in candidates:
                track_id = track_ids[int(candidate[0][0])]
                if track_id not in playlist + ids and tracks[track_id] not in playlist_tracks:
                    break
            playlist.append(track_id)
            playlist_tracks.append(tracks[track_id])
            add_track_to_playlist(sp, username, playlist_id, playlist[-1])
            html_playlist.append((f'<iframe src="https://open.spotify.com/embed/track/{playlist[-1]}" \
                         width="100%" height="80" frameborder="0" allowtransparency="true" \
                         allow="encrypted-media"></iframe>'))
        start = end
        start_vec = end_vec
    playlist.append(end)
    add_track_to_playlist(sp, username, playlist_id, playlist[-1])
    html_playlist.append((f'<iframe src="https://open.spotify.com/embed/track/{playlist[-1]}" \
                 width="100%" height="80" frameborder="0" allowtransparency="true" \
                 allow="encrypted-media"></iframe>'))
    return playlist

def spotify():
    sp = playlist_id = None
    if username !='' and playlist_name != '':
        if client_id == '':
            print(('Get your Spotify Credentials <a href="https://developer.spotify.com\
                         /dashboard/applications">here</a> and fill in the form...'))
            print(('...or simply leave the username empty'))
            return None
        token = util.prompt_for_user_token(username, scope, client_id, client_secret, redirect_uri)
        if token is not None:
            sp = spotipy.Spotify(token)
            if sp is not None:
                playlists = sp.user_playlists(username)
                if playlists is not None:
                    playlist_ids = [playlist['id'] for playlist in playlists['items'] \
                                    if playlist['name'] == playlist_name]
                    if len(playlist_ids) > 0:
                        playlist_id = playlist_ids[0]
        if playlist_id is None:
            print(f'Unable to access playlist {playlist_name} for user {username}')
        else:
            print(f'Creating playlist {playlist_name} for user {username}')
    mp3tovecs = pickle.load(open('spotifytovec.p', 'rb'))
    mp3tovecs = dict(zip(mp3tovecs.keys(), [mp3tovecs[_] / np.linalg.norm(mp3tovecs[_]) for _ in mp3tovecs]))
    tracktovecs = pickle.load(open('tracktovec.p', 'rb'))
    tracktovecs = dict(zip(tracktovecs.keys(), [tracktovecs[_] / np.linalg.norm(tracktovecs[_]) for _ in tracktovecs]))
    tracks = pickle.load(open('spotify_tracks.p', 'rb'))
    track_ids = [_ for _ in mp3tovecs]
    print(f'Loaded data for {len(mp3tovecs)} Spotify tracks')
    user_input = input('Search keywords: ')
    input_tracks = []
    while True:
        if user_input == '':
            break
        ids = sorted([track for track in mp3tovecs
                      if all(word in tracks[track].lower()
                             for word in user_input.lower().split())],
                     key = lambda x: tracks[x])
        for i, id in enumerate(ids):
            print(f'{i+1}. {tracks[id]}')
        while True:
            user_input = input('Input track number, ENTER to finish, or search keywords: ')
            if user_input == '':
                break
            if user_input.isdigit() and len(ids) > 0:
                if int(user_input)-1 >= len(ids):
                    continue
                id = ids[int(user_input)-1]
                input_tracks.append(id)
                print(f'Added {tracks[id]} to playlist')
            else:
                break
    if len(input_tracks) == 0:
        ids = [track for track in tracks]
        input_tracks.append(ids[random.randint(0, len(tracks))])
    if len(input_tracks) > 1:
        print((f'<h2>Joining the dots (creativity = {creativity})</h2>'))
        playlist = join_the_dots(sp, username, playlist_id, [mp3tovecs, tracktovecs], \
                                 [creativity, 1-creativity], input_tracks, tracks, track_ids, \
                                  n=size, noise=noise, replace=replace)
    else:
        print((f'<h2>Playlist (creativity = {creativity})</h2>'))
        playlist = make_playlist(sp, username, playlist_id, [mp3tovecs, tracktovecs], \
                                 [creativity, 1-creativity], input_tracks, tracks, track_ids, \
                                 size=size, lookback=lookback, noise=noise, replace=replace)
    return playlist



def init_spotify():
    global mp3tovecs, tracktovecs, tracks, track_ids
    mp3tovecs = pickle.load(open('spotifytovec.p', 'rb'))
    mp3tovecs = dict(zip(mp3tovecs.keys(), [mp3tovecs[_] / np.linalg.norm(mp3tovecs[_]) for _ in mp3tovecs]))
    tracktovecs = pickle.load(open('tracktovec.p', 'rb'))
    tracktovecs = dict(zip(tracktovecs.keys(), [tracktovecs[_] / np.linalg.norm(tracktovecs[_]) for _ in tracktovecs]))
    tracks = pickle.load(open('spotify_tracks.p', 'rb'))
    track_ids = [_ for _ in mp3tovecs]

if __name__ == "__main__":
    download_file_from_google_drive('1Mg924qqF3iDgVW5w34m6Zaki5fNBdfSy', 'spotifytovec.p')
    download_file_from_google_drive('1geEALPQTRBNUvkpI08B-oN4vsIiDTb5I', 'tracktovec.p')
    download_file_from_google_drive('1Qre4Lkym1n5UTpAveNl5ffxlaAmH1ntS', 'spotify_tracks.p')
    
    #track_details = spotify()
    init_spotify()
    app.run()