# Imports
import logging
import multiprocessing
import socket
import select
import queue
import tiles
import random
import time

MIN_PLAYERS = 2
MAX_PLAYERS = 4


class Player:
    def __init__(self, connection: socket, idnum: int, address: str):
        self.connection = connection
        self.idnum = idnum
        self.host, self.port = address
        self.name = '{}:{}'.format(self.host, self.port)



class Game:
    def __init__(self):
        self.idnum = 0
        self.live_idnums = []
        self.waiting_clients = []
        self.waiting_clients_for_next_game = []
        self.all_connections = []
        self.current_players = []
        self.all_players_eliminated_from_game = []
        self.all_players_to_start_current_game = []
        self.current_player = None
        self.game_started = False
        self.board = tiles.Board()
        self.inputs = [server]
        self.outputs = []
        self.msg_queue = {}
        self.buffer = bytearray()

    def create_client_socket(self, socket):
        connection, client_address = socket.accept()
        connection.setblocking(False)
        self.inputs.append(connection)
        self.outputs.append(connection)
        logging.info(f'38: Client Connection: {client_address}')

        # send new connection welcome message
        self.msg_queue[connection] = queue.Queue()
        self.msg_queue[connection].put(tiles.MessageWelcome(self.idnum).pack())
        logging.info("43")

        # create new player and add it to players list
        new_player = Player(connection, self.idnum, client_address)
        self.idnum += 1

        # add Player to connections and waiting lists
        self.all_connections.append(new_player)
        self.waiting_clients.append(new_player)

        # notify all clients of all connections
        for a in self.all_connections:
            for c in self.all_connections:
                game.msg_queue[c.connection].put(tiles.MessagePlayerJoined(a.name, a.idnum).pack())

        return new_player

    def enough_players(self):
        return len(self.current_players) == MIN_PLAYERS

    def number_of_players(self):
        return len(self.current_players)

    def not_enough_players(self):
        logging.info("73")
        return len(self.current_players) < MIN_PLAYERS

    def enough_clients_to_start_a_game(self):
        return len(self.waiting_clients + self.waiting_clients_for_next_game) >= MIN_PLAYERS

    def shuffle_players(self):
        return random.shuffle(self.waiting_clients)

    def get_next_player_idnum(self, client_socket, eliminated_list):
        logging.info("80: Getting next player idnum")
        current_index = 0
        current_idnum = 0
        number_of_players = len(self.current_players)
        for p in range(number_of_players):
            if self.current_players[p].connection == client_socket:
                current_idnum = self.current_players[p].idnum
                current_index = p

        if len(self.live_idnums) > (len(eliminated_list) + 1):

            if current_idnum in eliminated_list:
                next_index = current_index
            else:
                next_index = (current_index + 1) % number_of_players

            while self.current_players[next_index].idnum in eliminated_list:
                next_index = (next_index + 1) % number_of_players

            next_idnum = self.current_players[next_index].idnum
            logging.info(f'91: Next Player Idnum = {next_idnum}')
            return next_idnum
        else:
            return current_idnum

    def find_connection_for_idnum(self, idnum):
        for a in self.all_connections:
            if a.idnum == idnum:
                return a.connection

    def if_game_is_over(self):
        return self.game_started and (len(self.current_players) == 1)

    def start_new_game(self):
        logging.info("Start New Game")
        self.shuffle_players()
        self.live_idnums.clear()
        self.all_players_to_start_current_game.clear()

        if self.not_enough_players():
            # add waiting clients to players list and live_idnums
            for i in range(MIN_PLAYERS):
                new_player = self.waiting_clients[i]
                self.current_players.append(new_player)
                self.live_idnums.append(new_player.idnum)
            for p in self.current_players:
                if p in self.waiting_clients:
                    self.waiting_clients.remove(p)
                logging.info(f"153: Waiting Clients = {len(self.waiting_clients)}")

        # if there are more clients waiting to play, add up to the MAX_PlAYERS
        for i in range(len(self.waiting_clients)):
            if len(self.current_players) < MAX_PLAYERS:
                new_player = self.waiting_clients[i]
                self.current_players.append(new_player)
                self.live_idnums.append(new_player.idnum)
        for p in self.current_players:
            if p in self.waiting_clients:
                self.waiting_clients.remove(p)

        self.all_players_to_start_current_game = self.all_players_to_start_current_game + self.current_players

        # notify players that the game is starting
        for a in self.all_connections:
            game.msg_queue[a.connection].put(tiles.MessageGameStart().pack())

        # notify all clients of players turn positions
        for a in self.all_connections:
            for p in self.current_players:
                game.msg_queue[a.connection].put(tiles.MessagePlayerTurn(p.idnum).pack())

        for p in self.current_players:
            # deal hand
            for _ in range(tiles.HAND_SIZE):
                tileid = tiles.get_random_tileid()
                game.msg_queue[p.connection].put(tiles.MessageAddTileToHand(tileid).pack())

        # send all players turn info for first player to start
        for a in self.all_connections:
            game.msg_queue[a.connection].put(tiles.MessagePlayerTurn(self.current_players[0].idnum).pack())


        time.sleep(5.0)
        # reset the board
        self.board.reset()
        self.current_player = self.current_players[0]
        self.game_started = True

    def start_another_game(self):
        logging.info("162: Start another game")
        time.sleep(5.0)
        self.waiting_clients.append(self.current_players[0])
        self.current_players.clear()
        self.live_idnums.clear()
        self.all_players_eliminated_from_game.clear()
        self.game_started = False

        if self.enough_clients_to_start_a_game():
            for a in self.all_connections:
                game.msg_queue[a.connection].put(tiles.MessageCountdown().pack())
            time.sleep(5.0)
            self.waiting_clients = self.waiting_clients + self.waiting_clients_for_next_game
            self.waiting_clients_for_next_game.clear()
            self.start_new_game()

    def replace_eliminated_players(self):
        logging.info("171:Replace Eliminated Player")
        # if game isn't over, replace eliminated players
        if not self.if_game_is_over():
            # check if players have been eliminated and add new players
            joining_players = []
            logging.info(f"182: Waiting Clients = {len(self.waiting_clients)}")

            number_of_players_to_add = min(MAX_PLAYERS - len(self.current_players), len(self.waiting_clients))
            logging.info(f'186: players to add = {number_of_players_to_add}')

            # add player to the list and notify everyone
            self.shuffle_players()
            if number_of_players_to_add > 0:
                while number_of_players_to_add != 0 and len(self.waiting_clients) > 0:
                    logging.info("184")
                    joining_player = self.waiting_clients[0]
                    self.current_players.append(joining_player)
                    self.live_idnums.append(joining_player.idnum)
                    self.waiting_clients.remove(joining_player)
                    joining_players.append(joining_player)
                    logging.info(f" 191: Waiting Clients = {len(self.waiting_clients)} "
                                 f"Joining Player idnum = {joining_player.idnum}")
                    number_of_players_to_add -= 1

                    # reset all turn positions
                    for a in self.all_connections:
                        for p in self.current_players:
                            self.msg_queue[a.connection].put(tiles.MessagePlayerTurn(p.idnum).pack())

                # send player current turn info
                # deal hand
                for j in joining_players:
                    self.msg_queue[j.connection].put(tiles.MessagePlayerTurn(self.current_player.idnum).pack())
                    for e in self.all_players_eliminated_from_game:
                        self.msg_queue[j.connection].put(tiles.MessagePlayerEliminated(e).pack())
                    for _ in range(tiles.HAND_SIZE):
                        tileid = tiles.get_random_tileid()
                        game.msg_queue[j.connection].put(tiles.MessageAddTileToHand(tileid).pack())

                for a in self.all_connections:
                    self.msg_queue[a.connection].put(tiles.MessagePlayerTurn(self.current_player.idnum).pack())

    def add_more_players_to_current_game(self, new_player):
        # allow more players to be added to current game if there has been less than max_player-1 players eliminated
        # this allows us to replace a player that hasn't completed their turn if they disconnect
        logging.info("230: adding more players")
        if len(self.all_players_eliminated_from_game) < (MAX_PLAYERS - 1):
            self.current_players.append(new_player)
            self.live_idnums.append(new_player.idnum)
            self.waiting_clients.remove(new_player)
            self.all_players_to_start_current_game.append(new_player)

            # reset all turn positions
            for a in self.all_connections:
                for p in self.current_players:
                    self.msg_queue[a.connection].put(tiles.MessagePlayerTurn(p.idnum).pack())

            # send player current turn info
            # deal hand
            for e in self.all_players_eliminated_from_game:
                self.msg_queue[new_player.connection].put(tiles.MessagePlayerEliminated(e).pack())
            self.msg_queue[new_player.connection].put(tiles.MessagePlayerTurn(self.current_player.idnum).pack())
            for _ in range(tiles.HAND_SIZE):
                tileid = tiles.get_random_tileid()
                game.msg_queue[new_player.connection].put(tiles.MessageAddTileToHand(tileid).pack())

            for a in self.all_connections:
                self.msg_queue[a.connection].put(tiles.MessagePlayerTurn(self.current_player.idnum).pack())


    def update_board_for_joining_clients(self, new_player):
        # if game has started, send the new connection, the player's idnums
        for p in self.current_players:
            self.msg_queue[new_player.connection].put(tiles.MessagePlayerJoined(p.name, p.idnum).pack())
        logging.info("207: Update client")
        # notify all players that new client has joined
        for a in self.all_connections:
            self.msg_queue[a.connection].put(tiles.MessagePlayerJoined(new_player.name, new_player.idnum).pack())

        # notify the client of all player positions
        for p in self.current_players:
            self.msg_queue[new_player.connection].put(tiles.MessagePlayerTurn(p.idnum).pack())
        for e in self.all_players_eliminated_from_game:
            self.msg_queue[new_player.connection].put(tiles.MessagePlayerEliminated(e).pack())

        # catch them up on tiles on the board
        for h in range(self.board.height):
            for w in range(self.board.width):
                tileids, tilerotations, tileplaceids = self.board.get_tile(h, w)
                if tileids:
                    self.msg_queue[new_player.connection].put(
                        tiles.MessagePlaceTile(tileplaceids, tileids, tilerotations, h, w).pack())

        # send token positions
        for p in self.current_players:
            if self.board.have_player_position(p.idnum):
                token_pos = self.board.get_player_position(p.idnum)
                self.msg_queue[new_player.connection].put(
                    tiles.MessageMoveToken(p.idnum, token_pos[0], token_pos[1], token_pos[2]).pack())



logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ('', 30020)
server.bind(server_address)
server.setblocking(False)
logging.info(f'Listening on port {server.getsockname()}')
server.listen(5)

game = Game()

while True:
    # must give a time out value to select or else it will act in a blocking manner
    readable, writable, errors = select.select(game.inputs, game.outputs, game.inputs, 1.0)

    for s in readable:
        try:
            # the server only listens for connections and creates client sockets
            if s == server:
                # create a client socket and add it inputs and outputs list
                new_player = game.create_client_socket(s)
                logging.info("253")
                if game.game_started:
                    game.update_board_for_joining_clients(new_player)
                    if len(game.current_players) < MAX_PLAYERS:
                        game.add_more_players_to_current_game(new_player)
                # if game hasn't started check if there are enough players to start a game:
                if not game.game_started and game.enough_clients_to_start_a_game():
                    for a in game.all_connections:
                        game.msg_queue[a.connection].put(tiles.MessageCountdown().pack())
                    time.sleep(5.0)
                    game.start_new_game()
                logging.info("260")


            else:
                data = s.recv(4096)
                if data:
                    if s == game.current_player.connection:
                        game.buffer.extend(data)
                        msg, consumed = tiles.read_message_from_bytearray(game.buffer)
                        # logging.info(f'Message Attribute ID = {msg.idnum}')

                        if consumed > 0:
                            game.buffer = game.buffer[consumed:]

                            # sent by the player to put a tile onto the board (in all turns except
                            # their second)
                            if isinstance(msg, tiles.MessagePlaceTile):
                                # logging.info(f'202: Player {msg.idnum} has place tileid = {msg.tileid}')
                                if game.board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):

                                    # notify player, placement was successful
                                    for a in game.all_connections:
                                        game.msg_queue[a.connection].put(msg.pack())

                                    # check for token movement
                                    positionupdates, eliminated = game.board.do_player_movement(game.live_idnums)
                                    game.all_players_eliminated_from_game = game.all_players_eliminated_from_game + eliminated
                                    for msg in positionupdates:
                                        for a in game.all_connections:
                                            game.msg_queue[a.connection].put(msg.pack())

                                    next_player_idnum = game.get_next_player_idnum(s, eliminated)
                                    logging.info("294")

                                    for p in game.current_players:
                                        if next_player_idnum == p.idnum:
                                            game.current_player = p

                                    for eliminated_player in eliminated:
                                        # remove player from live_idnums list
                                        if eliminated_player in game.live_idnums:
                                            game.live_idnums.remove(eliminated_player)

                                        # send out elimination status to all clients
                                        for a in game.all_connections:
                                            game.msg_queue[a.connection].put(
                                                tiles.MessagePlayerEliminated(eliminated_player).pack())

                                        for i in range(len(game.current_players)):
                                            if game.current_players[i].idnum == eliminated_player:
                                                for a in game.all_connections:
                                                    elim_player = game.current_players[i]
                                                # remove from players list and add back to waiting list for next game
                                                game.waiting_clients_for_next_game.append(game.current_players[i])

                                        logging.info(f"333: Current Players = {game.current_players}")
                                        for p in game.current_players:
                                            if p.idnum == eliminated_player:
                                                logging.info(f"336: Current Player removed = {p.idnum}")
                                                game.current_players.remove(p)

                                    # Replace eliminated players if there hasn't already been 4 players in this round
                                    if eliminated and (len(game.all_players_eliminated_from_game) < (MAX_PLAYERS - 1)):
                                        game.replace_eliminated_players()

                                    logging.info(f"323: Game Started = {game.game_started} "
                                                 f"and current players = {len(game.current_players)}")

                                    for a in game.all_connections:
                                        game.msg_queue[a.connection].put(
                                            tiles.MessagePlayerTurn(next_player_idnum).pack())

                                    if not game.if_game_is_over():
                                        logging.info("326")
                                        # start next turn
                                        # pickup a new tile
                                        tileid = tiles.get_random_tileid()
                                        game.msg_queue[s].put(tiles.MessageAddTileToHand(tileid).pack())
                                        logging.info('335')

                            # sent by the player in the second turn, to choose their token's
                            # starting path
                            elif isinstance(msg, tiles.MessageMoveToken):
                                if not game.board.have_player_position(msg.idnum):
                                    if game.board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
                                        # check for token movement
                                        logging.info("339")
                                        positionupdates, eliminated = game.board.do_player_movement(game.live_idnums)
                                        game.all_players_eliminated_from_game = game.all_players_eliminated_from_game + eliminated

                                        for msg in positionupdates:
                                            for a in game.all_connections:
                                                game.msg_queue[a.connection].put(msg.pack())
                                                logging.info("346")
                                        next_player_idnum = game.get_next_player_idnum(s, eliminated)
                                        logging.info("351")

                                        for p in game.current_players:
                                            if next_player_idnum == p.idnum:
                                                game.current_player = p

                                        logging.info(f"357: eliminate = {eliminated}")
                                        for eliminated_player in eliminated:
                                            # remove player from live_idnums list
                                            if eliminated_player in game.live_idnums:
                                                game.live_idnums.remove(eliminated_player)
                                            # send out elimination status to all players
                                            for a in game.all_connections:
                                                game.msg_queue[a.connection].put(
                                                    tiles.MessagePlayerEliminated(eliminated_player).pack())

                                            for i in range(len(game.current_players)):
                                                if game.current_players[i].idnum == eliminated_player:
                                                    for a in game.all_connections:
                                                        elim_player = game.current_players[i]
                                                    # remove from players list and add back to waiting list
                                                    game.waiting_clients_for_next_game.append(game.current_players[i])

                                            logging.info(f"401: Current Players = {game.current_players}")
                                            for p in game.current_players:
                                                if p.idnum == eliminated_player:
                                                    logging.info(f"404: Current Player removed = {p.idnum}")
                                                    game.current_players.remove(p)

                                        if not game.if_game_is_over():
                                            if eliminated and (
                                                    len(game.all_players_to_start_current_game) < (MAX_PLAYERS - 1)):
                                                game.replace_eliminated_players()

                                        for a in game.all_connections:
                                            game.msg_queue[a.connection].put(
                                                tiles.MessagePlayerTurn(next_player_idnum).pack())

                        if s not in game.outputs:
                            game.outputs.append(s)
                    else:
                        pass

                else:
                    # if no data received, socket closed and removed from all i/o and msg_queue
                    # if the client has disconnected before a game started

                    # if the connection isn't a spectator, then assume the connection has been closed
                    for p in game.current_players:
                        if p.connection == s:
                            if p.idnum not in game.all_players_eliminated_from_game:
                                game.all_connections.remove(p)
                                logging.info(f'Client {s.getpeername()} disconnected')
                                logging.info("413")
                                # notify everyone that player has disconnected
                                for a in game.all_connections:
                                    game.msg_queue[a.connection].put(tiles.MessagePlayerEliminated(p.idnum).pack())

                                # if they are a player but not the current player, just remove the player
                                if s != game.current_player.connection:
                                    game.current_players.remove(p)
                                    game.live_idnums.remove(p.idnum)
                                    logging.info(f"498 Number of Players: {len(game.current_players)}")
                                # if the disconnection was the current player, send out next player's turn information
                                else:
                                    logging.info("485")
                                    next_player_idnum = game.get_next_player_idnum(s, [p.idnum])
                                    for n in game.current_players:
                                        if next_player_idnum == n.idnum:
                                            game.current_player = n
                                    game.current_players.remove(p)
                                    game.live_idnums.remove(p.idnum)
                                    for r in game.current_players:
                                        game.msg_queue[r.connection].put(
                                            tiles.MessagePlayerTurn(game.current_player.idnum).pack())

                                # if the game isn't over and MAX_PLAYERS haven't already played in current game,
                                # then replace disconnected player
                                if not game.if_game_is_over():
                                    if len(game.all_players_to_start_current_game) < MAX_PLAYERS:
                                        game.replace_eliminated_players()
                                        logging.info("511")

                                if s in game.outputs:
                                    logging.info("514")
                                    game.outputs.remove(s)
                                game.inputs.remove(s)

                                s.close()
                                del game.msg_queue[s]

        except Exception as ex:
            logging.warning(ex.args)

    # Handle outputs
    for s in writable:
        if s in game.msg_queue:
            try:
                next_msg = game.msg_queue[s].get_nowait()
            except queue.Empty:
                # No messages waiting so stop checking for writability.
                if game.if_game_is_over():
                    game.msg_queue[game.current_players[0].connection].put(
                        tiles.MessagePlayerTurn(game.current_players[0].idnum).pack())
                    time.sleep(5.0)
                    game.game_started = False
                    game.start_another_game()
            else:
                try:
                    sent = s.send(next_msg)
                except Exception as e:
                    # if we were unable to write to the socket, assume that it has disconnected
                    # remove the socket from all lists
                    print('Error: {}'.format(e))
                    # if connection was a current player
                    for p in game.current_players:
                        if p.connection == s:
                            game.all_connections.remove(p)
                            logging.info("413")
                            # notify everyone that player has disconnected
                            for a in game.all_connections:
                                game.msg_queue[a.connection].put(tiles.MessagePlayerEliminated(p.idnum).pack())

                            if s == game.current_player.connection:
                                logging.info("419")

                                # if there are more than two players on the board, find the next player
                                if len(game.live_idnums) > 2:
                                    logging.info("423")

                                    next_player_idnum = game.get_next_player_idnum(s, [p.idnum])
                                    for n in game.current_players:
                                        if next_player_idnum == n.idnum:
                                            game.current_player = n

                                logging.info("430")
                                game.current_players.remove(p)
                                game.live_idnums.remove(p.idnum)
                                if len(game.waiting_clients) > 0:
                                    game.replace_eliminated_players()
                                    logging.info("435")
                                # check whether game is over, if still going, notify who is the next player
                                logging.info("454")
                                if not game.if_game_is_over():
                                    for r in game.current_players:
                                        game.msg_queue[r.connection].put(
                                            tiles.MessagePlayerTurn(game.current_player.idnum).pack())

                        else:
                            for a in game.all_connections:
                                if a.connection == s:
                                    game.all_connections.remove(a)
                                    game.waiting_clients.remove(a)
                                    # notify everyone that player has disconnected
                                    for c in game.all_connections:
                                        game.msg_queue[c.connection].put(tiles.MessagePlayerLeft(a.idnum).pack())
                                    for r in game.current_players:
                                        game.msg_queue[r.connection].put(
                                            tiles.MessagePlayerTurn(game.current_player.idnum).pack())

                    if s in game.outputs:
                        logging.info("432")
                        game.outputs.remove(s)
                    game.inputs.remove(s)

                    s.close()
                    del game.msg_queue[s]

    for s in errors:
        if s in game.outputs:
            game.outputs.remove(s)
        game.inputs.remove(s)

        s.close()
        del game.msg_queue[s]