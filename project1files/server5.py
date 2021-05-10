# Imports
import logging
import multiprocessing
import socket
import select
import queue
import tiles
import random
import time

MAX_PLAYERS = 2


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
        self.players = []
        self.current_player = None
        self.game_started = False
        self.board = tiles.Board()

    def create_client_socket(self, socket, inputs, outputs, msg_queue):
        connection, client_address = socket.accept()
        connection.setblocking(False)
        inputs.append(connection)
        outputs.append(connection)
        logging.info(f'38: Client Connection: {client_address}')

        # send new connection welcome message
        msg_queue[connection] = queue.Queue()
        msg_queue[connection].put(tiles.MessageWelcome(self.idnum).pack())
        logging.info("43")

        # create new player and add it to players list
        new_player = Player(connection, self.idnum, client_address)
        self.idnum += 1

        logging.info("48")

        # add Player to connections and waiting lists
        self.all_connections.append(new_player)
        self.waiting_clients.append(new_player)

        logging.info("55")
        return new_player, inputs, outputs, msg_queue

    def enough_players(self):
        return len(self.players) == MAX_PLAYERS

    def number_of_players(self):
        return len(self.players)

    def not_enough_players(self):
        return len(self.players) < MAX_PLAYERS

    def enough_clients_to_start_a_game(self):
        return len(self.waiting_clients) >= MAX_PLAYERS

    def shuffle_players(self):
        return random.shuffle(self.waiting_clients)

    def get_next_player_idnum(self, client_socket, eliminated_list):
        logging.info("Getting next player idnum")
        current_index = 0
        current_idnum = 0
        number_of_players = len(self.players)
        for p in range(len(self.players)):
            if self.players[p].connection == client_socket:
                current_idnum = self.players[p].idnum
                current_index = p

        if len(self.live_idnums) > (len(eliminated_list) + 1):

            if current_idnum in eliminated_list:
                next_index = current_index
            else:
                next_index = (current_index + 1) % number_of_players

            while self.players[next_index].idnum in eliminated_list:
                next_index = next_index + 1 % number_of_players

            next_idnum = self.players[next_index].idnum
            logging.info(f'91: Next Player Idnum = {next_idnum}')
            return next_idnum
        else:
            return current_idnum


    def find_connection_for_idnum(self, idnum):
        for a in self.all_connections:
            if a.idnum == idnum:
                return a.connection

    def if_game_is_over(self):
        return self.game_started and (len(self.players) == 1)

    def start_new_game(self):
        self.shuffle_players()
        self.live_idnums.clear()
        logging.info("105: Live idnums cleared")

        if self.not_enough_players():
            # add waiting clients to players list and live_idnums
            for i in range(MAX_PLAYERS):
                new_player = self.waiting_clients[i]
                self.players.append(new_player)
                self.live_idnums.append(new_player.idnum)
            logging.info(f'Players list has {self.number_of_players()} players')

        # reset idnums of all players
        for a in self.all_connections:
            for i in self.all_connections:
                msg_queue[a.connection].put(tiles.MessagePlayerLeft(i.idnum).pack())

        # notify all clients players idnums
        for a in self.all_connections:
            for i in self.players:
                msg_queue[a.connection].put(tiles.MessagePlayerJoined(i.name, i.idnum).pack())

            # notify players that the game is starting
            msg_queue[a.connection].put(tiles.MessageGameStart().pack())

        # notify all clients spectator idnums
        for a in self.all_connections:
            for c in self.waiting_clients:
                msg_queue[a.connection].put(tiles.MessagePlayerJoined(c.name, c.idnum).pack())

        for p in self.players:
            # deal hand
            for _ in range(tiles.HAND_SIZE):
                tileid = tiles.get_random_tileid()
                msg_queue[p.connection].put(tiles.MessageAddTileToHand(tileid).pack())
            # send all players turn info:
            msg_queue[p.connection].put(tiles.MessagePlayerTurn(self.players[0].idnum).pack())
            # logging.info(f'Player {p.idnum} has been informed that its Player {players[0].idnum} turn!')

        for p in self.players:
            self.waiting_clients.remove(p)

        # reset the board
        self.board.reset()
        self.current_player = self.players[0]
        self.game_started = True



logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ('', 30021)
server.bind(server_address)
server.setblocking(False)
logging.info(f'Listening on port {server.getsockname()}')
server.listen(5)

game = Game()

inputs = [server]
outputs = []
msg_queue = {}
buffer = bytearray()

while True:
    # must give a time out value to select or else it will act in a blocking manner
    readable, writable, errors = select.select(inputs, outputs, inputs, 1.0)

    for s in readable:
        try:
            # the server only listens for connections and creates client sockets
            if s == server:
                # create a client socket and add it inputs and outputs list
                new_player, inputs, outputs, msg_queue = game.create_client_socket(s, inputs, outputs, msg_queue)
                logging.info("181")
                # if game hasn't started check if there are enough players to start a game:
                if not game.game_started and game.enough_clients_to_start_a_game():
                    for a in game.all_connections:
                        msg_queue[a.connection].put(tiles.MessageCountdown().pack())
                    time.sleep(5.0)
                    game.start_new_game()
                logging.info("188")
                # if game has started, send the new connection, the player's idnums
                if game.game_started:
                    for i in game.players:
                        msg_queue[new_player.connection].put(tiles.MessagePlayerJoined(i.name, i.idnum).pack())
                logging.info("193")
            else:
                data = s.recv(4096)
                if data:
                    if s == game.current_player.connection:
                        buffer.extend(data)
                        msg, consumed = tiles.read_message_from_bytearray(buffer)
                        # logging.info(f'Message Attribute ID = {msg.idnum}')

                        if consumed > 0:
                            buffer = buffer[consumed:]

                            # sent by the player to put a tile onto the board (in all turns except
                            # their second)
                            if isinstance(msg, tiles.MessagePlaceTile):
                                # logging.info(f'202: Player {msg.idnum} has place tileid = {msg.tileid}')
                                if game.board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):
                                    # notify player, placement was successful
                                    # logging.info('205: tile placement successful!')
                                    for a in game.all_connections:
                                        msg_queue[a.connection].put(msg.pack())

                                    # check for token movement
                                    positionupdates, eliminated = game.board.do_player_movement(game.live_idnums)

                                    for msg in positionupdates:
                                        for p in game.players:
                                            msg_queue[p.connection].put(msg.pack())

                                    next_player_idnum = game.get_next_player_idnum(s, eliminated)

                                    for p in game.players:
                                        if next_player_idnum == p.idnum:
                                            game.current_player = p

                                    for eliminated_player in eliminated:
                                        # remove player from live_idnums list
                                        if eliminated_player in game.live_idnums:
                                            game.live_idnums.remove(eliminated_player)

                                        # send out elimination status to all players
                                        for p in game.players:
                                            msg_queue[p.connection].put(
                                                tiles.MessagePlayerEliminated(eliminated_player).pack())

                                        for i in range(len(game.players)):
                                            if game.players[i].idnum == eliminated_player:
                                                # remove from players list and add back to waiting list
                                                game.waiting_clients.append(game.players[i])

                                        for p in game.players:
                                            if p.idnum == eliminated_player:
                                                game.players.remove(p)

                                    if not game.if_game_is_over():
                                        # start next turn
                                        for p in game.players:
                                            msg_queue[p.connection].put(
                                                tiles.MessagePlayerTurn(next_player_idnum).pack())

                                        # pickup a new tile
                                        tileid = tiles.get_random_tileid()
                                        msg_queue[s].put(tiles.MessageAddTileToHand(tileid).pack())

                            # sent by the player in the second turn, to choose their token's
                            # starting path
                            elif isinstance(msg, tiles.MessageMoveToken):
                                if not game.board.have_player_position(msg.idnum):
                                    if game.board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
                                        # check for token movement
                                        positionupdates, eliminated = game.board.do_player_movement(game.live_idnums)

                                        for msg in positionupdates:
                                            for p in game.players:
                                                msg_queue[p.connection].put(msg.pack())

                                        next_player_idnum = game.get_next_player_idnum(s, eliminated)

                                        for p in game.players:
                                            if next_player_idnum == p.idnum:
                                                game.current_player = p

                                        for eliminated_player in eliminated:
                                            # remove player from live_idnums list
                                            if eliminated_player in game.live_idnums:
                                                game.live_idnums.remove(eliminated_player)

                                            # send out elimination status to all players
                                            for p in game.players:
                                                msg_queue[p.connection].put(
                                                    tiles.MessagePlayerEliminated(eliminated_player).pack())

                                            for i in range(len(game.players)):
                                                if game.players[i].idnum == eliminated_player:
                                                    # remove from players list and add back to waiting list
                                                    game.waiting_clients.append(game.players[i])

                                            for p in game.players:
                                                if p.idnum == eliminated_player:
                                                    game.players.remove(p)

                                            for c in game.waiting_clients:
                                                connected_idnums = [c.idnum]

                                        if not game.if_game_is_over():
                                            # start next turn
                                            # try just sending back the same idnum to all clients:
                                            for p in game.players:
                                                msg_queue[p.connection].put(
                                                    tiles.MessagePlayerTurn(next_player_idnum).pack())

                        if s not in outputs:
                            outputs.append(s)

                    else:
                        pass
                else:
                    # if no data received, socket closed and removed from all i/o and msg_queues
                    logging.info(f'Client {s.getpeername()} disconnected')
                    for p in game.players:
                        if p.connection == s:
                            if s == game.current_player.connection:
                                if len(game.live_idnums) > 2:
                                    next_player_idnum = game.get_next_player_idnum(s, [p.idnum])

                                    for n in game.players:
                                        if next_player_idnum == n.idnum:
                                            game.current_player = n
                                game.players.remove(p)
                                game.all_connections.remove(p)
                                game.live_idnums.remove(p.idnum)
                                for r in game.players:
                                    msg_queue[r.connection].put(tiles.MessagePlayerTurn(game.current_player.idnum).pack())
                                for a in game.all_connections:
                                    msg_queue[a.connection].put(tiles.MessagePlayerEliminated(p.idnum).pack())
                                    msg_queue[a.connection].put(tiles.MessagePlayerLeft(p.idnum).pack())
                    if s in outputs:
                        outputs.remove(s)
                    inputs.remove(s)

                    s.close()
                    del msg_queue[s]

        except Exception as ex:
            logging.warning(ex.args)

    # Handle outputs
    for s in writable:
        if s in msg_queue:
            try:
                next_msg = msg_queue[s].get_nowait()
            except queue.Empty:
                # No messages waiting so stop checking for writability.
                if game.if_game_is_over():
                    time.sleep(5.0)
                    logging.info("257: game over == True")
                    game.waiting_clients.append(game.players[0])
                    game.players.clear()
                    game.live_idnums.clear()
                    game_started = False
                    logging.info(f"329: Players = {len(game.players)}")
                    if game.enough_clients_to_start_a_game():
                        for a in game.all_connections:
                            msg_queue[a.connection].put(tiles.MessageCountdown().pack())
                        # t = Timer(10.0, start_new_game)
                        # t.start()
                        game.start_new_game()
            else:
                s.send(next_msg)


