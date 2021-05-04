import socket
import logging
import select
import tiles
import multiprocessing


class Player():
    def __init__(self, connection: socket, idnum: int, address: str):
        self.conection = connection
        self.idnum = idnum
        self.address = address
        self.host, self.port = address
        self.turn = False
        self.initial_connection = True
        self.deal_hand = False
        self.selected_as_player = False
        self.name = '{}:{}'.format(self.host, self.port)
        self.msg = None


def add_clients_to_connected_list():
    potential_player = Player(connection, idnum, client_address)
    connected_clients.append(potential_player)
    outputs.append(potential_player.conection)
    logging.info(f'Client {potential_player.idnum} appended to connected clients list')


def send_connection_idnum_and_welcome():
    for c in connected_clients:
        c.conection.send(tiles.MessageWelcome(c.idnum).pack())
        logging.info(f'Server send tiles.MessageWelcome idnum = {c.idnum}')

def add_client_to_players_list():
        new_player = connected_clients.pop(0)
        players.append(new_player)
        live_idnums.append(new_player.idnum)
        new_player.selected_as_player = True
        new_player.conection.setblocking(False)
        logging.info(f'Initial connection player = {new_player.idnum}')
        # connection added to the list of sockets to monitor for input
        inputs.append(new_player.conection)
        logging.info(f'Player {new_player.idnum} appended to players list')
        outputs.append(new_player.conection)
        logging.info(f'Player {new_player.idnum} added to outputs list')
        new_player.selected_as_player = True


def start_game():
    for player in players:
        player.conection.send(tiles.MessagePlayerJoined(player.name, player.idnum).pack())
        logging.info(f'Player {player.idnum} has joined the game')
        player.conection.send(tiles.MessageGameStart().pack())

        for _ in range(tiles.HAND_SIZE):
            tileid = tiles.get_random_tileid()
            player.conection.send(tiles.MessageAddTileToHand(tileid).pack())

        player.conection.send(tiles.MessagePlayerTurn(player.idnum).pack())
        outputs.remove(player.conection)

def player_moves(player: Player):

    if isinstance(player.msg, tiles.MessagePlaceTile):
        if board.set_tile(player.msg.x, player.msg.y, player.msg.tileid, player.msg.rotation, player.msg.idnum):
            # notify client that placement was successful
            player.conection.send(player.msg.pack())

            # check for token movement
            positionupdates, eliminated = board.do_player_movement(live_idnums)

            for msg in positionupdates:
                for p in players:
                    p.conection.send(msg.pack())
                    logging.info(f'Player {p.idnum} was sent position update {msg}')

            if player.idnum in eliminated:
                # remove the player from the active players list
                players.remove(player)
                live_idnums.remove(player.idnum)
                player.conection.send(tiles.MessagePlayerEliminated(player.idnum).pack())
                return

            # pickup a new tile
            tileid = tiles.get_random_tileid()
            player.conection.send(tiles.MessageAddTileToHand(tileid).pack())

            # start next turn
            player.conection.send(tiles.MessagePlayerTurn(player.idnum).pack())

    # sent by the player in the second turn, to choose their token's
    # starting path
    elif isinstance(player.msg, tiles.MessageMoveToken):
        if not board.have_player_position(player.msg.idnum):
            if board.set_player_start_position(player.msg.idnum, player.msg.x, player.msg.y, player.msg.position):
                # check for token movement
                positionupdates, eliminated = board.do_player_movement(live_idnums)

                for msg in positionupdates:
                    p.conection.send(msg.pack())
                    logging.info(f'Player {p.idnum} was sent position update {msg}')

                if player.idnum in eliminated:
                    # remove the player from the active players list
                    players.remove(player)
                    live_idnums.remove(player.idnum)
                    player.conection.send(tiles.MessagePlayerEliminated(player.idnum).pack())
                    return

                # start next turn
                for p in players:
                    p.conection.send(tiles.MessagePlayerTurn(player.idnum).pack())
                    logging.info(f'Player {p.idnum} was sent playerTurn info')



# set logging config
logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

# create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# listen on all network interfaces
server_address = ('', 30021)
sock.bind(server_address)
# set server to non-blocking
sock.setblocking(False)
logging.info(f'Listening on port {sock.getsockname()}')
sock.listen(10)

# Sockets from which we expect to read
inputs = [sock]
# Sockets to which we expect to write
outputs = [sock]

idnum = 0
live_idnums = []
connected_clients = []
players = []
board = tiles.Board()
game_started = False
clients_sent_welcome = False


buffer = bytearray()

while True:
    # must give a time out value to select or else it will act in a blocking manner
    readable, writable, errors = select.select(inputs, outputs, inputs, 0.5)

# --------------------------------------------------------------------------------------------
    for s in readable:
        # logging.info('READABLE')
        try:
            if s == sock:
                # establish connection and add client to potential player list
                connection, client_address = s.accept()
                idnum += 1
                # add client to clients list
                add_clients_to_connected_list()
                # s appended to output list
            else:
                data = s.recv(4096)
                if data:
                    conn = Player
                    for p in players:
                        if p.conection == s:
                            conn = p
                    logging.info(f'Data received from client: {conn.idnum}')
                    buffer.extend(data)
                    msg, consumed = tiles.read_message_from_bytearray(buffer)
                    if not consumed:
                        break
                    buffer = buffer[consumed:]
                    logging.info(f'Received message {msg}')
                    conn.msg = msg
                    outputs.append(s)

                # if we don't receive any data
                else:
                    for p in players:
                        if p.conection == s:
                            players.remove(p)
                            logging.info(f'Remove player {p.idnum} from inputs sockets list')
                    s.close()
                    inputs.remove(s)
        except Exception as ex:
            logging.warning(ex.args)

# --------------------------------------------------------------------------------------------
    for s in writable:
        # logging.info('WRITABLE')
        # send all connected clients their unique idnums
        if not clients_sent_welcome:
            for c in connected_clients:
                if c.conection == s:
                    if c.initial_connection:
                        send_connection_idnum_and_welcome()
                        c.initial_connection = False
                        outputs.remove(s)
                        logging.info(f'Client {c.idnum} has been removed from output list')
            clients_sent_welcome = True

        # if not game_started:
        # #   start game and deal hand
        #     start_game()
        #     game_started = True





        # for p in players:
        #     if p.conection == s:
        #         if not game_started and len(players) == 4:
        #             for q in players:
        #                 start_game(q)
        #                 outputs.remove(q.connection)
        #             game_started = True

                    # else:
                    #     player_moves(p)
                    #     logging.info('TODO: player_moves()')
                    #     p.msg = None
        # for p in players:
        #     if not game_started:
        #         if len(players) == 4:
        #             start_game(p)
        #             game_started = True
        #     else:
        #         player_moves(p)
        #         logging.info('TODO: player_moves()')
        #         p.msg = None
        #
        # outputs.remove(s)

    for s in errors:
        # logging.info('ERROR')
        logging.info(f'handling exceptional condition for {s.getpeername()}')
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
            for p in players:
                if p.conection == s:
                    players.remove(p)
        s.close()
        pass

# game_server = multiprocessing.Process(target=server, daemon=True, name='Server')
# game_server.start()
# game_server.join()
