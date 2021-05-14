# CITS3002 Socket Programming Project
> Implement a game server to host a strategic tile placing game

## Table of Contents
* [General Info](#general-information)
* [Technologies Used](#technologies-used)
* [Features](#features)
* [Screenshots](#screenshots)
* [Setup](#setup)
* [Usage](#usage)
* [Project Status](#project-status)
* [Acknowledgements](#acknowledgements)

## General Information
- The tiles.py and client_v2.py was provided as the project framework


## Technologies Used
- Python 3.7
- The select library in python only works on Unix based systems, so this must be run on a Mac or Linux 

## The Game and How To Play
These instructions were provided in the project framework
The game is a strategic tile placing game. Each player is given a set of random tiles (from a preset list of tiles) by the server. A tile has two points on each side (north, east, south, and west). Each of these eight points is connected to one of the other points on the tile, so there are four connections in total.

The board is initially empty. One at a time, in an order determined by the server, each player places a single tile on the board, ensuring that the first tile is connected to the edge of the board. 
In the second turn, each player chooses where their token will enter the board. This must be one of the points on the tile that they placed in the first turn, so there will be either two or four possible locations (depending on whether or not the tile was placed in a corner).
The player's token automatically follows the connection across the tile, reaching a new square of the board. If that board already has a tile, the token will follow the connection in the new tile, continuing until it either reaches an empty square or the edge of the board. If a player's token reaches the edge of the board, that player is eliminated.
On the third turn, and all subsequent turns, each remaining player may place a single tile from their hand onto the empty square that their token is entering. Any other players who are entering the same square will
be moved automatically according to the connections on the placed tile, so it is possible for other players to
be eliminated.
If only one player remains alive, that player is considered the winner.


## Features
List the ready features implemented by server.py:
- If there are at least two clients connected the game will commence.
- There is a countdown set to all players, and the game will start after a short pause
- If anymore clients join, they will be added to the game, with a max of four players able to start any particular round.
- If the players join half way, they are caught up on the positions of all the tiles and tokens of other players.
- If a player is eliminated, and there has not been four players who have already joined the game, another player is added if there are any waiting to connect.
- Once eliminated, the player cannot rejoin that same game and have to wait for the next game.
- The game allows connected clients and eliminated players to watch the game unfold as spectators.
- When the game is over, if there are enough clients waiting to start another game, another game will start after a short pause.


## Screenshots

<img width="2126" alt="tilesgame" src="https://user-images.githubusercontent.com/37872572/118247463-cb7e0700-b4d5-11eb-99ec-f4e98e74fa43.png">



## Setup
Download Project. Make sure you have Python 3.0 and higher and running on a Unix Platform.


## Usage
Open multiple terminal windows.
In command line, navigate to the folder.
In one of the terminal windows, run: 

`python3 server5.py`

This is the final working version!
In other terminal windows, run:

`python3 client_v2.py`

Do this last step at least twice, to create two clients.
When there are at least two clients connected, the server will start the game and deal the hand.

Enjoy the game!

## Project Status
This project is a work in progress. Next implementation will have an autoplay component to play tiles if the player hasn't made a move in 10secs so we can improve the flow of the game.

To do: 
- Deploy the game on EC2 instance. Have a database for players to create accounts and leaderboards to tally up wins.


## Acknowledgements
Thanks to Matt for a cool project! Really had fun doing this! 

