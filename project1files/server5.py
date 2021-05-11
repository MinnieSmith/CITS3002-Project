# Imports
import logging
import multiprocessing
import socket
import select
import queue
import tiles
import random
import time

MAX_PLAYERS = 3


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
        self.all_connections = []
        self.current_players = []
        self.all_players_that_have_played = []
        self.current_player = None
        self.game_started = False
        self.board = tiles.Board()
        self.tile_positions_msg = []
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
        return len(self.current_players) == MAX_PLAYERS

    def number_of_players(self):
        return len(self.current_players)

    def not_enough_players(self):
        return len(self.current_players) < MAX_PLAYERS

    def enough_clients_to_start_a_game(self):
        return len(self.waiting_clients) >= MAX_PLAYERS

    def shuffle_players(self):
        return random.shuffle(self.waiting_clients)

    def get_next_player_idnum(self, client_socket, eliminated_list):
        logging.info("80: Getting next player idnum")
        current_index = 0
        current_idnum = 0
        number_of_players = len(self.current_players)
        for p in range(len(self.current_players)):
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
        self.shuffle_players()
        self.live_idnums.clear()
        logging.info("105: Live idnums cleared")

        if self.not_enough_players():
            # add waiting clients to players list and live_idnums
            for i in range(MAX_PLAYERS):
                new_player = self.waiting_clients[i]
                self.current_players.append(new_player)
                self.all_players_that_have_played.append(new_player)
                self.live_idnums.append(new_player.idnum)

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

        for p in self.current_players:
            self.waiting_clients.remove(p)

        time.sleep(5.0)
        # reset the board
        self.board.reset()
        self.current_player = self.current_players[0]
        self.game_started = True

    def start_another_game(self):
        time.sleep(5.0)
        logging.info("336: game over == True")
        self.waiting_clients.append(self.current_players[0])
        logging.info(f"338: waiting clients = {self.waiting_clients[0].idnum}")
        self.current_players.clear()
        self.live_idnums.clear()
        self.game_started = False
        logging.info(f"341: Players = {len(self.current_players)}")
        if self.enough_clients_to_start_a_game():
            for a in self.all_connections:
                game.msg_queue[a.connection].put(tiles.MessageCountdown().pack())
            self.start_new_game()

    def replace_eliminated_players(self, eliminated_list):
        if not self.if_game_is_over():
            # check if players have been eliminated and add new players
            joining_players = []

            number_of_players_to_add = min(((MAX_PLAYERS - len(self.current_players)), len(self.waiting_clients)),
                                           len(eliminated_list))
            logging.info(f'177: players to add = {number_of_players_to_add}')

            # add player to the list and notify everyone
            if len(eliminated_list) > 0:
                self.shuffle_players()
                for i in range(number_of_players_to_add):
                    logging.info("179")
                    joining_player = self.waiting_clients.pop(0)
                    self.current_players.append(joining_player)
                    self.all_players_that_have_played.append(joining_player)
                    self.live_idnums.append(joining_player.idnum)
                    joining_players.append(joining_player)
                    logging.info(f" 191: Joining Player idnum = {joining_player.idnum}")

                # reset all turn positions
                for a in self.all_connections:
                    for p in self.current_players:
                        self.msg_queue[a.connection].put(tiles.MessagePlayerTurn(p.idnum).pack())

                # deal hand
                for j in joining_players:
                    for _ in range(tiles.HAND_SIZE):
                        tileid = tiles.get_random_tileid()
                        game.msg_queue[j.connection].put(tiles.MessageAddTileToHand(tileid).pack())

    def update_board_for_joining_clients(self, new_player):
        # if game has started, send the new connection, the player's idnums
        self.waiting_clients.append(new_player)
        for p in self.current_players:
            self.msg_queue[new_player.connection].put(tiles.MessagePlayerJoined(p.name, p.idnum).pack())
        logging.info("245")
        # notify all players that new client has joined
        for a in self.all_connections:
            self.msg_queue[a.connection].put(tiles.MessagePlayerJoined(new_player.name, new_player.idnum).pack())

        # notify the client of all player positions
        for p in self.current_players:
            self.msg_queue[new_player.connection].put(tiles.MessagePlayerTurn(p.idnum).pack())

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
server_address = ('', 30021)
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
                logging.info("233")
                # if game hasn't started check if there are enough players to start a game:
                if not game.game_started and game.enough_clients_to_start_a_game():
                    for a in game.all_connections:
                        game.msg_queue[a.connection].put(tiles.MessageCountdown().pack())
                    time.sleep(5.0)
                    game.start_new_game()
                logging.info("240")
                if game.game_started:
                    game.update_board_for_joining_clients(new_player)



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
                                    for msg in positionupdates:
                                        for a in game.all_connections:
                                            game.msg_queue[a.connection].put(msg.pack())

                                    next_player_idnum = game.get_next_player_idnum(s, eliminated)

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
                                                # remove from players list and add back to waiting list
                                                game.waiting_clients.append(game.current_players[i])

                                        for p in game.current_players:
                                            if p.idnum == eliminated_player:
                                                game.current_players.remove(p)

                                    game.replace_eliminated_players(eliminated)

                                    if not game.if_game_is_over():
                                        logging.info("306")
                                        # start next turn
                                        for a in game.all_connections:
                                            game.msg_queue[a.connection].put(
                                                tiles.MessagePlayerTurn(next_player_idnum).pack())

                                        # pickup a new tile
                                        tileid = tiles.get_random_tileid()
                                        game.msg_queue[s].put(tiles.MessageAddTileToHand(tileid).pack())

                            # sent by the player in the second turn, to choose their token's
                            # starting path
                            elif isinstance(msg, tiles.MessageMoveToken):
                                if not game.board.have_player_position(msg.idnum):
                                    if game.board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
                                        # check for token movement
                                        positionupdates, eliminated = game.board.do_player_movement(game.live_idnums)

                                        for msg in positionupdates:
                                            for a in game.all_connections:
                                                game.msg_queue[a.connection].put(msg.pack())
                                            game.tile_positions_msg.append(msg.pack())

                                        next_player_idnum = game.get_next_player_idnum(s, eliminated)

                                        for p in game.current_players:
                                            if next_player_idnum == p.idnum:
                                                game.current_player = p

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
                                                    # remove from players list and add back to waiting list
                                                    game.waiting_clients.append(game.current_players[i])

                                            for p in game.current_players:
                                                if p.idnum == eliminated_player:
                                                    game.current_players.remove(p)

                                            for c in game.waiting_clients:
                                                connected_idnums = [c.idnum]

                                        game.replace_eliminated_players(eliminated)
                                        if not game.if_game_is_over():
                                            # start next turn
                                            for a in game.all_connections:
                                                game.msg_queue[a.connection].put(
                                                    tiles.MessagePlayerTurn(next_player_idnum).pack())

                        if s not in game.outputs:
                            game.outputs.append(s)

                    else:
                        pass
                else:
                    # if no data received, socket closed and removed from all i/o and msg_queues
                    logging.info(f'Client {s.getpeername()} disconnected')
                    for p in game.current_players:
                        if p.connection == s:
                            # notify everyone that player has disconnected
                            for a in game.all_connections:
                                game.msg_queue[a.connection].put(tiles.MessagePlayerLeft(p.idnum).pack())

                            if s == game.current_player.connection:
                                # if there are more than two players on the board, find the next player
                                if len(game.live_idnums) > 2:
                                    next_player_idnum = game.get_next_player_idnum(s, [p.idnum])
                                    for n in game.current_players:
                                        if next_player_idnum == n.idnum:
                                            game.current_player = n

                                game.current_players.remove(p)
                                game.all_connections.remove(p)
                                game.live_idnums.remove(p.idnum)
                                game.replace_eliminated_players(p.idnum)

                                # check whether game is over, if still going, notify who is the next player
                                if not game.if_game_is_over():
                                    for r in game.current_players:
                                        game.msg_queue[r.connection].put(
                                            tiles.MessagePlayerTurn(game.current_player.idnum).pack())

                    if game.if_game_is_over():
                        game.game_started = False
                        game.start_another_game()

                    if s in game.outputs:
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
                    game.game_started = False
                    game.start_another_game()
            else:
                s.send(next_msg)
