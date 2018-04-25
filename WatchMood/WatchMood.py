from flask import Flask
from flask import g, session, request, url_for, flash
from flask import redirect, render_template
from flask_oauthlib.client import OAuth
from justwatch import JustWatch
from watson_developer_cloud import ToneAnalyzerV3
from random import randint

# NEW to connect to mySQL
from flaskext.mysql import MySQL
#import json

app = Flask(__name__)
app.debug = True
app.secret_key = 'development'

# NEW mysql set up
mysql = MySQL()
# NEW
app.config['MYSQL_DATABASE_USER'] = 'root'
# NOTE MUST INSERT YOUR OWN PASSWORD
app.config['MYSQL_DATABASE_PASSWORD'] = 'Insert your Password'
app.config['MYSQL_DATABASE_DB'] = 'WatchMood'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)

oauth = OAuth(app)

##testing connection to WatchMoodDB
#conn = mysql.connect()
#cursor = conn.cursor()
#query = "SELECT * FROM Mood"
#cursor.execute(query)
#Moods = cursor.fetchall()
#print(Moods)

twitter = oauth.remote_app(
    'twitter',
    consumer_key='kRSXMH3EyQDo06EDjYtJ12KON',
    consumer_secret='msxut84GDA7jLsjLi0uVIYngxVZajTJZYcof8OvdnziscMG7rB',
    base_url='https://api.twitter.com/1.1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authorize'
)

tone_analyzer = ToneAnalyzerV3(
    username='f43730c8-0ff6-41e2-b93b-189e49f4f6e0',
    password='Q8i3qtpa1WwO',
    version='2017-09-26')

@twitter.tokengetter
def get_twitter_token():
    if 'twitter_oauth' in session:
        resp = session['twitter_oauth']
        return resp['oauth_token'], resp['oauth_token_secret']


@app.before_request
def before_request():
    g.user = None
    if 'twitter_oauth' in session:
        g.user = session['twitter_oauth']


@app.route('/')
def index():
    tweets = None
    if g.user is not None:
        resp = twitter.request('statuses/home_timeline.json')
        if resp.status == 200:
            tweets = resp.data
        else:
            flash('Unable to load tweets from Twitter.')
    return render_template('index.html', tweets=tweets)

def lastTenTweets():
    tweets = []
    if g.user is not None:
        resp = twitter.request('statuses/home_timeline.json')
        if resp.status == 200:
            tweets = resp.data
    return tweets


@app.route('/tweet', methods=['POST'])
def tweet():
    if g.user is not None:
        return redirect(url_for('login', next=request.url))
    status = request.form['tweet']
    if not status:
        return redirect(url_for('index'))
    resp = twitter.post('statuses/update.json', data={
        'status': status
    })
    if resp.status == 403:
        flash("Error: #%d, %s " % (
            resp.data.get('errors')[0].get('code'),
            resp.data.get('errors')[0].get('message'))
        )
    elif resp.status == 401:
        flash('Authorization error with Twitter.')
    else:
        flash('Successfully tweeted your tweet (ID: #%s)' % resp.data['id'])
    return render_template('index.html')


@app.route('/login')
def login():
    callback_url = url_for('oauthorized', next=request.args.get('next'))
    return twitter.authorize(callback=callback_url or request.referrer or None)


@app.route('/suggest',methods = ['POST'])
def result():
    if g.user is None:
        return redirect(url_for('login', next=request.url))
    moodDict = {"Joy": 'act', "Sadness": 'cmy', "Anger": 'trl', "Fear": 'fnt', "Analytical": 'doc', "Confident": 'hrr',
                "Tentative": 'rma'}
    tweet = lastTenTweets()
    tweets = []
    for i in range(len(tweet)):
        tweets.append(tweet[i]['text'])
    text = ""
    for i in range(len(tweets)):
        text += " "
        text += tweets[i]
    just_watch = JustWatch(country='US')
    resultsMovies = []
    resultsTV = []
    mood = tone_analyzer.tone(text, content_type="text/plain")
    max_mood = mood.get('document_tone').get('tones')[0].get('tone_name')
    selected = request.form.getlist('check')
    if len(selected) == 0:
        return render_template('index.html', tweets=tweet, noneCheck = True)
    genre = moodDict[max_mood]

    # here should implement cache
    # check if movies / shows corresponding to the given mood have already been stored,
    # if so place those into results
    # else retrieve movies from justwatch api and place results in the database
    # place into a variable called cachedResults so that displaying is easier

    #gquery = "INSERT INTO Users (fname, lname, dob, email, password, gender) VALUES ('{0}' , '{1}', '{2}','{3}','{4}', '{5}')".format(fname, lname, dob, email, password, gender)
    # conn = mysql.connect()
    # cursor = conn.cursor()
    # query = "SELECT * FROM Mood"
    # cursor.execute(query)
    # Moods = cursor.fetchall()

    ## The following code checks the DB for relevant data already being present in the DB
    #conn = mysql.connect()
    #cursor = conn.cursor()
    #if len(selected) ==1:
    #    query = "SELECT mname, mdescription, sname, sdescription FROM Movies M, Shows S, Providers P, Mood MD WHERE M.mid = MD.mdid AND S.sid = MD.mdid AND MD.mdname = '{0}' AND P.pname='{1}'".format(
    #        max_mood,selected[0])
    #    cursor.execute(query)
    #    cachedResults = cursor.fetchall()
    #elif len(selected) ==2:
    #    query = "SELECT mname, mdescription, sname, sdescription FROM Movies M, Shows S, Providers P, Mood MD WHERE M.mid = MD.mdid AND S.sid = MD.mdid AND MD.mdname = '{0}' AND P.pname='{1}' AND P.pname='{2}'".format(
    #        max_mood, selected[0], selected[1])
    #    cursor.execute(query)
    #    cachedResults = cursor.fetchall()
    #elif len(selected) ==3:
    #    query = "SELECT mname, mdescription, sname, sdescription FROM Movies M, Shows S, Providers P, Mood MD WHERE M.mid = MD.mdid AND S.sid = MD.mdid AND MD.mdname = '{0}' AND P.pname='{1}' AND P.pname='{2}'" \
    #            "AND P.pname='{3}'".format(max_mood, selected[0], selected[1], selected[2])
    #    cursor.execute(query)
    #    cachedResults = cursor.fetchall()
    #else:
    #    query = "SELECT mname, mdescription, sname, sdescription FROM Movies M, Shows S, Providers P, Mood MD WHERE M.mid = MD.mdid AND S.sid = MD.mdid AND MD.mdname = '{0}' AND P.pname='{1}' AND P.pname='{2}' " \
    #            "AND P.pname='{3}' AND P.pname='{4}'".format(max_mood, selected[0], selected[1], selected[2], selected[3])
    #    cursor.execute(query)
    #    cachedResults = cursor.fetchall()
    # if cachedResults !=()
    #   render_template('suggest.html', cached=cachedResults, mood=max_mood, tweets=text)
    # else:

    # below occurs if no relevant info found within the DB, every result below needs to be put into the DB

    for i in range(len(selected)):
        if selected[i] == 'Netflix':
            results_by_multiplea = just_watch.search_for_item(
                providers=['nfx'],
                genres=[genre],
                content_types=['movie'])
            movies = results_by_multiplea['items']
            for x in range(len(movies)):
                resultsMovies.append(movies[x])
                # add movie[x]['title'] movie[x]['short_description'] to database
            results_by_multiplef = just_watch.search_for_item(
                providers=['nfx'],
                genres=[genre],
                content_types=['show'])
            tv = results_by_multiplef['items']
            for x in range(len(tv)):
                # add movie[x]['title'] movie[x]['short_description'] to database
                resultsTV.append(tv[x])


        if selected[i] == 'Playstation Video':
            results_by_multipleb = just_watch.search_for_item(
                providers=['pls'],
                content_types=['movie'],
                genres=[genre])
            movies = results_by_multipleb['items']
            for x in range(len(movies)):
                resultsMovies.append(movies[x])

            results_by_multiplef = just_watch.search_for_item(
                providers=['pls'],
                genres=[genre],
                content_types=['show'])
            tv = results_by_multiplef['items']
            for x in range(len(tv)):

                resultsTV.append(tv[x])


        if selected[i] == 'Itunes':
            results_by_multiplec = just_watch.search_for_item(
                providers=['itu'],
                content_types=['movie'],
                genres=[genre])
            movies = results_by_multiplec['items']
            for x in range(len(movies)):

                resultsMovies.append(movies[x])
            results_by_multiplef = just_watch.search_for_item(
                providers=['itu'],
                genres=[genre],
                content_types=['show'])
            tv = results_by_multiplef['items']
            for x in range(len(tv)):

                resultsTV.append(tv[x])


        if selected[i] == 'Google Play':
            results_by_multipled = just_watch.search_for_item(
                providers=['ply'],
                content_types=['movie'],
                genres=[genre])
            movies = results_by_multipled['items']
            for x in range(len(movies)):

                resultsMovies.append(movies[x])
            results_by_multiplef = just_watch.search_for_item(
                providers=['ply'],
                genres=[genre],
                content_types=['show'])
            tv = results_by_multiplef['items']
            for x in range(len(tv)):

                resultsTV.append(tv[x])
        results = [resultsMovies[randint(0, len(resultsMovies) - 1)], resultsTV[randint(0, len(resultsTV) - 1)]]

    return render_template('suggest.html', selected=results, mood=max_mood, tweets=text)


@app.route('/oauthorized')
def oauthorized():
    resp = twitter.authorized_response()
    if resp is None:
        flash('You denied the request to sign in.')
    else:
        session['twitter_oauth'] = resp
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('twitter_oauth', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run()

