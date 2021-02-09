# Sets up the server
import flask
from flask import request, jsonify, send_file
from flask_cors import CORS
# helps connect to sql databases
import random

app = flask.Flask(__name__)
# debug gives us nice error messages when we make mistakes.
app.config["DEBUG"] = True
CORS(app)

# @app.route links a part of the url to a function.
# in this case, the base url will call home()
@app.route('/', methods=['GET'])
def home():
    return '''<h1>Delta Music</h1>
        <p>Generating Music with GANs and MIDI</p>
        <br>
        <br>
        <p>To see it in action, append /v1/test-song-player/ to the current url.</p>'''

# include the v1 or v2 in the url so that you can still have back compat.
@app.route('/v1/test-song-player/')
def generate_audioplayer_page():
    try:
        song_list = ["8-bit.wav", "Hunter_Fav.wav", "piano.wav"]
        song_choice = random.choice(song_list)
        path = "audio\\" + song_choice
        print("asking file", path)
        with open("Audioplayerpt1.txt", "r") as first_half, open("Audioplayerpt2.txt", "r") as second_half:
            return (first_half.read() + f'<audio controls id="myAudio" src="http://127.0.0.1:5000/v1/return-file?path={path}"'
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
######## END MY EXPERIMENTS

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

app.run()