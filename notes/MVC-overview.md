Model-View-Controller, commonly referred to as MVC, is an architectural pattern for organizing code. With MVC the organization is sorted based on what the code is responsible for. This is oftentimes referred to as separation of concerns.

When using MVC, developers are ultimately responsible for putting code into the right location and making sure the MVC pattern is followed. As a result, differing opinions or mistakes can lead to two codebases that both use MVC, but end up with a very different organization of the code.

There are three distinct roles in MVC are models, views, and controllers. In our application we will start by breaking our code into three packages with these names.

Models are about data, including logic and rules for data. In practice this typically means models encompass code used to interact with the database, but it isn’t limited to database code. Models could also entail code for interacting with files on the hard drive or data from a third party API.

Code classified as a model is not limited to fetching data. Models can also include code for validating and normalizing data. For example, our web application is going to have user accounts, and when we store those in our database we will want to make sure that an email address in all capital letters is not treated differently from one in lowercase. More specifically, the following two email addresses should be considered the same for account purposes:
