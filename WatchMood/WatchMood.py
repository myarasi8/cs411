# importing relevant tools from packages
# general tools / packages:
from flask import Flask
from flask import g, session, request, url_for, flash
from flask import redirect, render_template
from random import randint
import config
# for APIs:
from flask_oauthlib.client import OAuth
from justwatch import JustWatch
from watson_developer_cloud import ToneAnalyzerV3
# for SQL database:
from flaskext.mysql import MySQL

# setting up Flask
app = Flask(__name__)
app.debug = True
app.secret_key = 'development'

# mysql set up
mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
# NOTE MUST INSERT YOUR OWN PASSWORD
app.config['MYSQL_DATABASE_PASSWORD'] = config.SQL['password']
app.config['MYSQL_DATABASE_DB'] = 'WatchMood'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)

# Oauth set up
oauth = OAuth(app)

# connecting to twitter API using oauth
twitter = oauth.remote_app(
    'twitter',
    consumer_key=config.twitter['key'],
    consumer_secret=config.twitter['secret'],
    base_url='https://api.twitter.com/1.1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authorize'
)

# connecting to IBM Watson tone analyzer
tone_analyzer = ToneAnalyzerV3(
    username= config.watson['username'],
    password= config.watson['password'],
    version='2017-09-26')

# getting twitter oauth token
@twitter.tokengetter
def get_twitter_token():
    if 'twitter_oauth' in session:
        resp = session['twitter_oauth']
        return resp['oauth_token'], resp['oauth_token_secret']

# establishing the user's session
@app.before_request
def before_request():
    g.user = None
    if 'twitter_oauth' in session:
        g.user = session['twitter_oauth']

# front page of the app, what users are greeted with
# if the user is logged in, retrieves their recent tweets on their timeline
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

# helper function which retrieves the users most recent tweets
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

# app routes for logging in and authorization
@app.route('/login')
def login():
    callback_url = url_for('oauthorized', next=request.args.get('next'))
    return twitter.authorize(callback=callback_url or request.referrer or None)

# app route for the main feature of the app, providing the user with a movie / tvshow suggestion based on
# their perceived mood on twitter
@app.route('/suggest',methods = ['POST'])
def result():
    if g.user is None:
        return redirect(url_for('login', next=request.url))
    # created a mood dictionary that pairs all the possible main moods detected by the tone analyzer with a corresponding genre
    moodDict = {"Joy": 'act', "Sadness": 'cmy', "Anger": 'trl', "Fear": 'fnt', "Analytical": 'doc', "Confident": 'hrr',
                "Tentative": 'rma'}
    # concatinating all of the users tweets in variable text, which is then passed to the IBM Watson Tone Analyzer API
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

    # following if statement checks that the user picks at least one provider when requesting a suggestion
    if len(selected) == 0:
        return render_template('index.html', tweets=tweet, noneCheck = True)

    genre = moodDict[max_mood]

    # Here we implement our caching, before requesting movies / tvshows of the appropriate genre and correct provider
    # from the JustWatch API, the following code checks our SQL database to see if the relevant movies / tvshows are
    # already being present in the Database, if so the suggestion is made from this data
    cachedMovies = searchCachedMovies(selected,genre)
    cachedShows = searchCachedShows(selected,genre)
    if cachedMovies != ():
        if cachedShows != ():
            # to allow for some variation in the recommended movie / show a random index is used
            chosenMovie = cachedMovies[randint(0, len(cachedMovies) - 1)]
            chosenShow = cachedShows[randint(0, len(cachedShows) - 1)]
            return render_template('suggest.html', cachedMovie=chosenMovie, cachedShow=chosenShow, mood=max_mood, tweets=text)

    # below occurs if no relevant info found within the Database, the following code retrieves relevant movies and
    # tv shows depending on what providers the user selected, all of the results are stored within our database
    # using the storeMovie and storeShow helper function, additionally the linkMovieProvider and linkShowProvider
    # helper functions are used to ensure that the movies / tvshows are linked to the correct provider
    # (this is done to ensure DB accuracy)
    else:
        for i in range(len(selected)):
            # for loop goes through all the selected providers and retrieves / stores relevant data from them,
            # each if statement checks which provider the current index represents and then passes the relevent data
            # for retrieval and storage
            if selected[i] == 'Netflix':
                results_by_multiplea = just_watch.search_for_item(
                    providers=['nfx'],
                    genres=[genre],
                    content_types=['movie'])
                movies = results_by_multiplea['items']
                for x in range(len(movies)):
                    storeMovie(movies[x]['title'],movies[x]['short_description'],genre)
                    linkMovieProvider(movies[x]['title'],'Netflix')
                    resultsMovies.append(movies[x])
                results_by_multiplef = just_watch.search_for_item(
                    providers=['nfx'],
                    genres=[genre],
                    content_types=['show'])
                tv = results_by_multiplef['items']
                for x in range(len(tv)):
                    storeShow(tv[x]['title'], tv[x]['short_description'], genre)
                    linkShowProvider(tv[x]['title'], 'Netflix')
                    resultsTV.append(tv[x])

            if selected[i] == 'Playstation Video':
                results_by_multipleb = just_watch.search_for_item(
                    providers=['pls'],
                    content_types=['movie'],
                    genres=[genre])
                movies = results_by_multipleb['items']
                for x in range(len(movies)):
                    storeMovie(movies[x]['title'], movies[x]['short_description'], genre)
                    linkMovieProvider(movies[x]['title'], 'Playstation Video')
                    resultsMovies.append(movies[x])
                results_by_multiplef = just_watch.search_for_item(
                    providers=['pls'],
                    genres=[genre],
                    content_types=['show'])
                tv = results_by_multiplef['items']
                for x in range(len(tv)):
                    storeShow(tv[x]['title'], tv[x]['short_description'], genre)
                    linkShowProvider(tv[x]['title'], 'Playstation Video')
                    resultsTV.append(tv[x])

            if selected[i] == 'Itunes':
                results_by_multiplec = just_watch.search_for_item(
                    providers=['itu'],
                    content_types=['movie'],
                    genres=[genre])
                movies = results_by_multiplec['items']
                for x in range(len(movies)):
                    storeMovie(movies[x]['title'], movies[x]['short_description'], genre)
                    linkMovieProvider(movies[x]['title'], 'Itunes')
                    resultsMovies.append(movies[x])
                results_by_multiplef = just_watch.search_for_item(
                    providers=['itu'],
                    genres=[genre],
                    content_types=['show'])
                tv = results_by_multiplef['items']
                for x in range(len(tv)):
                    storeShow(tv[x]['title'], tv[x]['short_description'], genre)
                    linkShowProvider(tv[x]['title'], 'Itunes')
                    resultsTV.append(tv[x])

            if selected[i] == 'Google Play':
                results_by_multipled = just_watch.search_for_item(
                    providers=['ply'],
                    content_types=['movie'],
                    genres=[genre])
                movies = results_by_multipled['items']
                for x in range(len(movies)):
                    storeMovie(movies[x]['title'], movies[x]['short_description'], genre)
                    linkMovieProvider(movies[x]['title'], 'Google Play')
                    resultsMovies.append(movies[x])
                results_by_multiplef = just_watch.search_for_item(
                    providers=['ply'],
                    genres=[genre],
                    content_types=['show'])
                tv = results_by_multiplef['items']
                for x in range(len(tv)):
                    storeShow(tv[x]['title'], tv[x]['short_description'], genre)
                    linkShowProvider(tv[x]['title'], 'Google Play')
                    resultsTV.append(tv[x])

            # generate the movie / tvshow recommendation from all the data retrieved using a random index
            # this allows for some variation in the recommended result
            chosenMovie = resultsMovies[randint(0, len(resultsMovies) - 1)]
            chosenShow = resultsTV[randint(0, len(resultsTV) - 1)]
            results = [chosenMovie, chosenShow]
        return render_template('suggest.html', selected=results, mood=max_mood, tweets=text)

# The following are all helper functions used to store and retrieve data from the SQL database
# The searchCachedMovies helper function takes a list of providers and a genre as input and returns
# all the relevant movies found within the database, allowing our caching to be implemented
def searchCachedMovies(providers,genre):
    conn = mysql.connect()
    cursor = conn.cursor()
    if len(providers) == 1:
        query = "SELECT mname, mdescription FROM Movies M, Providers P, MovieMatch MM " \
                "WHERE M.mid = MM.mid AND MM.pid = P.pid AND M.mgenre = '{0}' AND P.pname = '{1}'".format(genre,providers[0])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    elif len(providers) == 2:
        query = "SELECT mname, mdescription FROM Movies M, Providers P, MovieMatch MM " \
                "WHERE M.mid = MM.mid AND MM.pid = P.pid AND M.mgenre = '{0}' AND P.pname = '{1}' AND P.pname = '{2}'".format(genre,providers[0],providers[1])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    elif len(providers) == 3:
        query = "SELECT mname, mdescription FROM Movies M, Providers P, MovieMatch MM " \
                "WHERE M.mid = MM.mid AND MM.pid = P.pid AND M.mgenre = '{0}' AND P.pname = '{1}' AND P.pname = '{2}' AND P.pname = '{3}'".format(genre,providers[0],providers[1],providers[2])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    else:
        query = "SELECT mname, mdescription FROM Movies M, Providers P, MovieMatch MM " \
                "WHERE M.mid = MM.mid AND MM.pid = P.pid AND M.mgenre = '{0}' AND P.pname = '{1}' AND P.pname = '{2}' AND P.pname = '{3}' AND P.pname = '{4}'".format(genre,providers[0], providers[1], providers[2],providers[3])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    return cachedResults

# Similar to the searchCachedMovies, the searchCachedShows helper function takes a list of providers and a genre as
# input and returns all the relevant shows found within the database, allowing our caching to be implemented
def searchCachedShows(providers,genre):
    conn = mysql.connect()
    cursor = conn.cursor()
    if len(providers) == 1:
        query = "SELECT sname, sdescription FROM Shows S, Providers P, ShowMatch SM " \
                "WHERE S.sid = SM.sid AND SM.pid = P.pid AND S.sgenre = '{0}' AND P.pname = '{1}'".format(genre, providers[0])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    elif len(providers) == 2:
        query = "SELECT sname, sdescription FROM Shows S, Providers P, ShowMatch SM " \
                "WHERE S.sid = SM.sid AND SM.pid = P.pid AND S.sgenre = '{0}' AND P.pname = '{1}' AND P.pname = '{2}'".format(genre,providers[0], providers[1])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    elif len(providers) == 3:
        query = "SELECT sname, sdescription FROM Shows S, Providers P, ShowMatch SM " \
                "WHERE S.sid = SM.sid AND SM.pid = P.pid AND S.sgenre = '{0}' AND P.pname = '{1}' AND P.pname = '{2}' AND P.pname = '{3}'".format(genre,providers[0], providers[1], providers[2])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    else:
        query = "SELECT sname, sdescription FROM Shows S, Providers P, ShowMatch SM " \
                "WHERE S.sid = SM.sid AND SM.pid = P.pid AND S.sgenre = '{0}' AND P.pname = '{1}' AND P.pname = '{2}' AND P.pname = '{3}' AND P.pname = '{4}'".format(genre,providers[0], providers[1], providers[2],providers[3])
        cursor.execute(query)
        cachedResults = cursor.fetchall()
    return cachedResults

# The storeMovie helper function takes a movie title, description and genre as input and stores said data
# in our database. For both the movie titles and descriptions commas and apostrophes are removed to
# prevent syntax errors
def storeMovie(title,description,genre):
    conn = mysql.connect()
    cursor = conn.cursor()
    newMovieDesc1 = description.replace("'", "")
    newMovieDesc2 = newMovieDesc1.replace(",", "")
    newTitle1 = title.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "INSERT INTO Movies (mname, mdescription, mgenre) VALUES ('{0}', '{1}', '{2}')".format(newTitle2,newMovieDesc2,genre)
    cursor.execute(query)
    conn.commit()
    return True

# The storeShow helper function takes a show title, description and genre as input and stores said data
# in our database. For both the show titles and descriptions commas and apostrophes are removed to
# prevent syntax errors
def storeShow(title,description,genre):
    conn = mysql.connect()
    cursor = conn.cursor()
    newShowDesc1 = description.replace("'", "")
    newShowDesc2 = newShowDesc1.replace(",", "")
    newTitle1 = title.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "INSERT INTO Shows (sname, sdescription, sgenre) VALUES ('{0}', '{1}', '{2}')".format(newTitle2,newShowDesc2,genre)
    cursor.execute(query)
    conn.commit()
    return True

# The linkMovieProvider helper function takes a movie title and provider name as input and ensures that the
# correct link / relationship between the two is made within our database, the getMid and getPid helper functions are
# used to help store this information. Before insertion the function uses the checkMovieDuplicate helper function
# to make sure that the relationship hasn't already been established, preventing duplicate entries.
def linkMovieProvider(mtitle,pname):
    conn = mysql.connect()
    cursor = conn.cursor()
    mid = getMid(mtitle)
    pid = getPid(pname)
    if checkMovieDuplicate(mid,pid):
        return True
    else:
        query = "INSERT INTO MovieMatch (mid, pid) VALUES ('{0}', '{1}')".format(mid,pid)
        cursor.execute(query)
        conn.commit()
        return True

def checkMovieDuplicate(mid,pid):
    conn = mysql.connect()
    cursor = conn.cursor()
    query = "SELECT * FROM MovieMatch WHERE pid = '{0}' AND mid = '{1}' ".format(pid,mid)
    cursor.execute(query)
    rowcount = cursor.rowcount
    if rowcount == 0:
        return False
    else:
        return True

# The linkShowProvider helper function takes a show title and provider name as input and ensures that the
# correct link / relationship between the two is made within our database, the getMid and getPid helper functions are
# used to help store this information. Before insertion the function uses the checkShowDuplicate helper function
# to make sure that the relationship hasn't already been established, preventing duplicate entries.
def linkShowProvider(stitle,pname):
    conn = mysql.connect()
    cursor = conn.cursor()
    sid = getSid(stitle)
    pid = getPid(pname)
    if checkShowDuplicate(sid,pid):
        return True
    else:
        query = "INSERT INTO ShowMatch (sid, pid) VALUES ('{0}', '{1}')".format(sid,pid)
        cursor.execute(query)
        conn.commit()
        return True

def checkShowDuplicate(sid,pid):
    conn = mysql.connect()
    cursor = conn.cursor()
    query = "SELECT * FROM ShowMatch WHERE pid = '{0}' AND sid = '{1}' ".format(pid,sid)
    cursor.execute(query)
    rowcount = cursor.rowcount
    if rowcount == 0:
        return False
    else:
        return True

# The getMid helper function takes as input a movie title and finds and returns its relevant mid number
# from the SQL database. It is utilized in the helper function above for situations in which the movie title
# is known but its mid number is not
def getMid(mname):
    conn = mysql.connect()
    cursor = conn.cursor()
    newTitle1 = mname.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "SELECT M.mid FROM Movies M WHERE mname = '{0}'".format(newTitle2)
    cursor.execute(query)
    mid = cursor.fetchone()[0]
    return mid

# The getSid helper function takes as input a tvshow title and finds and returns its relevant sid number
# from the SQL database. It is utilized in the helper function above for situations in which the tvshow title
# is known but its sid number is not
def getSid(sname):
    conn = mysql.connect()
    cursor = conn.cursor()
    newTitle1 = sname.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "SELECT S.sid FROM Shows S WHERE sname = '{0}'".format(newTitle2)
    cursor.execute(query)
    sid = cursor.fetchone()[0]
    return sid

# The getPid helper function takes as input a provider name and finds and returns its relevant pid number
# from the SQL database. It is utilized in the helper function above for situations in which the provider name
# is known but its pid number is not
def getPid(pname):
    conn = mysql.connect()
    cursor = conn.cursor()
    query = "SELECT P.pid FROM Providers P WHERE pname = '{0}'".format(pname)
    cursor.execute(query)
    pid = cursor.fetchone()[0]
    return pid

@app.route('/oauthorized')
def oauthorized():
    resp = twitter.authorized_response()
    if resp is None:
        flash('You denied the request to sign in.')
    else:
        session['twitter_oauth'] = resp
    return redirect(url_for('index'))

# app route for logging out of the app
@app.route('/logout')
def logout():
    session.pop('twitter_oauth', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run()

