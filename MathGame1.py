"""Juego matemático multijugador para ejecutar con NiceGUI."""

from __future__ import annotations

import os
import random
import secrets
import string
from dataclasses import dataclass, field
from itertools import product

from nicegui import ui


Position = tuple[int, int]
Cell = int | str | None
SKULL = '💀'
KEY = '🔑'
HEART = '❤️'
POSITIONS = tuple(
    (row, column)
    for row in range(6)
    for column in range(6)
    if row >= 2 or (row == 0 and column in (2, 3)) or (row == 1 and 1 <= column <= 4)
)
DOORS = {(1, 3), (2, 2), (3, 3), (4, 0), (4, 5), (5, 2), (5, 3)}
ROLLS = tuple(product(range(1, 7), repeat=3))
RNG = random.SystemRandom()
ROOMS: dict[str, Game] = {}
TOKENS: dict[str, Game] = {}


def neighbors(position: Position) -> list[Position]:
    row, column = position
    return [
        (row + dr, column + dc)
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if (dr or dc) and (row + dr, column + dc) in POSITIONS
    ]


@dataclass
class BoardAnalysis:
    scores: dict[str, int]
    longest_sequence: list[Position]
    sequence_edges: list[tuple[Position, Position]]
    group_cells: set[Position]
    positive_skulls: set[Position]
    negative_skulls: set[Position]


def analyze_board(board: dict[Position, Cell]) -> BoardAnalysis:
    """Calcula la puntuación y las casillas que la explican."""
    numbers = {position: value for position, value in board.items() if isinstance(value, int)}
    paths: dict[Position, list[Position]] = {}
    edges: list[tuple[Position, Position]] = []
    for position in sorted(numbers, key=lambda pos: (numbers[pos], pos)):
        predecessors = [other for other in neighbors(position)
                        if numbers.get(other) == numbers[position] - 1]
        edges.extend((other, position) for other in predecessors)
        paths[position] = (max((paths[other] for other in predecessors), key=len, default=[])
                           + [position])
    longest = max(paths.values(), key=len, default=[])
    if len(longest) < 2:
        longest = []

    visited: set[Position] = set()
    scored_values: set[int] = set()
    group_cells: set[Position] = set()
    for position, value in numbers.items():
        if position in visited:
            continue
        stack = [position]
        visited.add(position)
        component: set[Position] = set()
        while stack:
            current = stack.pop()
            component.add(current)
            for other in neighbors(current):
                if other not in visited and numbers.get(other) == value:
                    visited.add(other)
                    stack.append(other)
        if len(component) >= 3:
            scored_values.add(value)
            group_cells.update(component)
    positive_skulls = {position for position, value in board.items() if value == SKULL
                       and any(board.get(other) == 9 for other in neighbors(position))}
    negative_skulls = {position for position, value in board.items() if value == SKULL} - positive_skulls
    sequences = len(longest)
    groups = 3 * len(scored_values)
    skulls = 2 * (len(positive_skulls) - len(negative_skulls))
    scores = {'secuencias': sequences, 'grupos': groups, 'calaveras': skulls,
              'total': sequences + groups + skulls}
    return BoardAnalysis(scores, longest, edges, group_cells, positive_skulls, negative_skulls)


def score(board: dict[Position, Cell]) -> dict[str, int]:
    return analyze_board(board).scores


@dataclass
class Player:
    name: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    board: dict[Position, Cell] = field(default_factory=lambda: dict.fromkeys(POSITIONS))


@dataclass
class Game:
    code: str
    players: list[Player] = field(default_factory=list)
    state: str = 'waiting'
    roll: tuple[int, int, int] | None = None
    turn: int = 0
    revision: int = 0
    submitted: set[str] = field(default_factory=set)
    targets: dict[str, str] = field(default_factory=dict)

    def add_player(self, name: str) -> Player:
        name = name.strip()
        if self.state != 'waiting':
            raise ValueError('La partida ya ha comenzado.')
        if not name or len(name) > 30:
            raise ValueError('Escribe un nombre de entre 1 y 30 caracteres.')
        if any(player.name.casefold() == name.casefold() for player in self.players):
            raise ValueError('Ese nombre ya está en uso en la partida.')
        player = Player(name)
        self.players.append(player)
        TOKENS[player.token] = self
        self.revision += 1
        return player

    def player(self, token: str) -> Player:
        return next(player for player in self.players if player.token == token)

    def start(self, token: str) -> None:
        if self.state != 'waiting' or not self.players or self.players[0].token != token:
            raise ValueError('Solo el creador puede iniciar la partida.')
        if len(self.players) < 2:
            raise ValueError('Se necesitan al menos dos jugadores.')
        self.state = 'playing'
        self.next_turn()

    def next_turn(self) -> None:
        if all(all(player.board[pos] is not None for pos in POSITIONS if pos not in DOORS)
               for player in self.players):
            self.state = 'finished'
            self.roll = None
            self.revision += 1
            return

        door_possible = any(any(p.board[pos] is None for pos in DOORS) for p in self.players)
        normal_possible = any(any(p.board[pos] is None for pos in POSITIONS if pos not in DOORS)
                              for p in self.players)
        valid = [
            roll for roll in ROLLS
            if (normal_possible if roll[2] == 6 else door_possible if roll[0] == 6 else normal_possible)
        ]
        if not valid:
            raise RuntimeError('No hay ninguna tirada posible para continuar la partida.')
        self.roll = RNG.choice(valid)
        self.turn += 1
        self.submitted.clear()
        self.targets.clear()
        if self.roll[2] == 6:
            shuffled = self.players.copy()
            RNG.shuffle(shuffled)
            for index, player in enumerate(shuffled):
                target = shuffled[(index + 1) % len(shuffled)]
                self.targets[player.token] = target.token
                if not any(target.board[pos] is None for pos in POSITIONS if pos not in DOORS):
                    self.submitted.add(player.token)
        else:
            is_door_turn = self.roll[0] == 6
            self.submitted.update(
                player.token for player in self.players
                if not any(player.board[pos] is None for pos in POSITIONS
                           if (pos in DOORS) == is_door_turn)
            )
        self.revision += 1

    def choices(self) -> list[int]:
        if self.roll is None or self.roll[2] == 6:
            return []
        if self.roll[1] == 6 and self.roll[0] != 6:
            return list(range(1, 16))
        numbers = [die for die in self.roll if die != 6]
        return sorted({sum(numbers[index] for index in range(len(numbers)) if mask & (1 << index))
                       for mask in range(1, 1 << len(numbers))})

    def place(self, token: str, position: Position, number: int | None, turn: int) -> None:
        if self.state != 'playing' or self.roll is None or turn != self.turn:
            raise ValueError('El turno ya ha cambiado. Espera la actualización.')
        if token in self.submitted:
            raise ValueError('Ya has jugado en este turno.')
        player = self.player(token)
        skull = self.roll[2] == 6
        target = self.player(self.targets[token]) if skull else player
        if position not in target.board or target.board[position] is not None:
            raise ValueError('Elige una casilla vacía.')
        if (position in DOORS) != (not skull and self.roll[0] == 6):
            raise ValueError('La tirada no permite usar esa casilla.')
        if not skull and number not in self.choices():
            raise ValueError('Elige un número permitido por los dados.')
        target.board[position] = SKULL if skull else number
        self.submitted.add(token)
        self.revision += 1
        if len(self.submitted) == len(self.players):
            self.next_turn()


def create_game(name: str) -> tuple[Game, Player]:
    while True:
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        if code not in ROOMS:
            break
    game = Game(code)
    player = game.add_player(name)
    ROOMS[code] = game
    return game, player


def display_roll(roll: tuple[int, int, int]) -> str:
    return f'{KEY if roll[0] == 6 else roll[0]}    {HEART if roll[1] == 6 else roll[1]}    {SKULL if roll[2] == 6 else roll[2]}'


def notice(error: ValueError) -> None:
    ui.notify(str(error), type='negative')


@ui.page('/')
def index() -> None:
    ui.page_title('MathGame1')
    with ui.column().classes('w-full max-w-lg mx-auto p-4 gap-4'):
        ui.label('MathGame1').classes('text-3xl font-bold')
        ui.label('Crea una partida o únete con el código que te hayan compartido.')
        name = ui.input('Tu nombre', validation={'Máximo 30 caracteres': lambda v: len(v or '') <= 30}).classes('w-full')
        code = ui.input('Código de partida').props('maxlength=6').classes('w-full')

        def create() -> None:
            try:
                _, player = create_game(name.value or '')
            except ValueError as error:
                notice(error)
                return
            ui.navigate.to(f'/partida?token={player.token}')

        def join() -> None:
            game = ROOMS.get((code.value or '').strip().upper())
            if game is None:
                ui.notify('No existe una partida con ese código.', type='negative')
                return
            try:
                player = game.add_player(name.value or '')
            except ValueError as error:
                notice(error)
                return
            ui.navigate.to(f'/partida?token={player.token}')

        ui.button('Crear partida', on_click=create).classes('w-full')
        ui.button('Unirse a la partida', on_click=join).props('outline').classes('w-full')
        ui.label('Cada persona juega desde su propio dispositivo.').classes('text-sm text-grey-7')


@ui.page('/partida')
def game_page(token: str = '') -> None:
    game = TOKENS.get(token)
    if game is None:
        ui.label('La partida no existe o ha caducado.').classes('text-lg')
        ui.link('Volver al inicio', '/')
        return
    player = game.player(token)
    ui.page_title('MathGame1 - partida')
    ui.add_css('.door-cell .q-btn__content { transform: scaleX(1.6); }')
    selected: dict[str, int | None] = {'number': None}
    seen = {'revision': -1}

    @ui.refreshable
    def content() -> None:
        with ui.column().classes('w-full max-w-xl mx-auto p-3 gap-3'):
            ui.label(f'Partida {game.code}').classes('text-2xl font-bold')
            ui.label(f'Jugador: {player.name}')
            if game.state == 'waiting':
                ui.label('Comparte el código de partida. No compartas la dirección de esta página.')
                ui.label('Jugadores: ' + ', '.join(p.name for p in game.players))
                if player is game.players[0]:
                    def start() -> None:
                        try:
                            game.start(token)
                        except ValueError as error:
                            notice(error)
                    ui.button('Empezar partida', on_click=start)
                else:
                    ui.label('Esperando a que el creador empiece la partida.')
                return
            if game.state == 'finished':
                results = [(p, analyze_board(p.board)) for p in game.players]
                best = max(analysis.scores['total'] for _, analysis in results)
                winners = ', '.join(p.name for p, analysis in results if analysis.scores['total'] == best)
                ui.label(f'Ganador(es): {winners}').classes('text-xl font-bold')
                ui.label('Línea verde: secuencia puntuable; gris: otras conexiones consecutivas. '
                         'Fondo de color: grupo; verde: calavera positiva; cruz roja: negativa.').classes('text-sm')
                for p, analysis in sorted(results, key=lambda item: item[1].scores['total'], reverse=True):
                    result = analysis.scores
                    ui.label(f"{p.name}: {result['total']} puntos "
                             f"(secuencias {result['secuencias']}, grupos {result['grupos']}, "
                             f"calaveras {result['calaveras']:+})").classes('font-bold')
                    draw_board(p.board, None, analysis=analysis)
                ui.link('Nueva partida', '/')
                return

            assert game.roll is not None
            skull = game.roll[2] == 6
            done = token in game.submitted
            ui.label(f'Turno {game.turn}').classes('text-lg font-bold')
            ui.label(display_roll(game.roll)).classes('text-3xl tracking-wide')
            ui.label(f'Jugadores que han terminado el turno: {len(game.submitted)}/{len(game.players)}')
            if done:
                ui.label('Ya has jugado o no tienes una casilla válida. Esperando a los demás.')
                ui.label('Tu tablero:')
                draw_board(player.board, None)
                return
            if skull:
                ui.label('Calavera: marca una casilla vacía sin puerta en este tablero anónimo.')
                target = game.player(game.targets[token])
            else:
                target = player
                ui.label('Elige un número y toca una casilla ' + ('con puerta.' if game.roll[0] == 6 else 'sin puerta.'))
                choices = game.choices()
                if selected['number'] not in choices:
                    selected['number'] = choices[0]
                ui.select(choices, label='Número', value=selected['number'],
                          on_change=lambda e: selected.update(number=e.value)).classes('w-full')

            current_turn = game.turn

            def place(position: Position) -> None:
                try:
                    game.place(token, position, selected['number'], current_turn)
                except ValueError as error:
                    notice(error)
                update()

            draw_board(target.board, place, doors_only=not skull and game.roll[0] == 6)

    def update() -> None:
        if seen['revision'] != game.revision:
            seen['revision'] = game.revision
            content.refresh()

    content()
    seen['revision'] = game.revision
    ui.timer(0.7, update)


GROUP_COLORS = (
    '#ffd1dc', '#ffdfba', '#fff2a8', '#d2f3a5', '#a8e6cf',
    '#a3e4e9', '#b5d8ff', '#c4c6ff', '#e1c4ff', '#ffc4f0',
    '#e8b99a', '#d1d992', '#9ed3bc', '#b9c9d6', '#e2c6b3',
)


def score_overlay(analysis: BoardAnalysis) -> str:
    longest_edges = set(zip(analysis.longest_sequence, analysis.longest_sequence[1:]))
    lines = []
    for start, end in sorted(analysis.sequence_edges, key=lambda edge: edge in longest_edges):
        color = '#15803d' if (start, end) in longest_edges else '#64748b'
        width = 8 if (start, end) in longest_edges else 4
        lines.append(f'<line x1="{start[1] * 100 + 50}" y1="{start[0] * 100 + 50}" '
                     f'x2="{end[1] * 100 + 50}" y2="{end[0] * 100 + 50}" '
                     f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
    for row, column in analysis.negative_skulls:
        x, y = column * 100, row * 100
        lines.append(f'<path d="M {x + 20} {y + 20} L {x + 80} {y + 80} '
                     f'M {x + 80} {y + 20} L {x + 20} {y + 80}" '
                     'stroke="#dc2626" stroke-width="9" stroke-linecap="round"/>')
    return ('<svg viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg" '
            'width="100%" height="100%" aria-hidden="true">' + ''.join(lines) + '</svg>')


def draw_board(board: dict[Position, Cell], on_place, doors_only: bool = False,
               analysis: BoardAnalysis | None = None) -> None:
    with ui.element('div').classes('grid grid-cols-6 w-full relative'):
        for row in range(6):
            for column in range(6):
                position = (row, column)
                if position not in board:
                    ui.element('div').classes('aspect-square')
                    continue
                value = board[position]
                door = position in DOORS
                label = str(value) if value is not None else ('🚪' if door else '')
                description = f'Fila {row + 1}, columna {column + 1}, '
                description += str(value) if value is not None else ('puerta vacía' if door else 'vacía')
                if analysis is not None:
                    if position in analysis.group_cells:
                        description += ', grupo puntuable'
                    if position in analysis.positive_skulls:
                        description += ', calavera positiva'
                    elif position in analysis.negative_skulls:
                        description += ', calavera negativa'
                    if position in analysis.longest_sequence:
                        description += ', secuencia puntuable'
                    with ui.element('div').classes(
                            'aspect-square w-full border flex items-center justify-center text-2xl'
                    ).props(f'aria-label="{description}"') as cell:
                        if position in analysis.group_cells and isinstance(value, int):
                            cell.style(f'background-color: {GROUP_COLORS[(value - 1) % len(GROUP_COLORS)]}')
                        if position in analysis.positive_skulls:
                            cell.style('background-color: #86efac')
                        if value is None and door:
                            ui.label(label).style(
                                'font-size: clamp(1.5rem, 11vw, 4.5rem); line-height: 1; transform: scaleX(1.6)'
                            )
                        else:
                            ui.label(label)
                    continue
                enabled = on_place is not None and value is None and door == doors_only
                button = ui.button(label, on_click=lambda e, p=position: on_place(p)).classes(
                    'aspect-square w-full min-w-0 p-0 text-lg'
                ).props(f'outline aria-label="{description}"')
                if value is None and door:
                    button.classes('door-cell')
                    button.style('font-size: clamp(1.5rem, 11vw, 4.5rem); line-height: 1')
                if not enabled:
                    button.disable()
        if analysis is not None:
            ui.html(score_overlay(analysis), sanitize=False).classes(
                'absolute inset-0 w-full h-full pointer-events-none'
            )


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), reload=False,
           title='MathGame1', show=False)
