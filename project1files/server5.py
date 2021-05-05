#Imports
import logging
import multiprocessing
import socket
import select
import queue
import tiles
import random

MAX_PLAYERS = 2

class Player:
    def __init__(self, connection: socket, idnum: int, address: str):
        self.connection = connection
        self.idnum = idnum
        self.host, self.port = address
        self.name = '{}:{}'.format(self.host, self.port)

def enough_players():
    return len(players) == MAX_PLAYERS

def not_enough_players():
    return len(players) < MAX_PLAYERS

logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s',datefmt='%H:%M:%S', level=logging.DEBUG)


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
players = []
game_started = False
board = tiles.Board()

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

                # check if enough players, if not add to players list
                if not_enough_players():
                    players.append(new_player)

                # if enough players, send all clients players list
                if enough_players():
                    for p in players:
                        for i in players:
                            msg_queue[p.connection].put(tiles.MessagePlayerJoined(i.name, i.idnum).pack())
                            logging.info(f"Client {p.idnum} was notified that player {i.idnum} is in the game")

                    # start game and deal hand
                    if not game_started:
                        for p in players:
                            msg_queue[p.connection].put(tiles.MessageGameStart().pack())
                            logging.info(f'Player {p.idnum} has been informed that game started')

                            for _ in range(tiles.HAND_SIZE):
                                tileid = tiles.get_random_tileid()
                                msg_queue[p.connection].put(tiles.MessageAddTileToHand(tileid).pack())
                            # send all players turn info:
                            msg_queue[p.connection].put(tiles.MessagePlayerTurn(players[0].idnum).pack())
                            logging.info(f'Player {p.idnum} has been informed that its Player {players[0].idnum} turn!')
                        game_started = True
            else:
                data = s.recv(4096)
                if data:
                    # logging.info(f'Data Received added to msg queue: {data}')
                    # TODO: parse data here and add it to the appropriate socket queue
                    msg_queue[s].put(data)
                    if s not in outputs:
                        outputs.append(s)
                else:
                    # if no data received, socket closed and removed from all i/o and msg_queues
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
            logging.info(f'Sending {next_msg} to {s.getpeername()}')
            s.send(next_msg)



