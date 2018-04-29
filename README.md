# cs411
When you are up late and can’t decide what to watch, this web application will solve your problems. Just tweet about how you’re feeling and go to our app. Click on which streaming services you are subscribed to and click submit! We will provide a movie and show for you to watch!

The app uses the following API’s:
1.	Twitter – the user uses Twitter to login and this is where security authentication is implemented. The user’s most recent tweets will also be displayed in the live feed portion of the app.
2.	IBM Watson Tone Analyzer – the users top 20 tweets will be analyzed and a mood will be generated. Each possible mood will be associated with a specific genre, ex: joy is associated with action. 
3.	JustWatch – The JustWatch API takes the mood and pulls one television show and 1 movie from the genre associated with that mood and displays it on the screen

We have implemented a cache that stores a mood and the TV and movie recommendations associated with that mood. So, if the user is feeling the same way in the future, it will bring their recommendations. If the user has already seen these then they can submit their tweets for a new recommendation. The cache will then be updated. 

Our Web app uses a Flask framework so the entire application is written in Python with HTML and CSS styling. We chose this framework as everyone in the group has a background in Python and due to the fact that Python is synchronous – thus avoiding asynchronous issues. 
In addition the back-end of our application employs a MySQL relational databse. This is mainly utilized to store movies, tvshows and their related providers, for caching purposes. 
