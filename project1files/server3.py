import socket
import logging
import select
import tiles
import multiprocessing

board = tiles.Board()

class Player():
    def __init__(self, connection: socket, idnum: int, address: str):
        self.conection = connection
        self.idnum = idnum
        self.initial_connection = True
        self.address = address
        self.host, self.port = address
        self.turn = False
        self.name = '{}:{}'.format(self.host, self.port)
        self.msg = None


def initial_connection_deal_hand(player: Player):
    logging.info(f'Initial connection{player.idnum}')
    player.conection.send(tiles.MessageWelcome(player.idnum).pack())
    logging.info(f'Server send tiles.MessageWelcome idnum = {player.idnum}')
    player.conection.send(tiles.MessagePlayerJoined(player.name, player.idnum).pack())
    player.conection.send(tiles.MessageGameStart().pack())

    for _ in range(tiles.HAND_SIZE):
        tileid = tiles.get_random_tileid()
        player.conection.send(tiles.MessageAddTileToHand(tileid).pack())

    player.conection.send(tiles.MessagePlayerTurn(idnum).pack())
    player.initial_connection = False


def player_moves(player: Player):
    live_idnums = []
    for p in players:
        live_idnums.append(p.idnum)

    if isinstance(player.msg, tiles.MessagePlaceTile):
        if board.set_tile(player.msg.x, player.msg.y, player.msg.tileid, player.msg.rotation, player.msg.idnum):
            # notify client that placement was successful
            s.send(player.msg.pack())

            # check for token movement
            positionupdates, eliminated = board.do_player_movement(live_idnums)

            for player.msg in positionupdates:
                s.send(player.msg.pack())

            if idnum in eliminated:
                # remove the player from the active players list
                players.remove(player)
                player.conection.send(tiles.MessagePlayerEliminated(player.idnum).pack())
                return

            # pickup a new tile
            tileid = tiles.get_random_tileid()
            player.conection.send(tiles.MessageAddTileToHand(tileid).pack())

            # start next turn
            player.conection.send(tiles.MessagePlayerTurn(idnum).pack())

    # sent by the player in the second turn, to choose their token's
    # starting path
    elif isinstance(player.msg, tiles.MessageMoveToken):
        if not board.have_player_position(player.idnum):
            if board.set_player_start_position(player.idnum, player.msg.x, player.msg.y, player.msg.position):
                # check for token movement
                positionupdates, eliminated = board.do_player_movement(live_idnums)

                for msg in positionupdates:
                    s.send(msg.pack())

                if idnum in eliminated:
                    # remove the player from the active players list
                    players.remove(player)
                    s.send(tiles.MessagePlayerEliminated(idnum).pack())
                    return

                # start next turn
                s.send(tiles.MessagePlayerTurn(idnum).pack())

    player.msg = None

# set logging config
logging.basicConfig(format='%(levelname)s - %(asctime)s: %(message)s',datefmt='%H:%M:%S', level=logging.DEBUG)


# create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# listen on all network interfaces
server_address = ('', 30021)
sock.bind(server_address)
# set server to non-blocking
sock.setblocking(False)
logging.info(f'Listening on port {sock.getsockname()}')
sock.listen(5)

# Sockets from which we expect to read
inputs = [sock]
# Sockets to which we expect to write
outputs = [sock]

idnum = 0
players = []

buffer = bytearray()

while True:
    # must give a time out value to select or else it will act in a blocking manner
    readable, writable, errors = select.select(inputs, outputs, inputs, 0.5)

    for s in readable:
        logging.info('READABLE')
        try:
            if s == sock:
                connection, client_address = s.accept()
                # set clients to non-blocking as well
                connection.setblocking(False)
                # connection added to the list of sockets to monitor for input
                inputs.append(connection)
                logging.info(f'Client Connection: {client_address}')
                # client establishes connection - deal tiles
                idnum += 1
                conn = Player(connection, idnum, client_address)
                players.append(conn)
                logging.info(f'Player {conn.idnum} appended to players list')
                outputs.append(connection)

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
                    logging.info(f'Remove player {s} from inputs sockets list')
                    s.close()
                    inputs.remove(s)
        except Exception as ex:
            logging.warning(ex.args)

    for s in writable:
        logging.info('WRITABLE')
        conn = Player
        for p in players:
            if s == p.conection:
                conn = p
                if p.initial_connection:
                    initial_connection_deal_hand(p)
                else:
                    player_moves(p)
                outputs.remove(s)

    for s in errors:
        logging.info('ERROR')
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



