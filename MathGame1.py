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

GAME_CSS = '''
    body {
        background: linear-gradient(135deg, #f8f2e5, #e5eee8);
        color: #293d37;
    }
    .q-btn:not(.board-cell) {
        border-radius: 0.75rem;
        box-shadow: 0 3px 0 rgba(31, 62, 55, 0.3), 0 5px 10px rgba(31, 62, 55, 0.12);
        transition: transform 0.12s, box-shadow 0.12s;
    }
    .q-btn:not(.board-cell):active {
        transform: translateY(2px);
        box-shadow: 0 1px 0 rgba(31, 62, 55, 0.3);
    }
    .board-frame {
        padding: 8px;
        border: 3px solid #70452d;
        border-radius: 12px;
        background: repeating-linear-gradient(45deg, #aa7047 0 6px, #c08b5d 6px 12px);
        box-shadow: 0 6px 0 #74462c, 0 12px 18px rgba(57, 40, 26, 0.3),
                    inset 0 2px 3px rgba(255, 237, 199, 0.7), inset 0 0 0 1px #e8c799;
    }
    .board-grid {
        background: #e7f3e5;
    }
    .board-grid.skull-board {
        background: #263d39;
    }
    .board-void {
        background: #b7cfb2;
    }
    .skull-board .board-void {
        background: #142925;
    }
    .board-cell, .board-result-cell {
        border-radius: 6px;
        box-shadow: inset 0 2px 3px rgba(255, 255, 255, 0.55),
                    inset 0 -3px 4px rgba(45, 80, 57, 0.18);
    }
    .board-cell.q-btn--outline::before {
        border-width: 2px;
        border-radius: inherit;
        background: linear-gradient(160deg, rgba(255, 255, 255, 0.5), rgba(147, 183, 151, 0.15));
    }
    .skull-board .board-cell.q-btn--outline::before {
        background: linear-gradient(160deg, rgba(179, 209, 195, 0.2), rgba(4, 20, 18, 0.2));
    }
    .board-result-cell {
        border-width: 2px;
        border-color: #60766a;
    }
    .status-badge {
        max-width: 100%;
        padding: 0.4rem 0.8rem;
        border: 1px solid rgba(66, 94, 76, 0.22);
        border-radius: 0.8rem;
        box-shadow: 0 3px 0 rgba(68, 87, 67, 0.2), 0 5px 10px rgba(49, 67, 52, 0.12),
                    inset 0 1px 2px rgba(255, 255, 255, 0.8);
    }
    .status-player {
        background: linear-gradient(#edf8df, #d6ebca);
    }
    .status-turn {
        background: linear-gradient(#fff0cc, #f8dca4);
    }
    .die-face {
        position: relative;
        width: clamp(54px, 16vw, 72px);
        aspect-ratio: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 2px solid #aebfb7;
        border-radius: 17%;
        background: linear-gradient(145deg, #fffefa, #dce8df);
        box-shadow: inset 0 2px 3px #fff, inset 0 -3px 4px rgba(67, 94, 77, 0.18),
                    0 5px 0 #aabbb0, 0 8px 10px rgba(40, 61, 48, 0.22);
    }
    .die-face:nth-child(1) { transform: rotate(-3deg); }
    .die-face:nth-child(3) { transform: rotate(3deg); }
    .die-face.ignored::after {
        content: '';
        position: absolute;
        left: -6%;
        top: calc(50% - 2px);
        width: 112%;
        height: 4px;
        border-radius: 2px;
        background: #dc2626;
        transform: rotate(-45deg);
        pointer-events: none;
    }
    .die-pips {
        width: 70%;
        height: 70%;
        display: grid;
        grid-template: repeat(3, 1fr) / repeat(3, 1fr);
        place-items: center;
    }
    .die-pip {
        width: 60%;
        aspect-ratio: 1;
        border-radius: 50%;
        background: #294c42;
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.35);
    }
    .die-symbol {
        font-size: clamp(30px, 9vw, 42px);
        line-height: 1;
    }
'''


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
    shorter_sequence_edges: list[tuple[Position, Position]]
    group_cells: set[Position]
    positive_skulls: set[Position]
    negative_skulls: set[Position]


def analyze_board(board: dict[Position, Cell]) -> BoardAnalysis:
    """Calcula la puntuación y las casillas que la explican."""
    numbers = {position: value for position, value in board.items() if isinstance(value, int)}
    paths: dict[Position, list[Position]] = {}
    prefix_lengths: dict[Position, set[int]] = {}
    predecessors_by_position: dict[Position, list[Position]] = {}
    edges: list[tuple[Position, Position]] = []
    ordered = sorted(numbers, key=lambda pos: (numbers[pos], pos))
    for position in ordered:
        predecessors = [other for other in neighbors(position)
                        if numbers.get(other) == numbers[position] - 1]
        predecessors_by_position[position] = predecessors
        edges.extend((other, position) for other in predecessors)
        paths[position] = (max((paths[other] for other in predecessors), key=len, default=[])
                           + [position])
        prefix_lengths[position] = ({length + 1 for other in predecessors
                                     for length in prefix_lengths[other]} or {1})
    longest = max(paths.values(), key=len, default=[])
    if len(longest) < 2:
        longest = []

    successors: dict[Position, list[Position]] = {position: [] for position in ordered}
    for position, predecessors in predecessors_by_position.items():
        for predecessor in predecessors:
            successors[predecessor].append(position)
    suffix_lengths: dict[Position, set[int]] = {}
    for position in reversed(ordered):
        suffix_lengths[position] = ({length + 1 for other in successors[position]
                                     for length in suffix_lengths[other]} or {1})
    shorter_edges = [(start, end) for start, end in edges
                     if any(3 <= prefix + suffix < len(longest)
                            for prefix in prefix_lengths[start] for suffix in suffix_lengths[end])]

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
    return BoardAnalysis(scores, longest, edges, shorter_edges, group_cells, positive_skulls, negative_skulls)


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
    ready: set[str] = field(default_factory=set)
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
        self.ready.clear()
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
        self.state = 'playing'
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
            self.state = 'between_turns'

    def continue_turn(self, token: str, turn: int) -> None:
        if self.state != 'between_turns' or turn != self.turn:
            raise ValueError('El turno ya ha cambiado. Espera la actualización.')
        if not any(player.token == token for player in self.players):
            raise ValueError('No perteneces a esta partida.')
        if token in self.ready:
            raise ValueError('Ya has confirmado que estás preparado.')
        self.ready.add(token)
        self.revision += 1
        if len(self.ready) == len(self.players):
            self.next_turn()

    def place_random(self, token: str, turn: int) -> tuple[Position, int]:
        if self.state != 'playing' or self.roll is None or turn != self.turn:
            raise ValueError('El turno ya ha cambiado. Espera la actualización.')
        if token in self.submitted:
            raise ValueError('Ya has jugado en este turno.')
        choices = self.choices()
        positions = [pos for pos, value in self.player(token).board.items()
                     if value is None and (pos in DOORS) == (self.roll[0] == 6)]
        if not choices or not positions:
            raise ValueError('No hay números o casillas disponibles en este turno.')
        number = RNG.choice(choices)
        position = RNG.choice(positions)
        self.place(token, position, number, turn)
        return position, number


def create_game(name: str) -> tuple[Game, Player]:
    while True:
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        if code not in ROOMS:
            break
    game = Game(code)
    player = game.add_player(name)
    ROOMS[code] = game
    return game, player


def draw_roll(roll: tuple[int, int, int]) -> None:
    pip_positions = {
        1: (4,),
        2: (0, 8),
        3: (0, 4, 8),
        4: (0, 2, 6, 8),
        5: (0, 2, 4, 6, 8),
    }
    specials = ((KEY, 'llave'), (HEART, 'corazón'), (SKULL, 'calavera'))
    with ui.row().classes('gap-3'):
        for index, value in enumerate(roll):
            symbol, name = specials[index]
            description = name if value == 6 else str(value)
            ignored = roll[2] == 6 and index < 2
            if ignored:
                description += ', no se aplica'
            with ui.element('div').classes('die-face ignored' if ignored else 'die-face').props(
                    f'role=img aria-label="Dado {index + 1}: {description}"'):
                if value == 6:
                    ui.label(symbol).classes('die-symbol').props('aria-hidden=true')
                else:
                    with ui.element('div').classes('die-pips').props('aria-hidden=true'):
                        for position in pip_positions[value]:
                            ui.element('span').classes('die-pip').style(
                                f'grid-area: {position // 3 + 1} / {position % 3 + 1}')


def notice(error: ValueError) -> None:
    ui.notify(str(error), type='negative')


@ui.page('/')
def index() -> None:
    ui.page_title('MathGame1')
    ui.add_css(GAME_CSS)
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

        @ui.refreshable
        def available_games(codes: tuple[str, ...]) -> None:
            if codes:
                ui.label('Partidas disponibles: ' + ', '.join(codes))
                ui.button('Unirse a la partida', on_click=join).classes('w-full')
                ui.button('Crear partida', on_click=create).props('outline').classes('w-full')
            else:
                ui.button('Crear partida', on_click=create).classes('w-full')
                ui.button('Unirse a la partida', on_click=join).props('outline').classes('w-full')

        def waiting_codes() -> tuple[str, ...]:
            return tuple(sorted(game.code for game in ROOMS.values() if game.state == 'waiting'))

        seen_codes = waiting_codes()
        available_games(seen_codes)

        def update_available_games() -> None:
            nonlocal seen_codes
            codes = waiting_codes()
            if codes != seen_codes:
                seen_codes = codes
                available_games.refresh(codes)

        ui.timer(0.7, update_available_games)
        ui.label('Cada persona juega desde su propio dispositivo.').classes('text-sm text-grey-7')


@ui.page('/partida')
def game_page(token: str = '') -> None:
    ui.add_css(GAME_CSS)
    game = TOKENS.get(token)
    if game is None:
        ui.label('La partida no existe o ha caducado.').classes('text-lg')
        ui.link('Volver al inicio', '/')
        return
    player = game.player(token)
    ui.page_title('MathGame1 - partida')
    selected: dict[str, int | None] = {'number': None, 'turn': None}
    seen = {'revision': -1}

    @ui.refreshable
    def content() -> None:
        with ui.column().classes('w-full max-w-xl mx-auto p-3 gap-3'):
            ui.label(f'Partida {game.code}').classes('text-2xl font-bold')
            ui.label(f'Jugador: {player.name}').classes('status-badge status-player')
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
                results = sorted(((p, analyze_board(p.board)) for p in game.players),
                                 key=lambda item: item[1].scores['total'], reverse=True)
                best = max(analysis.scores['total'] for _, analysis in results)
                winners = ', '.join(p.name for p, analysis in results if analysis.scores['total'] == best)
                ui.label(f'Ganador(es): {winners}').classes('text-xl font-bold')
                ui.label('Clasificación').classes('text-lg font-bold')
                board_dialog = ui.dialog()

                def show_board(p: Player, analysis: BoardAnalysis) -> None:
                    board_dialog.clear()
                    with board_dialog, ui.card().classes('w-full max-w-xl'):
                        ui.label(f'Tablero de {p.name}').classes('text-lg font-bold')
                        ui.label('Línea verde: secuencia puntuable; gris discontinua: secuencia menor '
                                 'de al menos 3 casillas. Fondo de color: grupo; verde: calavera positiva; '
                                 'cruz roja: negativa.').classes('text-sm')
                        draw_board(p.board, None, analysis=analysis)
                        ui.button('Cerrar', on_click=board_dialog.close)
                    board_dialog.open()

                rank = 0
                previous_total = None
                for index, (p, analysis) in enumerate(results, start=1):
                    result = analysis.scores
                    if result['total'] != previous_total:
                        rank = index
                        previous_total = result['total']
                    ui.label(f"{rank}. {p.name}: {result['total']} puntos "
                             f"(secuencias {result['secuencias']}, grupos {result['grupos']}, "
                             f"calaveras {result['calaveras']:+})").classes('font-bold')
                    ui.button(f'Ver tablero de {p.name}',
                              on_click=lambda e, player=p, result=analysis: show_board(player, result)).props('outline')
                ui.link('Nueva partida', '/')
                return

            assert game.roll is not None
            skull = game.roll[2] == 6
            done = token in game.submitted
            ui.label(f'Turno {game.turn}').classes('status-badge status-turn text-lg font-bold')
            draw_roll(game.roll)
            ui.label(f'Jugadores que han terminado el turno: {len(game.submitted)}/{len(game.players)}')
            ui.linear_progress(value=len(game.submitted) / len(game.players),
                               size='12px', show_value=False).props('rounded').classes('w-full')
            if game.state == 'between_turns':
                ui.label('Turno completado. Pulsa para continuar.').classes('text-xl font-bold')
                ui.label(f'Jugadores preparados: {len(game.ready)}/{len(game.players)}')
                if token in game.ready:
                    ui.label('Esperando a que los demás jugadores continúen.')
                else:
                    current_turn = game.turn

                    def continue_game() -> None:
                        try:
                            game.continue_turn(token, current_turn)
                        except ValueError as error:
                            notice(error)
                        update()

                    ui.button('Continuar', on_click=continue_game).classes('w-full')
                return
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
                ui.label('Si eliges un número incorrecto, se colocará uno válido al azar.').classes('text-sm')
                if selected['turn'] != game.turn:
                    selected.update(number=None, turn=game.turn)

            current_turn = game.turn

            def choose(number: int) -> None:
                if game.state != 'playing' or game.turn != current_turn or token in game.submitted:
                    notice(ValueError('El turno ya ha cambiado o ya has jugado.'))
                    update()
                    return
                if number in game.choices():
                    selected['number'] = number
                    content.refresh()
                    return
                try:
                    position, placed = game.place_random(token, current_turn)
                except ValueError as error:
                    notice(error)
                else:
                    ui.notify(f'Número incorrecto: se ha colocado {placed} en la fila {position[0] + 1}, '
                              f'columna {position[1] + 1}.', type='warning')
                update()

            if not skull:
                with ui.element('div').classes('grid grid-cols-5 gap-2 w-full'):
                    for number in range(1, 16):
                        button = ui.button(str(number), on_click=lambda e, n=number: choose(n)).classes('w-full')
                        if number != selected['number']:
                            button.props('outline')

            def place(position: Position) -> None:
                try:
                    game.place(token, position, selected['number'], current_turn)
                except ValueError as error:
                    notice(error)
                update()

            draw_board(target.board, place if skull or selected['number'] is not None else None,
                       doors_only=not skull and game.roll[0] == 6, skull_target=skull)

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


def overlay_svg(shapes: list[str]) -> str:
    return ('<svg viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg" '
            'width="100%" height="100%" aria-hidden="true">' + ''.join(shapes) + '</svg>')


def score_overlay(analysis: BoardAnalysis) -> str:
    longest_edges = set(zip(analysis.longest_sequence, analysis.longest_sequence[1:]))
    lines = []
    displayed_edges = [(edge, False) for edge in analysis.shorter_sequence_edges if edge not in longest_edges]
    displayed_edges.extend((edge, True) for edge in zip(analysis.longest_sequence, analysis.longest_sequence[1:]))
    for (start, end), scoring in displayed_edges:
        color = '#15803d' if scoring else '#64748b'
        width = 8 if scoring else 4
        dash = '' if scoring else ' stroke-dasharray="12 8"'
        lines.append(f'<line x1="{start[1] * 100 + 50}" y1="{start[0] * 100 + 50}" '
                     f'x2="{end[1] * 100 + 50}" y2="{end[0] * 100 + 50}" '
                     f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"{dash}/>')
    return overlay_svg(lines)


def skull_overlay(analysis: BoardAnalysis) -> str:
    crosses = []
    for row, column in analysis.negative_skulls:
        x, y = column * 100, row * 100
        crosses.append(f'<path d="M {x + 20} {y + 20} L {x + 80} {y + 80} '
                       f'M {x + 80} {y + 20} L {x + 20} {y + 80}" '
                       'stroke="#dc2626" stroke-width="9" stroke-linecap="round"/>')
    return overlay_svg(crosses)


def draw_board(board: dict[Position, Cell], on_place, doors_only: bool = False,
               analysis: BoardAnalysis | None = None, skull_target: bool = False) -> None:
    grid_classes = 'board-grid grid grid-cols-6 w-full relative aspect-square'
    if skull_target:
        grid_classes += ' skull-board'
    with ui.element('div').classes('board-frame w-full'), \
            ui.element('div').classes(grid_classes).style(
                'grid-template-rows: repeat(6, minmax(0, 1fr)); container-type: inline-size'):
        for row in range(6):
            for column in range(6):
                position = (row, column)
                if position not in board:
                    ui.element('div').classes('board-void aspect-square')
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
                            'board-result-cell w-full h-full min-w-0 min-h-0 overflow-hidden '
                            'border flex items-center justify-center text-2xl'
                    ).props(f'aria-label="{description}"') as cell:
                        if position in analysis.group_cells and isinstance(value, int):
                            cell.style(f'background-color: {GROUP_COLORS[(value - 1) % len(GROUP_COLORS)]}')
                        if position in analysis.positive_skulls:
                            cell.style('background-color: #86efac')
                        text = ui.label(label).classes('relative z-20')
                        if (value is None and door) or value == SKULL:
                            text.style('font-size: calc(100cqw / 6 * 0.8); line-height: 1')
                    continue
                enabled = on_place is not None and value is None and door == doors_only
                button = ui.button(label, on_click=lambda e, p=position: on_place(p)).classes(
                    'board-cell w-full h-full min-w-0 min-h-0 overflow-hidden p-0 text-lg'
                ).props(f'outline aria-label="{description}"')
                if skull_target:
                    button.props('color=white')
                if (value is None and door) or value == SKULL:
                    button.style('font-size: calc(100cqw / 6 * 0.8); line-height: 1')
                if not enabled:
                    button.disable()
        if analysis is not None:
            ui.html(score_overlay(analysis), sanitize=False).classes(
                'absolute inset-0 w-full h-full pointer-events-none z-10'
            )
            ui.html(skull_overlay(analysis), sanitize=False).classes(
                'absolute inset-0 w-full h-full pointer-events-none z-30'
            )


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), reload=False,
           title='MathGame1', show=False)
