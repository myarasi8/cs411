## **Idea 1:**

With the amount of streaming sites available to the consumers and the vast libraries of shows and movies to choose from, 
it is very difficult to decide what to watch.  This app will give the user a suggestion for a show or movie, based on what 
streaming sites they subscribe to and their current moods.  This app will gather recent tweets from a user, send them through 
IBM Watson Tone Analyzer to get the person’s mood, and select the best choice via genre and ratings using the IMDB API.  
JustWatch API will be used to gather the current libraries on each of the streaming sites.


## **Idea 2:**

Wanted to cook something but don’t know where to start?

The goal is to create an app which allows users to input a meal that they would like to prepare. 
The app will then find the highest rated recipe for the desired dish, look for its component through 
the Wal-mart API and create a cart filled with said items for a quick checkout. Users will not only be 
provided with the price, but also nutritional information regarding the completed dish itself.  


Finds a recipe for a given dish, compiles its components in a walmart cart, and presents this along with 
the price and some nutritional info. 

APIs:

Gmail or Facebook for user authentication.

Food2Fork or Edamam for searching recipes.

Wal-Mart for item prices / availability and creating a cart feature

Nutritionix or USDA Nutrients to find nutritional data for the dish 
