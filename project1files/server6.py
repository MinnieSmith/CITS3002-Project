#Imports
import logging
import multiprocessing
import socket
import select
import queue
import tiles
import random

MAX_PLAYERS = 4

class Player:
    def __init__(self, connection: socket, idnum: int, address: str):
        self.connection = connection
        self.idnum = idnum
        self.host, self.port = address
        self.name = '{}:{}'.format(self.host, self.port)

def enough_connected_clients():
    return len(connected_clients) == MAX_PLAYERS


def enough_players():
    return len(players) == MAX_PLAYERS

def not_enough_players():
    return len(connected_clients) < MAX_PLAYERS

def shuffle_players(client_list):
    random.shuffle(client_list)

def game_end():
    return len(players) == 1



def get_next_player_idnum(client_socket, eliminated_list):
    logging.info("Getting next player idnum")
    current_index = 0
    current_idnum = 0
    number_of_players = len(players)

    for p in range(len(players)):
        if players[p].connection == client_socket:
            current_idnum = players[p].idnum
            current_index = p

    if number_of_players == 1:
        return current_idnum

    if current_idnum in eliminated_list:
        next_index = current_index
    else:
        next_index = (current_index + 1) % number_of_players

    while players[next_index].idnum in eliminated_list:
        next_index = next_index + 1 % number_of_players

    next_idnum = players[next_index].idnum

    logging.info(f'Next Player Idnum = {next_idnum}')
    return next_idnum


def find_connection_for_idnum(idnum):
    for p in players:
        if p.idnum == idnum:
            return p.connection

logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s',datefmt='%H:%M:%S', level=logging.DEBUG)


# create the socket for the server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ('', 30021)
server.bind(server_address)
server.setblocking(False)
logging.info(f'Listening on port {server.getsockname()}')
server.listen(10)

# create the input and output list for the select function
inputs = [server]
outputs = []
msg_queue = {}

idnum = 0
live_idnums = []
connected_clients = []
players = []
game_started = False
board = tiles.Board()
buffer = bytearray()

while True:
    # must give a time out value to select or else it will act in a blocking manner
    readable, writable, errors = select.select(inputs, outputs, inputs, 0.5)


    for s in readable:
        try:
            # the server only listens for connections and creates client sockets
            if s == server:
                # create a client socket and add it inputs and outputs list
                connection, client_address = s.accept()
                connection.setblocking(False)
                inputs.append(connection)
                outputs.append(connection)
                logging.info(f'Client Connection: {client_address}')

                # send new connection welcome message
                msg_queue[connection] = queue.Queue()
                msg_queue[connection].put(tiles.MessageWelcome(idnum).pack())

                # create new player and add it to players list
                new_player = Player(connection, idnum, client_address)
                idnum += 1

                # add Player to connected clients list
                connected_clients.append(new_player)

                logging.info(f'Number of Connected clients = {len(connected_clients)}')
                # check if there are enough connected clients to start a game
                if not game_started and enough_connected_clients():
                    # if there is enough, randomize and add MAX_PLAYERS to players list
                    shuffle_players(connected_clients)
                    for p in range(MAX_PLAYERS):
                        active_player = connected_clients[p]
                        players.append(active_player)
                        live_idnums.append(active_player.idnum)
                    logging.info(f'Number of players = {len(players)}')

                    # notify all clients of who the players are in this game!

                    for p in players:
                        for i in players:
                            msg_queue[p.connection].put(tiles.MessagePlayerJoined(i.name, i.idnum).pack())
                            logging.info(f'Notify player {p.idnum} of {i.idnum} connecting')
                    for c in connected_clients:
                        for p in players:
                            msg_queue[c.connection].put(tiles.MessagePlayerJoined(p.name, p.idnum).pack())
                            logging.info(f'Notify Clients {c.idnum} of {p.idnum} connecting')

                    # start game and deal hand
                # if not game_started:
                    for p in players:
                        msg_queue[p.connection].put(tiles.MessageGameStart().pack())
                        # logging.info(f'Player {p.idnum} has been informed that game started')

                        for _ in range(tiles.HAND_SIZE):
                            tileid = tiles.get_random_tileid()
                            msg_queue[p.connection].put(tiles.MessageAddTileToHand(tileid).pack())
                        # send all players turn info:
                        msg_queue[p.connection].put(tiles.MessagePlayerTurn(players[0].idnum).pack())
                        # logging.info(f'Player {p.idnum} has been informed that its Player {players[0].idnum} turn!')
                    game_started = True
            else:
                data = s.recv(4096)
                if data:
                    # logging.info(f'Data Received added to msg queue from {s.getpeername()}')
                    # TODO: parse data here and add it to the appropriate socket queue
                    buffer.extend(data)
                    msg, consumed = tiles.read_message_from_bytearray(buffer)
                    logging.info(f'Message Attribute ID = {msg.idnum}')

                    if consumed > 0:
                        buffer = buffer[consumed:]
                        # logging.info(f'Received message: "{msg}" \nfrom {s.getpeername}')

                        # sent by the player to put a tile onto the board (in all turns except
                        # their second)
                        if isinstance(msg, tiles.MessagePlaceTile):
                            if board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):
                                # notify player, placement was successful
                                for p in players:
                                    msg_queue[p.connection].put(msg.pack())
                                # notify all connected clients
                                for c in connected_clients:
                                    msg_queue[c.connection].put(msg.pack())

                                # check for token movement
                                positionupdates, eliminated = board.do_player_movement(live_idnums)

                                for msg in positionupdates:
                                    # notify all players
                                    for p in players:
                                        msg_queue[p.connection].put(msg.pack())
                                    # notify all connected clients
                                    for c in connected_clients:
                                        msg_queue[c.connection].put(msg.pack())

                                for eliminated_player in eliminated:
                                    # send out elimination status to all players
                                    for p in players:
                                        msg_queue[p.connection].put(tiles.MessagePlayerEliminated(eliminated_player).pack())
                                    # send out elimination status to all connected clients
                                    for c in connected_clients:
                                        msg_queue[c.connection].put(
                                            tiles.MessagePlayerEliminated(eliminated_player).pack())

                                # start next turn
                                # try just sending back the same idnum to all clients:
                                for p in players:
                                    msg_queue[p.connection].put(tiles.MessagePlayerTurn(get_next_player_idnum(s, eliminated)).pack())

                                # update player lists
                                for eliminated_player in eliminated:
                                    # remove player from live_idnums list
                                    if eliminated_player in live_idnums:
                                        live_idnums.remove(eliminated_player)
                                    # remove player from players list
                                    for p in players:
                                        if p.idnum == eliminated_player:
                                            players.remove(p)
                                            if game_end():
                                                game_started = False


                                # pickup a new tile
                                tileid = tiles.get_random_tileid()
                                msg_queue[s].put(tiles.MessageAddTileToHand(tileid).pack())



                        # sent by the player in the second turn, to choose their token's
                        # starting path
                        elif isinstance(msg, tiles.MessageMoveToken):
                            if not board.have_player_position(msg.idnum):
                                if board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
                                    # check for token movement
                                    positionupdates, eliminated = board.do_player_movement(live_idnums)

                                    for msg in positionupdates:
                                        for p in players:
                                            msg_queue[p.connection].put(msg.pack())
                                        # notify all connected clients
                                        for c in connected_clients:
                                            msg_queue[c.connection].put(msg.pack())

                                    for eliminated_player in eliminated:
                                        # send out elimination status to all players
                                        for p in players:
                                            msg_queue[p.connection].put(
                                                tiles.MessagePlayerEliminated(eliminated_player).pack())
                                        # send out elimination status to all connected clients
                                        for c in connected_clients:
                                            msg_queue[c.connection].put(
                                                tiles.MessagePlayerEliminated(eliminated_player).pack())

                                    # start next turn
                                    # try just sending back the same idnum to all clients:
                                    for p in players:
                                        msg_queue[p.connection].put(
                                            tiles.MessagePlayerTurn(get_next_player_idnum(s, eliminated)).pack())

                                    # update player lists
                                    for eliminated_player in eliminated:
                                        # remove player from live_idnums list
                                        if eliminated_player in live_idnums:
                                            live_idnums.remove(eliminated_player)
                                        # remove player from players list
                                        for p in players:
                                            if p.idnum == eliminated_player:
                                                players.remove(p)
                                                if game_end():
                                                    game_started = False

                    if s not in outputs:
                        outputs.append(s)
                else:
                    # if no data received, socket closed and removed from all i/o and msg_queues
                    logging.info(f'Client {s.getpeername()} disconnected')
                    if s in outputs:
                        outputs.remove(s)
                    inputs.remove(s)
                    s.close()
                    del msg_queue[s]
        except Exception as ex:
            logging.warning(ex.args)

    # Handle outputs
    for s in writable:
        try:
            next_msg = msg_queue[s].get_nowait()
        except queue.Empty:
            pass
            # No messages waiting so stop checking for writability.
            # logging.info(f'Output queue for {s.getpeername()} is empty - removed from outputs')
            # TODO: for now don't remove s from output, will do it at some other stage!!!
            # outputs.remove(s)
        else:
            # logging.info(f'Sending {next_msg.decode("utf-8")} to {s.getpeername()}')
            s.send(next_msg)



