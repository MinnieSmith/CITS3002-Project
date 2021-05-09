# Imports
import logging
import multiprocessing
import socket
import select
import queue
import tiles
import random
import time
from threading import Timer

MAX_PLAYERS = 2


class Player:
    def __init__(self, connection: socket, idnum: int, address: str):
        self.connection = connection
        self.idnum = idnum
        self.host, self.port = address
        self.name = '{}:{}'.format(self.host, self.port)

def create_client_socket(s, idnum):
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

    # add Player to connections and waiting lists
    all_connections.append(new_player)
    connected_clients_waiting_to_play.append(new_player)

    return idnum, new_player

def enough_players():
    return len(players) == MAX_PLAYERS


def not_enough_players():
    return len(players) < MAX_PLAYERS


def enough_clients_to_start_a_game():
    return len(connected_clients_waiting_to_play) >= MAX_PLAYERS


def shuffle_players(client_list):
    random.shuffle(client_list)


def get_next_player_idnum(client_socket, eliminated_list, players):
    logging.info("Getting next player idnum")
    current_index = 0
    current_idnum = 0
    number_of_players = len(players)

    for p in range(len(players)):
        if players[p].connection == client_socket:
            current_idnum = players[p].idnum
            current_index = p

    else:
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


def if_game_is_over():
    return game_started and (len(players) == 1)


def start_new_game():
    shuffle_players(connected_clients_waiting_to_play)
    live_idnums.clear()
    logging.info("105: Live idnums cleared")

    if not_enough_players():
        # add waiting clients to players list and live_idnums
        for i in range(MAX_PLAYERS):
            new_player = connected_clients_waiting_to_play[i]
            players.append(new_player)
            live_idnums.append(new_player.idnum)
        logging.info(f'Players list has {len(players)} players')

    # reset idnums of all players
    for a in all_connections:
        for i in all_connections:
            msg_queue[a.connection].put(tiles.MessagePlayerLeft(i.idnum).pack())

    # notify all clients players idnums
    for a in all_connections:
        for i in players:
            msg_queue[a.connection].put(tiles.MessagePlayerJoined(i.name, i.idnum).pack())

        # notify players that the game is starting
        msg_queue[a.connection].put(tiles.MessageGameStart().pack())

    # notify all clients spectator idnums
    for a in all_connections:
        for c in connected_clients_waiting_to_play:
            msg_queue[a.connection].put(tiles.MessagePlayerJoined(c.name, c.idnum).pack())


    for p in players:
        # deal hand
        for _ in range(tiles.HAND_SIZE):
            tileid = tiles.get_random_tileid()
            msg_queue[p.connection].put(tiles.MessageAddTileToHand(tileid).pack())
        # send all players turn info:
        msg_queue[p.connection].put(tiles.MessagePlayerTurn(players[0].idnum).pack())
        # logging.info(f'Player {p.idnum} has been informed that its Player {players[0].idnum} turn!')

    for p in players:
        connected_clients_waiting_to_play.remove(p)

    # reset the board
    board.reset()



logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

# create the socket for the server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ('', 30021)
server.bind(server_address)
server.setblocking(False)
logging.info(f'Listening on port {server.getsockname()}')
server.listen(5)

# create the input and output list for the select function
inputs = [server]
outputs = []
msg_queue = {}

idnum = 0
live_idnums = []
connected_clients_waiting_to_play = []
all_connections = []
players = []
current_player = None
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
                idnum, new_player = create_client_socket(s, idnum)

                # if game hasn't started check if there are enough players to start a game:
                if not game_started and enough_clients_to_start_a_game():
                    for a in all_connections:
                        msg_queue[a.connection].put(tiles.MessageCountdown().pack())
                    time.sleep(5.0)
                    start_new_game()
                    current_player = players[0]
                    game_started = True

                # if game has started, send the new connection, the player's idnums
                if game_started:
                    for i in players:
                        msg_queue[new_player.connection].put(tiles.MessagePlayerJoined(i.name, i.idnum).pack())



            else:
                data = s.recv(4096)
                if data:
                    if s == current_player.connection:
                        buffer.extend(data)
                        msg, consumed = tiles.read_message_from_bytearray(buffer)
                        # logging.info(f'Message Attribute ID = {msg.idnum}')

                        if consumed > 0:
                            buffer = buffer[consumed:]

                            # sent by the player to put a tile onto the board (in all turns except
                            # their second)
                            if isinstance(msg, tiles.MessagePlaceTile):
                                # logging.info(f'202: Player {msg.idnum} has place tileid = {msg.tileid}')
                                if board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):
                                    # notify player, placement was successful
                                    # logging.info('205: tile placement successful!')
                                    for a in all_connections:
                                        msg_queue[a.connection].put(msg.pack())

                                    # check for token movement
                                    positionupdates, eliminated = board.do_player_movement(live_idnums)
                                    # logging.info(f'Move player token if possible for live_idnum: {live_idnums}')
                                    # logging.info(f'Position Updates: {positionupdates}')

                                    # TODO: check if position updates and eliminated need to be sent to all clients!
                                    for msg in positionupdates:
                                        for p in players:
                                            msg_queue[p.connection].put(msg.pack())

                                    if len(live_idnums) > (len(eliminated) + 1):
                                        next_player_idnum = get_next_player_idnum(s, eliminated, players)

                                        for p in players:
                                            if next_player_idnum == p.idnum:
                                                current_player = p

                                    for eliminated_player in eliminated:
                                        # remove player from live_idnums list
                                        if eliminated_player in live_idnums:
                                            live_idnums.remove(eliminated_player)

                                        # send out elimination status to all players
                                        for p in players:
                                            msg_queue[p.connection].put(
                                                tiles.MessagePlayerEliminated(eliminated_player).pack())

                                        for i in range(len(players)):
                                            if players[i].idnum == eliminated_player:
                                                # remove from players list and add back to waiting list
                                                connected_clients_waiting_to_play.append(players[i])

                                        for p in players:
                                            if p.idnum == eliminated_player:
                                                players.remove(p)

                                    if not if_game_is_over():
                                        # start next turn
                                        for p in players:
                                            msg_queue[p.connection].put(tiles.MessagePlayerTurn(next_player_idnum).pack())

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

                                        if len(live_idnums) > (len(eliminated) + 1):
                                            next_player_idnum = get_next_player_idnum(s, eliminated, players)
                                            for p in players:
                                                if next_player_idnum == p.idnum:
                                                    current_player = p

                                        logging.info(f'299 Current Player = {current_player}')
                                        for eliminated_player in eliminated:
                                            # remove player from live_idnums list
                                            if eliminated_player in live_idnums:
                                                live_idnums.remove(eliminated_player)

                                            # send out elimination status to all players
                                            for p in players:
                                                msg_queue[p.connection].put(
                                                    tiles.MessagePlayerEliminated(eliminated_player).pack())

                                            for i in range(len(players)):
                                                if players[i].idnum == eliminated_player:
                                                    # remove from players list and add back to waiting list
                                                    connected_clients_waiting_to_play.append(players[i])

                                            for p in players:
                                                if p.idnum == eliminated_player:
                                                    players.remove(p)

                                            for c in connected_clients_waiting_to_play:
                                                connected_idnums = []
                                                connected_idnums.append(c.idnum)

                                        if not if_game_is_over():
                                            # start next turn
                                            # try just sending back the same idnum to all clients:
                                            for p in players:
                                                msg_queue[p.connection].put(
                                                    tiles.MessagePlayerTurn(next_player_idnum).pack())

                        if s not in outputs:
                            outputs.append(s)

                    else:
                        pass
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
            # No messages waiting so stop checking for writability.
            if if_game_is_over():
                time.sleep(5.0)
                logging.info("257: game over == True")
                connected_clients_waiting_to_play.append(players[0])
                players.clear()
                live_idnums.clear()
                game_started = False
                logging.info(f"329: Players = {len(players)}")
                if enough_clients_to_start_a_game():

                    for a in all_connections:
                        msg_queue[a.connection].put(tiles.MessageCountdown().pack())
                    # t = Timer(5.0, start_new_game)
                    # t.start()
                    start_new_game()
                    current_player = players[0]
                    logging.info(f'336: current player = {current_player.idnum}')
                    logging.info('Timer started')
                    game_started = True

        else:
            # logging.info(f'Sending {next_msg.decode("utf-8")} to {s.getpeername()}')
            s.send(next_msg)