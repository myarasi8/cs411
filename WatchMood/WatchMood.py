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

# mysql set up
mysql = MySQL()

app.config['MYSQL_DATABASE_USER'] = 'root'
# NOTE MUST INSERT YOUR OWN PASSWORD
app.config['MYSQL_DATABASE_PASSWORD'] = 'YourPassword'
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
    cachedMovies = searchCachedMovies(selected,genre)
    cachedShows = searchCachedShows(selected,genre)
    #print('####################### Cached Movie results:')
    #print(cachedMovies)
    if cachedMovies != ():
        if cachedShows != ():
            chosenMovie = cachedMovies[randint(0, len(cachedMovies) - 1)]
            chosenShow = cachedShows[randint(0, len(cachedShows) - 1)]
            #print('chosen m:', chosenMovie)
            #print('chosen s:', chosenShow)
            return render_template('suggest.html', cachedMovie=chosenMovie, cachedShow = chosenShow, mood=max_mood, tweets=text)
    else:
    # below occurs if no relevant info found within the DB, every result below needs to be put into the DB
        for i in range(len(selected)):
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
                    # add movie[x]['title'] movie[x]['short_description'] to database
                    storeShow(movies[x]['title'], movies[x]['short_description'], genre)
                    linkShowProvider(movies[x]['title'], 'Netflix')
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
                    storeShow(movies[x]['title'], movies[x]['short_description'], genre)
                    linkShowProvider(movies[x]['title'], 'Playstation Video')
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
                    storeShow(movies[x]['title'], movies[x]['short_description'], genre)
                    linkShowProvider(movies[x]['title'], 'Itunes')
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
                    storeShow(movies[x]['title'], movies[x]['short_description'], genre)
                    linkShowProvider(movies[x]['title'], 'Google Play')
                    resultsTV.append(tv[x])

            # store recommendations in DB using seperate helper functions
            chosenMovie = resultsMovies[randint(0, len(resultsMovies) - 1)]
            storeMovie(chosenMovie['title'], chosenMovie['short_description'], genre)

            chosenShow = resultsTV[randint(0, len(resultsTV) - 1)]
            storeShow(chosenShow['title'], chosenShow['short_description'], genre)

            results = [chosenMovie, chosenShow]
        return render_template('suggest.html', selected=results, mood=max_mood, tweets=text)

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

def storeMovie(title,description,genre):
    #print('title is', title)
    #print('desc is', description)
    #print('genre is', genre)
    conn = mysql.connect()
    cursor = conn.cursor()
    newMovieDesc1 = description.replace("'", "")
    newMovieDesc2 = newMovieDesc1.replace(",", "")
    newTitle1 = title.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "INSERT INTO Movies (mname, mdescription, mgenre) VALUES ('{0}', '{1}', '{2}')".format(newTitle2,newMovieDesc2,genre)
    #print('query is', query)
    cursor.execute(query)
    conn.commit()
    return True

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

def linkMovieProvider(mtitle,pname):
    conn = mysql.connect()
    cursor = conn.cursor()
    mid = getMid(mtitle)
    pid = getPid(pname)
    #print('mid is', mid)
    #print('pis is', pid)
    if checkMovieDuplicate(mid,pid):
        #print('dupe found')
        return True
    else:
        #print('linking p and m:', pid, mid)
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
    #print('row count for p m:',pid,mid, 'is', rowcount)
    if rowcount == 0:
        return False
    else:
        return True

def linkShowProvider(stitle,pname):
    conn = mysql.connect()
    cursor = conn.cursor()
    sid = getSid(stitle)
    pid = getPid(pname)
    #print('sid is', sid)
    #print('pis is', pid)
    if checkShowDuplicate(sid,pid):
        #print('dupe found')
        return True
    else:
        #print('linking p and s:', pid, sid)
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
    #print('row count for p s:', pid, sid, 'is', rowcount)
    if rowcount == 0:
        return False
    else:
        return True

def getMid(mname):
    conn = mysql.connect()
    cursor = conn.cursor()
    newTitle1 = mname.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "SELECT M.mid FROM Movies M WHERE mname = '{0}'".format(newTitle2)
    cursor.execute(query)
    mid = cursor.fetchone()[0]
    return mid

def getSid(sname):
    conn = mysql.connect()
    cursor = conn.cursor()
    newTitle1 = sname.replace("'", "")
    newTitle2 = newTitle1.replace(",", "")
    query = "SELECT S.sid FROM Shows S WHERE sname = '{0}'".format(newTitle2)
    cursor.execute(query)
    sid = cursor.fetchone()[0]
    return sid

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

@app.route('/logout')
def logout():
    session.pop('twitter_oauth', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run()

