import socket
import logging
import select
import tiles
import multiprocessing


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
        self.start_game = False
        self.clients_notified = False


def initial_connection(player: Player):
    logging.info(f'Initial connection player = {player.idnum}')
    player.conection.send(tiles.MessageWelcome(player.idnum).pack())
    logging.info(f'Server send tiles.MessageWelcome idnum = {player.idnum}')

def notify_all_clients(player):
    for a in all_connections:
        if a.idnum != player.idnum and player.initial_connection:
            a.conection.send(tiles.MessagePlayerJoined(player.name, player.idnum).pack())
            logging.info(f'ID = {a.idnum} informed that client {player.idnum} has connected')
            player.initial_connection = False

def add_client_to_players_list():
    new_player = client_connections.pop(0)
    players.append(new_player)
    live_idnums.append(new_player.idnum)
    new_player.selected_as_player = True
    new_player.conection.setblocking(False)
    logging.info(f'Initial connection player = {new_player.idnum}')
    # connection added to the list of sockets to monitor for input
    inputs.append(new_player.conection)
    logging.info(f'Player {new_player.idnum} appended to players list')
    new_player.selected_as_player = True

def next_turn():
    if current_turn_index == (len(live_idnums) - 1):
        current_turn_index = 0
    else:
        current_turn_index + 1

def start_game(p):
    p.conection.send(tiles.MessageGameStart().pack())
    for _ in range(tiles.HAND_SIZE):
        tileid = tiles.get_random_tileid()
        p.conection.send(tiles.MessageAddTileToHand(tileid).pack())
    p.conection.send(tiles.MessagePlayerTurn(live_idnums[current_turn_index]).pack())




def player_moves(player: Player):
    logging.info(f'38: Player msg.idnum = {player.msg.idnum}')
    if isinstance(player.msg, tiles.MessagePlaceTile):
        if board.set_tile(player.msg.x, player.msg.y, player.msg.tileid, player.msg.rotation, player.msg.idnum):
            # notify client that placement was successful
            player.conection.send(player.msg.pack())

            # check for token movement
            logging.info(f'50: Player_moves: live_idnums = {live_idnums}')
            positionupdates, eliminated = board.do_player_movement(live_idnums)

            logging.info(f'53: Position updates: {positionupdates}')
            for msg in positionupdates:
                for p in players:
                    p.conection.send(msg.pack())
                    logging.info(f'52: Player {p.idnum} was sent position update \n message = {msg}')

            if player.idnum in eliminated:
                player.conection.send(tiles.MessagePlayerEliminated(player.idnum).pack())
                # remove the player from the active players list
                player.conection.close()
                outputs.remove(player.conection)
                players.remove(player)
                live_idnums.remove(player.idnum)
                return

            # pickup a new tile
            tileid = tiles.get_random_tileid()
            player.conection.send(tiles.MessageAddTileToHand(tileid).pack())

            # start next turn
            next_turn()
            player.conection.send(tiles.MessagePlayerTurn(live_idnums[current_turn_index]).pack())

    # sent by the player in the second turn, to choose their token's
    # starting path
    elif isinstance(player.msg, tiles.MessageMoveToken):
        if not board.have_player_position(player.msg.idnum):
            if board.set_player_start_position(player.msg.idnum, player.msg.x, player.msg.y, player.msg.position):
                logging.info(f'79: Board Player Positions = {board.playerpositions}')
                # check for token movement
                positionupdates, eliminated = board.do_player_movement(live_idnums)

                for msg in positionupdates:
                    for p in players:
                        p.conection.send(msg.pack())
                        logging.info(f'85: Player {p.idnum} was sent position update \n message = {msg}')

                if player.idnum in eliminated:
                    # remove the player from the active players list
                    player.conection.send(tiles.MessagePlayerEliminated(player.idnum).pack())
                    player.conection.close()
                    outputs.remove(player.conection)
                    players.remove(player)
                    live_idnums.remove(player.idnum)
                    return


                # start next turn
                next_turn()
                player.conection.send(tiles.MessagePlayerTurn(live_idnums[current_turn_index]).pack())
                logging.info(f'98: Player {player.idnum} was sent playerTurn info')



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
sock.listen(5)

# Sockets from which we expect to read
inputs = [sock]
# Sockets to which we expect to write
outputs = [sock]

idnum = 0
live_idnums = []
players = []
client_connections = []
all_connections = []
game_started = False
board = tiles.Board()
current_turn_index = 0


buffer = bytearray()

while True:
    # must give a time out value to select or else it will act in a blocking manner
    readable, writable, errors = select.select(inputs, outputs, inputs, 0.5)

    for s in readable:
        try:
            if s == sock:
                connection, client_address = s.accept()
                # set clients to non-blocking as well
                connection.setblocking(False)
                # connection added to the list of sockets to monitor for input
                inputs.append(connection)
                outputs.append(connection)
                logging.info(f'Client Connection: {client_address}')
                # client establishes connection - deal tiles
                conn = Player(connection, idnum, client_address)
                client_connections.append(conn)
                all_connections.append(conn)

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
                # else:
                #     for p in players:
                #         if p.conection == s:
                #             players.remove(p)
                #             logging.info(f'Remove player {p.idnum} from inputs sockets list')
                #     s.close()
                #     inputs.remove(s)
        except Exception as ex:
            logging.warning(ex.args)

    for s in writable:
        if len(client_connections) > 0:
            for c in client_connections:
                if s == c.conection:
                    if c.initial_connection:
                        initial_connection(c)
                        idnum += 1
                        # add players to game
                    # add players to game

        if len(client_connections) > 0 and len(players) < 2 and not game_started:
            for c in client_connections:
                if s == c.conection:
                    add_client_to_players_list()

        if len(players) == 2 and not game_started:
            for p in range(len(players)):
                if s == players[p].conection:
                    if not players[p].clients_notified:
                        notify_all_clients(players[p])
                        players[p].clients_notified = True

            for p in range(len(players)):
                if s == players[p].conection:
                    if not players[p].start_game:
                        logging.info(f'193: Game started {players[p].idnum}')
                        start_game(players[p])
                        players[p].start_game = True





    for s in errors:
        logging.info(f'handling exceptional condition for {s.getpeername()}')
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
            for p in players:
                if p.conection == s:
                    players.remove(p)
        s.close()


# game_server = multiprocessing.Process(target=server, daemon=True, name='Server')
# game_server.start()
# game_server.join()