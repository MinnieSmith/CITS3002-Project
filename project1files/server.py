# CITS3002 2021 Assignment
#
# This file implements a basic server that allows a single client to play a
# single game with no other participants, and very little error checking.
#
# Any other clients that connect during this time will need to wait for the
# first client's game to complete.
#
# Your task will be to write a new server that adds all connected clients into
# a pool of players. When enough players are available (two or more), the server
# will create a game with a random sample of those players (no more than
# tiles.PLAYER_LIMIT players will be in any one game). Players will take turns
# in an order determined by the server, continuing until the game is finished
# (there are less than two players remaining). When the game is finished, if
# there are enough players available the server will start a new game with a
# new selection of clients.

import socket
import sys
import tiles
import select
import queue


def initial_connection(inputs, sockets, idnum):
    print("establishing inital connection")
    # new connection accepted and added to the it to the queue of sockets
    # to monitor
    connection, client_address = sockets.accept()
    connections_idnum[connection] = idnum
    # sets client to non-setblocking
    connection.setblocking(0)
    # add client to inputs list to monitor
    inputs.append(connection)
    # give the client a queue for data we want to send
    message_queues[connection] = queue.Queue()
    host, port = client_address
    name = '{}:{}'.format(host, port)

    connection.send(tiles.MessageWelcome(idnum).pack())
    print("server send tiles.MessageWelcome idnum = {}".format(idnum))
    connection.send(tiles.MessagePlayerJoined(name, idnum).pack())
    print("server send tiles.MessagePlayerJoined idnum = {}".format(idnum))
    connection.send(tiles.MessageGameStart().pack())
    print("server send tiles startgame")

    for _ in range(tiles.HAND_SIZE):
        tileid = tiles.get_random_tileid()
        connection.send(tiles.MessageAddTileToHand(tileid).pack())
        print("server sends tiles.MessageAddTimeToHand tileid = {}".format(tileid))

    connection.send(tiles.MessagePlayerTurn(idnum).pack())
    print("server sends tile.MessagePlayerTurn idnum {}".format(idnum))


def process_client_input(message):
    output_msg = []
    print("58: processing client input")
    # sent by the player to put a tile onto the board (in all turns except
    # their second)
    msg, consumed = tiles.read_message_from_bytearray(message)

    if isinstance(msg, tiles.MessagePlaceTile):
        if board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):
            # notify client that placement was successful
            output_msg.append(msg)
            print("65: output_msg = {}".format(output_msg))

            # check for token movement
            positionupdates, eliminated = board.do_player_movement(live_idnums)

            for msg in positionupdates:
                output_msg.append(msg)

            if idnum in eliminated:
                output_msg.append(tiles.MessagePlayerEliminated(idnum))
                print("idnum eliminated: {}".format(idnum))
                print("live idnums = {}".format(live_idnums))
                return

            # pickup a new tile
            tileid = tiles.get_random_tileid()
            output_msg.append(tiles.MessageAddTileToHand(tileid))
            print("output_msg = {}".format(output_msg))

            # start next turn
            output_msg.append(tiles.MessagePlayerTurn(idnum))
            print("output_msg = {}".format(output_msg))

    # sent by the player in the second turn, to choose their token's
    # starting path
    elif isinstance(msg, tiles.MessageMoveToken):
        if not board.have_player_position(msg.idnum):
            if board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
                # check for token movement
                positionupdates, eliminated = board.do_player_movement(live_idnums)

                for msg in positionupdates:
                    output_msg.append(msg)

                if idnum in eliminated:
                    live_idnums.remove(idnum)
                    output_msg.append(tiles.MessagePlayerEliminated(idnum))
                    return

                # start next turn
                output_msg.append(tiles.MessagePlayerTurn(idnum))
                print("106: output_msg = {}".format(output_msg))
    return output_msg


# create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(False)
# listen on all network interfaces
server_address = ('', 30021)
sock.bind(server_address)

print('listening on {}'.format(sock.getsockname()))

sock.listen(5)

# Sockets from which we expect to read
inputs = [sock]
# Sockets to which we expect to write
outputs = []
# Outgoing message queues dictionary (socket:queue) for data we want to send
message_queues = {}

board = tiles.Board()
idnum = 0
# Dictionary of connections and their idnum (connection: idnum)
connections_idnum = {}
live_idnums = []

while inputs:
    # readable socket list have incoming data buffered and available to be read
    # writable socket list have free space in buffer that can be written to
    readable, writable, exceptional = select.select(inputs, outputs, inputs)
    for sockets in readable:
        print("sockets in readable:")
        # if socket has incoming data establish a connection
        if sockets is sock:
            idnum += 1
            live_idnums.append(idnum)
            print("live idnums = {}".format(live_idnums))
            initial_connection(inputs, sockets, idnum)
        else:
            #  data is read with recv(), then placed on the queue so it can be sent
            #  through the socket and back to the client.
            chunk = sockets.recv(4096)
            if chunk:
                message_queues[sockets].put(chunk)
                print("if data received: chunk added to message_queue")
                if sockets not in outputs:
                    outputs.append(sockets)
                    print("socket appended to outputs list, if not in it already")
            else:
                if sockets in outputs:
                    print("if no data received, then remove socket from ouputs")
                    outputs.remove(sockets)
                inputs.remove(sockets)
                print("if no more data received, removed socket from inputs")
                sockets.close()
                del message_queues[sockets]
                print("socket closed and it's queue is removed from outgoing message queue")

    # handles output
    # if there is data in the queue for a connect, the next message is sent
    for sockets in writable:
        print("sockets in writable")
        try:
            next_message = message_queues[sockets].get_nowait()
            print("172: next_message = {}".format(next_message))
            output_messages = process_client_input(next_message)
            print("174: output_messages = {}".format(output_messages))
        except queue.Empty:
            # if there are no data waiting in queue to be sent, remove it from outputs list
            outputs.remove(sockets)
        else:
            print("queue not empty and there is data to send, send it")
            print("len(outputmsg) = {}".format(len(output_messages)))
            for msg in range(len(output_messages)):
                sockets.send(msg)
                print("output msg sent")



    for sockets in exceptional:
        print(" error in socket, remove it from both input and output list and close the connection ")
        inputs.remove(sockets)
        live_idnums.remove(connections_idnum[sockets])
        if sockets in outputs:
            outputs.remove(sockets)
            sockets.close()
            del message_queues[sockets]
