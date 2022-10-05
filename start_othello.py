"""

Othello is a turn-based two-player strategy board game.

-----------------------------------------------------------------------------
Board representation

We represent the board as a flat-list of 100 elements, which includes each square on
the board as well as the outside edge. Each consecutive sublist of ten
elements represents a single row, and each list element stores a piece. 
An initial board contains four pieces in the center:

    ? ? ? ? ? ? ? ? ? ?
    ? . . . . . . . . ?
    ? . . . . . . . . ?
    ? . . . . . . . . ?
    ? . . . o @ . . . ?
    ? . . . @ o . . . ?
    ? . . . . . . . . ?
    ? . . . . . . . . ?
    ? . . . . . . . . ?
    ? ? ? ? ? ? ? ? ? ?

The outside edge is marked ?, empty squares are ., black is @, and white is o.

This representation has two useful properties:

1. Square (m,n) can be accessed as `board[mn]`, and m,n means m*10 + n. This avoids conversion
   between square locations and list indexes.
2. Operations involving bounds checking are slightly simpler.
"""
from datetime import datetime
import math
import random
import time

# The black and white pieces represent the two players.
EMPTY, BLACK, WHITE, OUTER = '.', '@', 'o', '?'
PIECES = (EMPTY, BLACK, WHITE, OUTER)
PLAYERS = {BLACK: 'Black', WHITE: 'White'}

# To refer to neighbor squares we can add a direction to a square.
UP, DOWN, LEFT, RIGHT = -10, 10, -1, 1
UP_RIGHT, DOWN_RIGHT, DOWN_LEFT, UP_LEFT = -9, 11, 9, -11
# in total 8 directions.
DIRECTIONS = (UP, UP_RIGHT, RIGHT, DOWN_RIGHT, DOWN, DOWN_LEFT, LEFT, UP_LEFT)

DEPTH = 4

SQUARE_WEIGHTS = [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 120, -20, 20, 5, 5, 20, -20, 120, 0,
    0, -20, -40, -5, -5, -5, -5, -40, -20, 0,
    0, 20, -5, 15, 3, 3, 15, -5, 20, 0,
    0, 5, -5, 3, 3, 3, 3, -5, 5, 0,
    0, 5, -5, 3, 3, 3, 3, -5, 5, 0,
    0, 20, -5, 15, 3, 3, 15, -5, 20, 0,
    0, -20, -40, -5, -5, -5, -5, -40, -20, 0,
    0, 120, -20, 20, 5, 5, 20, -20, 120, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
]


def squares():
    # list all the valid squares on the board.
    # returns a list of valid integers [11, 12, ...]; e.g. 19,20,21 are invalid
    # 11 means first row, first col, because the board size is 10x10
    return [i for i in range(11, 89) if 1 <= (i % 10) <= 8]


def initial_board():
    # create a new board with the initial black and white positions filled
    # returns a list ['?', '?', '?', ..., '?', '?', '?', '.', '.', '.', ...]
    board = [OUTER] * 100
    for i in squares():
        board[i] = EMPTY
    # the middle four squares should hold the initial piece positions.
    board[44], board[45] = WHITE, BLACK
    board[54], board[55] = BLACK, WHITE
    return board


def print_board(board):
    # get a string representation of the board
    # heading '  1 2 3 4 5 6 7 8\n'
    rep = ''
    rep += '  %s\n' % ' '.join(map(str, range(1, 9)))
    # begin,end = 11,19 21,29 31,39 ..
    for row in range(1, 9):
        begin, end = 10 * row + 1, 10 * row + 9
        rep += '%d %s\n' % (row, ' '.join(board[begin:end]))
    return rep


# -----------------------------------------------------------------------------
# Playing the game

# We need functions to get moves from players, check to make sure that the moves
# are legal, apply the moves to the board, and detect when the game is over.

# Checking moves. A move must be both valid and legal: it must refer to a real square,
# and it must form a bracket with another piece of the same color with pieces of the
# opposite color in between.

def is_valid(move):
    # is move a square on the board?
    # move must be an int, and must refer to a real square
    return isinstance(move, int) and move in squares()


def opponent(player):
    # get player's opponent piece
    return BLACK if player is WHITE else WHITE


def find_bracket(square, player, board, direction):
    # find and return the square that forms a bracket with square for player in the given
    # direction; returns None if no such square exists
    bracket = square + direction
    if board[bracket] == player:
        return None
    opp = opponent(player)
    while board[bracket] == opp:
        bracket += direction
    # if last square board[bracket] not in (EMPTY, OUTER, opp) then it is player
    return None if board[bracket] in (OUTER, EMPTY) else bracket


def is_legal(move, player, board):
    # is this a legal move for the player?
    # move must be an empty square and there has to be a bracket in some direction
    # note: any(iterable) will return True if any element of the iterable is true
    hasbracket = lambda direction: find_bracket(move, player, board, direction)
    return board[move] == EMPTY and any(hasbracket(x) for x in DIRECTIONS)


def make_move(move, player, board):
    # when the player makes a valid move, we need to update the board and flip all the
    # bracketed pieces.
    board[move] = player
    # look for a bracket in any direction
    for d in DIRECTIONS:
        make_flips(move, player, board, d)
    return board


def make_flips(move, player, board, direction):
    # flip pieces in the given direction as a result of the move by player
    bracket = find_bracket(move, player, board, direction)
    if not bracket:
        return
    # found a bracket in this direction
    square = move + direction
    while square != bracket:
        board[square] = player
        square += direction


# Monitoring players

# define an exception
class IllegalMoveError(Exception):
    def __init__(self, player, move, board):
        self.player = player
        self.move = move
        self.board = board

    def __str__(self):
        return '%s cannot move to square %d' % (PLAYERS[self.player], self.move)


def legal_moves(player, board):
    # get a list of all legal moves for player
    # legal means: move must be an empty square and there has to be is an occupied line in some direction
    return [sq for sq in squares() if is_legal(sq, player, board)]


def any_legal_move(player, board):
    # can player make any moves?
    return any(is_legal(sq, player, board) for sq in squares())


# Putting it all together. Each round consists of:
# - Get a move from the current player.
# - Apply it to the board.
# - Switch players. If the game is over, get the final score.

def play(black_strategy, white_strategy):
    # play a game of Othello and return the final board and score
    board = initial_board()
    player = BLACK
    print(print_board(board))

    if player == WHITE:
        strategy = white_strategy
    elif player == BLACK:
        strategy = black_strategy

    while len(legal_moves(player, board)) != 0:
        move = get_move(strategy, player, board)
        board = make_move(move, player, board)

        print(print_board(board))
        print(datetime.now())

        player = next_player(board, player)

    print(print_board(board))
    print("white:" + str(board.count(WHITE)))
    print("Black:" + str(board.count(BLACK)))


def next_player(board, prev_player):
    # which player should move next?  Returns None if no legal moves exist
    if not any_legal_move(prev_player, board) and not any_legal_move(opponent(prev_player), board):
        return None

    elif prev_player == PIECES[1]:
        player = PIECES[2]
    else:
        player = PIECES[1]

    return player


def get_move(strategy, player, board):
    # call strategy(player, board) to get a move
    time_start = time.time()
    move = strategy(player, board, DEPTH, time_start)

    if is_legal(move, player, board) and is_valid(move):
        return move
    else:
        raise IllegalMoveError(player, move, board)


def score(player, board):
    # compute player's score (number of player's pieces minus opponent's)
    opp = opponent(player)

    starting_player = 0
    second_player = 0

    for square in squares():
        position = board[square]
        if position == player:
            starting_player += 1
        elif position == opp:
            second_player += 1

    player_score = starting_player - second_player
    return player_score


# Play strategies

def random_move(player, board, depth, time):
    return random.choice(legal_moves(player, board))


def negamax(player, board, depth, time):
    possible_moves = legal_moves(player, board)

    # wikipedia pseudocode
    # if depth = 0 or node is a terminal node then
    #   return color x the heuristic value of node
    if depth < 1 or len(possible_moves) <= 0:
        return score(player, board)

    # value := -infinity
    current_best = -math.inf
    best_move = possible_moves[0]

    # for each child of node do
    #   value = max(value, negamax(player, next_version_of_board, depth -1))

    for move in possible_moves:
        new_board = make_move(move, player, board[:])
        move_score = -negamax(player, new_board, depth - 1)

        if move_score > current_best:
            current_best = move_score
            best_move = move

    # return value
    return best_move


def heuristic_score(player, board):
    score = 0

    for sq in squares():
        if board[sq] == player:
            score += SQUARE_WEIGHTS[sq]
        if board[sq] == opponent(player):
            score -= SQUARE_WEIGHTS[sq]
    return score


def negamax_heuristics(player, board, depth, start_time):
    possible_moves = legal_moves(player, board)

    if depth < 1 or len(possible_moves) <= 0:
        return heuristic_score(player, board)

    current_best = -math.inf
    best_move = possible_moves[0]

    current_time = time.time()
    if current_time - start_time >= 2:
        #print("Ran out of time!")
        return best_move

    for move in possible_moves:
        new_board = make_move(move, player, board[:])
        move_score = -negamax_heuristics(opponent(player), new_board, depth - 1, start_time)

        if move_score > current_best:
            current_best = move_score
            best_move = move
    return best_move


def negamax_pruning(player, board, depth, start_time, alfa=-math.inf, beta=math.inf):

    possible_moves = legal_moves(player, board)

    # print(possible_moves, len(possible_moves) <= 0)

    if depth < 1 or len(possible_moves) <= 0:
        #print("Returning score")
        return heuristic_score(player, board)

    current_best = -math.inf
    best_move = possible_moves[0]

    current_time = time.time()
    if current_time - start_time >= 2:
        print("Ran out of time!")
        return best_move

    for move in possible_moves:
        new_board = make_move(move, player, board[:])
        move_score = -negamax_pruning(opponent(player), new_board, depth - 1, start_time, -beta, -alfa)
        if move_score > current_best:
            current_best = move_score
            best_move = move

        # alfa beta pruning
        # onthoudt de beste tak die het algoritme is tegen gekomen en als het resultaat
        # minder lijkt dan knipt ie de tak af en zoekt ie niet verder.

        alfa = max(alfa, current_best)
        if alfa >= beta:
            break

        # F
        # kan nog worden worden verbeterd door gebruik te maken van transpositie tabellen.
        # https://en.wikipedia.org/wiki/Negamax#Negamax_with_alpha_beta_pruning_and_transposition_tables
        # Transpositie is een term wat betekent dat er meerdere wegen naar Rome (een gegeven bord positie) leiden.

    return best_move


# play (black, white)
play(negamax_pruning, random_move)
