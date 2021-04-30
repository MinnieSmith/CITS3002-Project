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


def client_handler(connection, address):
  host, port = address
  name = '{}:{}'.format(host, port)

  idnum = 0
  live_idnums = [idnum]

  connection.send(tiles.MessageWelcome(idnum).pack())
  connection.send(tiles.MessagePlayerJoined(name, idnum).pack())
  connection.send(tiles.MessageGameStart().pack())

  for _ in range(tiles.HAND_SIZE):
    tileid = tiles.get_random_tileid()
    connection.send(tiles.MessageAddTileToHand(tileid).pack())
  
  connection.send(tiles.MessagePlayerTurn(idnum).pack())
  
  board = tiles.Board()

  buffer = bytearray()

  while True:
    chunk = connection.recv(4096)
    if not chunk:
      print('client {} disconnected'.format(address))
      return

    buffer.extend(chunk)

    while True:
      msg, consumed = tiles.read_message_from_bytearray(buffer)
      if not consumed:
        break

      buffer = buffer[consumed:]

      print('received message {}'.format(msg))

      # sent by the player to put a tile onto the board (in all turns except
      # their second)
      if isinstance(msg, tiles.MessagePlaceTile):
        if board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):
          # notify client that placement was successful
          connection.send(msg.pack())

          # check for token movement
          positionupdates, eliminated = board.do_player_movement(live_idnums)

          for msg in positionupdates:
            connection.send(msg.pack())
          
          if idnum in eliminated:
            connection.send(tiles.MessagePlayerEliminated(idnum).pack())
            return

          # pickup a new tile
          tileid = tiles.get_random_tileid()
          connection.send(tiles.MessageAddTileToHand(tileid).pack())

          # start next turn
          connection.send(tiles.MessagePlayerTurn(idnum).pack())

      # sent by the player in the second turn, to choose their token's
      # starting path
      elif isinstance(msg, tiles.MessageMoveToken):
        if not board.have_player_position(msg.idnum):
          if board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
            # check for token movement
            positionupdates, eliminated = board.do_player_movement(live_idnums)

            for msg in positionupdates:
              connection.send(msg.pack())
            
            if idnum in eliminated:
              connection.send(tiles.MessagePlayerEliminated(idnum).pack())
              return
            
            # start next turn
            connection.send(tiles.MessagePlayerTurn(idnum).pack())


# create a IPV4, TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# listen on all network interfaces
server_address = ('', 30020)
sock.bind(server_address)

print('listening on {}'.format(sock.getsockname()))

sock.listen(5)



# handle each new connection independently
# sock.accept() accepts any incoming connections and stores the connection
# in the connection and the address in client_address
# connection, client_address = sock.accept()
# print('received connection from {}'.format(client_address))


while True:
  inputs = [sock]
  outputs = []
  message_queues = {}

  while inputs:
    # Wait for at least one of the sockets to be ready for processing
    print('\nwaiting for the next event')
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

    for s in readable:
      if s is sock:
        connection, client_address = sock.accept()
        print ('new connection from', client_address)
        # connection.setblocking(0)
        inputs.append(connection)
        message_queues[connection] = queue.Queue()
        client_handler(connection, client_address)
      else:
        data = s.recv(4096)
        if data:
          print ('received "%s" from %s' % (data, s.getpeername()))
          message_queues[s].put(data)
          # Add output channel for response
          if s not in outputs:
            outputs.append(s)
        else:
          # Interpret empty result as closed connection
          print ('closing after reading no data')
          # Stop listening for input on the connection
          if s in outputs:
            outputs.remove(s)
          inputs.remove(s)
          s.close()
          # Remove message queue
          del message_queues[s]

    # Handle outputs
    for s in writable:
      try:
        next_msg = message_queues[s].get_nowait()
      except queue.Empty:
        # No messages waiting so stop checking for writability.
        print ('output queue for', s.getpeername(), 'is empty')
        outputs.remove(s)
      else:
        print >> sys.stderr, 'sending "%s" to %s' % (next_msg, s.getpeername())
        s.send(next_msg)

    # Handle "exceptional conditions"
    for s in exceptional:
      print ('handling exceptional condition for', s.getpeername())
      # Stop listening for input on the connection
      inputs.remove(s)
      if s in outputs:
        outputs.remove(s)
      s.close()

      # Remove message queue
      del message_queues[s]
































