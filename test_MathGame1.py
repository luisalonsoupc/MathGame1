import asyncio
import unittest
from unittest.mock import MagicMock, patch

from MathGame1 import (CONNECTIONS, DISCONNECT_TASKS, DOORS, HEART, KEY, POSITIONS, ROOMS, SKULL,
                       TOKENS, Game, analyze_board, connect_player, create_game, disconnect_player,
                       draw_board, draw_roll, expire_games, game_page, index, score, score_overlay,
                       skull_overlay)


class IndexTests(unittest.TestCase):
    def test_waiting_games_update_without_recreating_inputs(self):
        buttons = []
        labels = {}
        inputs = {}

        def make_button(*args, **kwargs):
            button = MagicMock()
            buttons.append(button)
            return button

        def make_label(text):
            label = MagicMock()
            label.classes.return_value = label
            label.set_visibility.return_value = label
            labels[text] = label
            return label

        def make_input(text, **kwargs):
            element = MagicMock()
            element.classes.return_value = element
            element.props.return_value = element
            element.set_visibility.return_value = element
            inputs[text] = element
            return element

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(ROOMS, {}, clear=True), patch('MathGame1.ui') as ui:
            ui.button.side_effect = make_button
            ui.label.side_effect = make_label
            ui.input.side_effect = make_input
            ui.refreshable.side_effect = refreshable
            index()
            update = ui.timer.call_args.args[1]
            self.assertIn('Math Game 1', ui.html.call_args.args[0])

            self.assertEqual([call.args[0] for call in ui.button.call_args_list],
                             ['Crear partida'])
            buttons[0].props.assert_not_called()
            inputs['Código de partida'].set_visibility.assert_called_once_with(False)
            inputs['Tu nombre'].set_visibility.assert_not_called()
            for label in labels.values():
                label.set_visibility.assert_called_once_with(False)
            inputs['Tu nombre'].value = 'Ana'

            ROOMS['NEW123'] = Game('NEW123')
            update()
            ui.label.assert_any_call('Partidas disponibles: NEW123')
            self.assertEqual([call.args[0] for call in ui.button.call_args_list[-2:]],
                             ['Unirse a la partida', 'Crear partida'])
            inputs['Código de partida'].set_visibility.assert_called_with(True)
            self.assertEqual(inputs['Tu nombre'].value, 'Ana')
            ROOMS.clear()
            update()

            ROOMS['PLAYIN'] = Game('PLAYIN', state='playing')
            update()
            self.assertEqual([call.args[0] for call in ui.button.call_args_list[-2:]],
                             ['Crear partida', 'Unirse a la partida'])
            inputs['Código de partida'].set_visibility.assert_called_with(True)
            self.assertEqual(inputs['Tu nombre'].value, 'Ana')

            ROOMS.update({'Z12345': Game('Z12345'), 'A12345': Game('A12345'),
                          'FINISH': Game('FINISH', state='finished')})
            update()
            ui.label.assert_any_call('Partidas disponibles: A12345, Z12345')
            self.assertEqual([call.args[0] for call in ui.button.call_args_list[-2:]],
                             ['Unirse a la partida', 'Crear partida'])
            buttons[-2].props.assert_not_called()
            buttons[-1].props.assert_called_once_with('outline')

            update()
            self.assertEqual(ui.button.call_count, 8)
            ROOMS['A12345'].state = 'playing'
            update()
            ui.label.assert_any_call('Partidas disponibles: Z12345')
            ROOMS['Z12345'].state = 'playing'
            update()
            self.assertEqual([call.args[0] for call in ui.button.call_args_list[-2:]],
                             ['Crear partida', 'Unirse a la partida'])
            ROOMS.clear()
            update()
            self.assertEqual(ui.button.call_args.args[0], 'Crear partida')
            inputs['Código de partida'].set_visibility.assert_called_with(False)
            self.assertEqual(ui.input.call_count, 2)

    def test_creation_dialog_validates_and_applies_optional_time(self):
        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(ROOMS, {}, clear=True), patch.dict(TOKENS, {}, clear=True), \
                patch('MathGame1.ui') as ui:
            ui.refreshable.side_effect = refreshable
            ui.input.return_value.classes.return_value.value = 'Ana'
            checkbox, continue_checkbox = MagicMock(value=False), MagicMock(value=False)
            seconds, continue_seconds = MagicMock(value=30), MagicMock(value=15)
            ui.checkbox.side_effect = [checkbox, continue_checkbox]
            ui.number.side_effect = [MagicMock(bind_visibility_from=MagicMock(return_value=seconds)),
                                     MagicMock(bind_visibility_from=MagicMock(return_value=continue_seconds))]
            index()
            ui.button.call_args.kwargs['on_click']()
            self.assertEqual(ROOMS, {})
            confirm = next(call.kwargs['on_click'] for call in ui.button.call_args_list
                           if call.args[0] == 'Crear')
            checkbox.value = True
            seconds.value = 0
            confirm()
            self.assertEqual(ROOMS, {})
            ui.notify.assert_called_once()
            seconds.value = 12
            continue_checkbox.value = True
            continue_seconds.value = 0
            confirm()
            self.assertEqual(ROOMS, {})
            continue_seconds.value = 7
            confirm()
            self.assertEqual(next(iter(ROOMS.values())).turn_seconds, 12)
            self.assertEqual(next(iter(ROOMS.values())).continue_seconds, 7)


class DiceTests(unittest.TestCase):
    def test_numeric_faces_show_correct_pips_and_accessible_values(self):
        elements = []

        def element(tag):
            item = MagicMock()
            item.classes.return_value = item
            item.props.return_value = item
            elements.append(item)
            return item

        with patch('MathGame1.ui') as ui:
            ui.element.side_effect = element
            draw_roll((1, 2, 5))

        faces = [item for item in elements if item.classes.call_args.args[0] == 'die-face']
        self.assertEqual([item.props.call_args.args[0] for item in faces], [
            'role=img aria-label="Dado 1: 1"',
            'role=img aria-label="Dado 2: 2"',
            'role=img aria-label="Dado 3: 5"',
        ])
        pips = [item.style.call_args.args[0] for item in elements
                if item.classes.call_args.args[0] == 'die-pip']
        self.assertEqual(pips, [
            'grid-area: 2 / 2',
            'grid-area: 1 / 1', 'grid-area: 3 / 3',
            'grid-area: 1 / 1', 'grid-area: 1 / 3', 'grid-area: 2 / 2',
            'grid-area: 3 / 1', 'grid-area: 3 / 3',
        ])

    def test_special_faces_show_the_right_symbols(self):
        with patch('MathGame1.ui') as ui:
            draw_roll((6, 6, 6))
            self.assertEqual([call.args[0] for call in ui.label.call_args_list], [KEY, HEART, SKULL])
            props = [call.args[0] for call in ui.element.return_value.classes.return_value.props.call_args_list]
            self.assertEqual(props, ['role=img aria-label="Dado 1: llave, no se aplica"',
                                     'role=img aria-label="Dado 2: corazón, no se aplica"',
                                     'role=img aria-label="Dado 3: calavera"'])
            classes = [call.args[0] for call in ui.element.return_value.classes.call_args_list]
            self.assertEqual(classes, ['die-face ignored', 'die-face ignored', 'die-face'])

    def test_numeric_dice_are_crossed_only_when_skull_is_rolled(self):
        for roll, expected in [((2, 3, 6), ['die-face ignored', 'die-face ignored', 'die-face']),
                               ((2, 6, 4), ['die-face', 'die-face', 'die-face'])]:
            with self.subTest(roll=roll), patch('MathGame1.ui') as ui:
                draw_roll(roll)
                classes = [call.args[0] for call in ui.element.return_value.classes.call_args_list
                           if call.args[0].startswith('die-face')]
                self.assertEqual(classes, expected)


class TimedGameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game('TEST', turn_seconds=10)
        self.first = self.game.add_player('Ana')
        self.second = self.game.add_player('Luis')

    def test_creation_defaults_to_unlimited_and_rejects_invalid_limits(self):
        with patch.dict(ROOMS, {}, clear=True), patch.dict(TOKENS, {}, clear=True):
                game, _ = create_game('Ana')
                self.assertIsNone(game.turn_seconds)
                for value in (0, -1, 1.5, True, '10'):
                    with self.subTest(value=value), self.assertRaises(ValueError):
                        create_game('Luis', value)
                game, _ = create_game('Luis', 10)
                self.assertEqual(game.turn_seconds, 10)

    def test_deadline_is_exact_and_restart_waits_for_both_players(self):
        with patch('MathGame1.time.monotonic', return_value=100), \
                    patch('MathGame1.RNG.choice', side_effect=lambda values: (
                        (2, 3, 4) if (2, 3, 4) in values else values[0])):
                self.game.start(self.first.token)
                self.assertEqual(self.game.deadline, 110)
                self.assertEqual(self.game.remaining_seconds(), 10)
                self.game.place(self.first.token, POSITIONS[0], 2, self.game.turn)
        with patch('MathGame1.time.monotonic', return_value=109.9):
                self.game.expire_turn()
                self.assertEqual(self.game.remaining_seconds(), 1)
                self.assertEqual(self.game.submitted, {self.first.token})
        with patch('MathGame1.time.monotonic', return_value=110), \
                    patch('MathGame1.RNG.choice', side_effect=lambda values: values[0]):
                self.game.expire_turn()
                self.game.expire_turn()
                self.assertEqual(self.game.timed_out, {self.second.token})
                self.assertEqual(sum(v is not None for v in self.first.board.values()), 1)
                self.assertEqual(sum(v is not None for v in self.second.board.values()), 1)
                self.assertIsNone(self.game.deadline)
                self.assertEqual(self.game.state, 'between_turns')
                self.game.continue_turn(self.first.token, self.game.turn)
                self.assertIsNone(self.game.deadline)
        with patch('MathGame1.time.monotonic', return_value=200), \
                    patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
                self.game.continue_turn(self.second.token, self.game.turn)
        self.assertEqual(self.game.deadline, 210)
        self.assertEqual(self.game.timed_out, set())

    def test_automatic_moves_respect_roll_and_skull_targets(self):
        for roll in ((2, 3, 4), (6, 2, 3), (2, 6, 4), (2, 3, 6)):
                with self.subTest(roll=roll):
                    game = Game('TEST', turn_seconds=5)
                    ana, luis = game.add_player('Ana'), game.add_player('Luis')
                    with patch('MathGame1.time.monotonic', return_value=10), \
                            patch('MathGame1.RNG.choice', return_value=roll):
                        game.start(ana.token)
                    expected_choices = game.choices()
                    with patch('MathGame1.time.monotonic', return_value=15), \
                            patch('MathGame1.RNG.choice', side_effect=lambda values: values[-1]):
                        game.expire_turn()
                    self.assertEqual(game.timed_out, {ana.token, luis.token})
                    for p in (ana, luis):
                        board = game.player(game.targets[p.token]).board if roll[2] == 6 else p.board
                        filled = [(pos, value) for pos, value in board.items() if value is not None]
                        self.assertEqual(len(filled), 1)
                        pos, value = filled[0]
                        self.assertEqual(pos in DOORS, roll[0] == 6 and roll[2] != 6)
                        if roll[2] == 6:
                            self.assertEqual(value, SKULL)
                        else:
                            self.assertIn(value, expected_choices)

    def test_automatic_move_skips_passed_players_and_works_without_clients(self):
        for pos in DOORS:
                self.first.board[pos] = 1
        with patch('MathGame1.time.monotonic', return_value=10), \
                    patch('MathGame1.RNG.choice', return_value=(6, 2, 3)):
                self.game.start(self.first.token)
        self.assertEqual(self.game.submitted, {self.first.token})
        with patch.dict(ROOMS, {'TEST': self.game}, clear=True), \
                    patch('MathGame1.time.monotonic', return_value=20), \
                    patch('MathGame1.RNG.choice', side_effect=lambda values: values[0]):
                expire_games()
        self.assertEqual(self.game.timed_out, {self.second.token})
        self.assertEqual(self.game.state, 'between_turns')

    def test_unlimited_game_does_not_expire_and_late_placement_is_rejected(self):
        self.game.turn_seconds = None
        with patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
                self.game.start(self.first.token)
        self.game.expire_turn()
        self.assertIsNone(self.game.remaining_seconds())
        self.assertEqual(self.game.submitted, set())
        self.game.deadline = 10
        with patch('MathGame1.time.monotonic', return_value=10), \
                    patch('MathGame1.RNG.choice', side_effect=lambda values: values[0]):
                with self.assertRaises(ValueError):
                    self.game.place(self.first.token, POSITIONS[-1], 2, self.game.turn)
        self.assertEqual(sum(v is not None for v in self.first.board.values()), 1)
        self.assertIsNone(self.first.board[POSITIONS[-1]])


class ContinueTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.game = Game('TEST', turn_seconds=20, continue_seconds=5)
        self.ana, self.luis = self.game.add_player('Ana'), self.game.add_player('Luis')
        with patch('MathGame1.time.monotonic', return_value=100), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            self.game.start(self.ana.token)
            self.game.place(self.ana.token, POSITIONS[0], 2, self.game.turn)
            self.game.place(self.luis.token, POSITIONS[0], 2, self.game.turn)

    def test_limit_starts_when_turn_ends_and_expires_without_clients(self):
        self.assertEqual(self.game.continue_deadline, 105)
        with patch('MathGame1.time.monotonic', return_value=104.9):
            self.game.continue_turn(self.ana.token, 1)
            self.game.expire_continue()
            self.assertEqual(self.game.continue_remaining_seconds(), 1)
            self.assertEqual(self.game.state, 'between_turns')
        with patch.dict(ROOMS, {'TEST': self.game}, clear=True), \
                patch('MathGame1.time.monotonic', return_value=105), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            expire_games()
            expire_games()
        self.assertEqual(self.game.turn, 2)
        self.assertEqual(self.game.state, 'playing')
        self.assertEqual(self.game.deadline, 125)
        self.assertIsNone(self.game.continue_deadline)
        self.assertEqual(self.game.ready, set())

    def test_late_click_advances_once_and_is_rejected(self):
        with patch('MathGame1.time.monotonic', return_value=105), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            with self.assertRaises(ValueError):
                self.game.continue_turn(self.ana.token, 1)
        self.assertEqual(self.game.turn, 2)
        self.assertEqual(self.game.state, 'playing')

    def test_all_confirmations_advance_early(self):
        with patch('MathGame1.time.monotonic', return_value=102), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            self.game.continue_turn(self.ana.token, 1)
            self.game.continue_turn(self.luis.token, 1)
        self.assertEqual(self.game.turn, 2)
        self.assertIsNone(self.game.continue_deadline)

    def test_no_limit_waits_and_invalid_settings_are_rejected(self):
        self.game.continue_deadline = None
        self.game.continue_seconds = None
        with patch('MathGame1.time.monotonic', return_value=10000):
            self.game.expire_continue()
        self.assertEqual(self.game.state, 'between_turns')
        for value in (0, -1, 1.5, True, '10'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                create_game('Ana', continue_seconds=value)

    def test_expiry_after_final_move_displays_results(self):
        for p in self.game.players:
            for pos in POSITIONS:
                if pos not in DOORS:
                    p.board[pos] = 1
        with patch('MathGame1.time.monotonic', return_value=105):
            self.game.expire_continue()
        self.assertEqual(self.game.state, 'finished')
        self.assertIsNone(self.game.continue_deadline)

    def test_departure_that_completes_turn_starts_continue_limit(self):
        game = Game('TEST', continue_seconds=5)
        players = [game.add_player(name) for name in ('Ana', 'Luis', 'María')]
        with patch('MathGame1.time.monotonic', return_value=100), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            game.start(players[0].token)
            for p in players[:2]:
                game.place(p.token, POSITIONS[0], 2, game.turn)
            game.remove_player(players[2].token)
        self.assertEqual(game.state, 'between_turns')
        self.assertEqual(game.continue_deadline, 105)

    def test_expired_playing_turn_starts_separate_continue_limit(self):
        game = Game('TEST', turn_seconds=10, continue_seconds=5)
        ana, luis = game.add_player('Ana'), game.add_player('Luis')
        with patch('MathGame1.time.monotonic', return_value=100), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            game.start(ana.token)
        with patch.dict(ROOMS, {'TEST': game}, clear=True), \
                patch('MathGame1.time.monotonic', return_value=110), \
                patch('MathGame1.RNG.choice', side_effect=lambda values: values[0]):
            expire_games()
        self.assertEqual(game.timed_out, {ana.token, luis.token})
        self.assertEqual(game.continue_deadline, 115)
        self.assertEqual(game.state, 'between_turns')


class DisconnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_waits_and_reconnection_or_other_tab_prevents_removal(self):
        game = Game('TEST')
        ana = game.add_player('Ana')
        game.add_player('Luis')
        with patch.dict(TOKENS, {p.token: game for p in game.players}, clear=True), \
                patch.dict(CONNECTIONS, {}, clear=True), patch.dict(DISCONNECT_TASKS, {}, clear=True), \
                patch('MathGame1.DISCONNECT_GRACE_SECONDS', 0.02):
            connect_player(game, ana.token, 'first')
            connect_player(game, ana.token, 'second')
            disconnect_player(game, ana.token, 'first')
            self.assertNotIn(ana.token, DISCONNECT_TASKS)
            disconnect_player(game, ana.token, 'second')
            await asyncio.sleep(0.005)
            connect_player(game, ana.token, 'third')
            await asyncio.sleep(0.03)
            self.assertIn(ana, game.players)
            disconnect_player(game, ana.token, 'third')
            await asyncio.sleep(0.03)
            self.assertNotIn(ana, game.players)
            self.assertNotIn(ana.token, TOKENS)

    def test_waiting_host_transfers_and_empty_room_is_removed(self):
        game = Game('TEST')
        ana, luis = game.add_player('Ana'), game.add_player('Luis')
        with patch.dict(ROOMS, {'TEST': game}, clear=True), \
                patch.dict(TOKENS, {ana.token: game, luis.token: game}, clear=True):
            game.remove_player(ana.token)
            self.assertIs(game.players[0], luis)
            self.assertNotIn(ana.token, TOKENS)
            game.remove_player(luis.token)
            self.assertNotIn('TEST', ROOMS)

    def test_departure_unblocks_playing_and_between_turns(self):
        for state in ('playing', 'between_turns'):
            with self.subTest(state=state):
                game = Game('TEST')
                ana, luis, maria = [game.add_player(name) for name in ('Ana', 'Luis', 'María')]
                with patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
                    game.start(ana.token)
                if state == 'playing':
                    game.place(ana.token, POSITIONS[0], 2, game.turn)
                    game.place(luis.token, POSITIONS[0], 2, game.turn)
                    game.remove_player(maria.token)
                    self.assertEqual(game.state, 'between_turns')
                else:
                    for p in game.players:
                        game.place(p.token, POSITIONS[0], 2, game.turn)
                    game.continue_turn(ana.token, game.turn)
                    game.continue_turn(luis.token, game.turn)
                    with patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
                        game.remove_player(maria.token)
                    self.assertEqual(game.state, 'playing')
                    self.assertEqual(game.turn, 2)

    def test_last_remaining_player_finishes_and_is_ranked(self):
        game = Game('TEST', turn_seconds=10)
        ana, luis = game.add_player('Ana'), game.add_player('Luis')
        with patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            game.start(ana.token)
        game.remove_player(luis.token)
        self.assertEqual(game.players, [ana])
        self.assertEqual(game.state, 'finished')
        self.assertTrue(game.ended_early)
        self.assertIsNone(game.deadline)

    def test_skull_target_is_reassigned_and_full_target_passes(self):
        game = Game('TEST')
        ana, luis, maria = [game.add_player(name) for name in ('Ana', 'Luis', 'María')]
        for pos in POSITIONS:
            if pos not in DOORS:
                maria.board[pos] = 1
        with patch('MathGame1.RNG.choice', return_value=(2, 3, 6)), \
                patch('MathGame1.RNG.shuffle'):
            game.start(ana.token)
        self.assertEqual(game.targets[ana.token], luis.token)
        game.remove_player(luis.token)
        self.assertEqual(game.targets[ana.token], maria.token)
        self.assertEqual(game.targets[maria.token], ana.token)
        self.assertIn(ana.token, game.submitted)
        self.assertNotIn(maria.token, game.submitted)
        game.place(maria.token, POSITIONS[0], None, game.turn)
        self.assertEqual(ana.board[POSITIONS[0]], SKULL)
        self.assertEqual(game.state, 'between_turns')


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game('TEST')
        self.first = self.game.add_player('Ana')
        self.second = self.game.add_player('Luis')

    def test_board_shape_and_doors(self):
        self.assertEqual([sum(row == r for row, _ in POSITIONS) for r in range(6)],
                         [2, 4, 6, 6, 6, 6])
        self.assertEqual(DOORS, {(1, 3), (2, 2), (3, 3), (4, 0), (4, 5), (5, 2), (5, 3)})
        self.assertEqual(len(self.first.board), 30)

    def test_choices_and_special_dice(self):
        self.game.roll = (2, 3, 4)
        self.assertEqual(self.game.choices(), [2, 3, 4, 5, 6, 7, 9])
        self.game.roll = (6, 6, 4)
        self.assertEqual(self.game.choices(), [4])
        self.game.roll = (2, 6, 4)
        self.assertEqual(self.game.choices(), list(range(1, 16)))
        self.game.roll = (6, 6, 6)
        self.assertEqual(self.game.choices(), [])

    def test_incorrect_number_uses_valid_random_number_and_empty_matching_cell(self):
        for roll, door in [((2, 3, 4), False), ((6, 2, 3), True)]:
            with self.subTest(roll=roll):
                self.game.state = 'playing'
                self.game.roll = roll
                self.game.turn += 1
                self.game.submitted.clear()
                positions = [pos for pos in POSITIONS if (pos in DOORS) == door]
                self.first.board[positions[0]] = 10
                with patch('MathGame1.RNG.choice', side_effect=lambda values: values[-1]) as choose:
                    position, number = self.game.place_random(self.first.token, self.game.turn)
                self.assertEqual(choose.call_args_list[0].args[0], self.game.choices())
                self.assertNotIn(positions[0], choose.call_args_list[1].args[0])
                self.assertTrue(all((pos in DOORS) == door for pos in choose.call_args_list[1].args[0]))
                self.assertEqual(self.first.board[position], number)
                self.assertIn(self.first.token, self.game.submitted)

    def test_random_placement_rejects_stale_submitted_and_skull_turns(self):
        self.game.state = 'playing'
        self.game.roll = (2, 3, 4)
        self.game.turn = 2
        with patch('MathGame1.RNG.choice') as choose:
            with self.assertRaises(ValueError):
                self.game.place_random(self.first.token, 1)
            self.game.submitted.add(self.first.token)
            with self.assertRaises(ValueError):
                self.game.place_random(self.first.token, 2)
            self.game.submitted.clear()
            self.game.roll = (2, 3, 6)
            with self.assertRaises(ValueError):
                self.game.place_random(self.first.token, 2)
            choose.assert_not_called()

    def test_placement_validation_and_turn_barrier(self):
        with patch('MathGame1.RNG.choice', return_value=(6, 2, 3)):
            self.game.start(self.first.token)
        turn = self.game.turn
        door = next(iter(DOORS))
        normal = next(pos for pos in POSITIONS if pos not in DOORS)
        with self.assertRaises(ValueError):
            self.game.place(self.first.token, normal, 2, turn)
        with self.assertRaises(ValueError):
            self.game.place(self.first.token, door, 6, turn)
        self.game.place(self.first.token, door, 5, turn)
        with self.assertRaises(ValueError):
            self.game.place(self.first.token, door, 5, turn)
        self.assertEqual(self.game.turn, turn)
        self.game.place(self.second.token, door, 2, turn)
        self.assertEqual(self.game.state, 'between_turns')
        self.assertEqual(self.game.turn, turn)
        self.game.continue_turn(self.first.token, turn)
        self.assertEqual(self.game.state, 'between_turns')
        with self.assertRaises(ValueError):
            self.game.continue_turn(self.first.token, turn)
        with self.assertRaises(ValueError):
            self.game.continue_turn('invalid-token', turn)
        with self.assertRaises(ValueError):
            self.game.continue_turn(self.second.token, turn + 1)
        with patch('MathGame1.RNG.choice', return_value=(1, 2, 3)):
            self.game.continue_turn(self.second.token, turn)
        self.assertEqual(self.game.turn, turn + 1)
        self.assertEqual(self.game.state, 'playing')
        self.assertEqual(self.game.ready, set())
        with self.assertRaises(ValueError):
            self.game.place(self.first.token, normal, 1, turn)

    def test_skulls_are_anonymous_other_boards_and_override_dice(self):
        with patch('MathGame1.RNG.choice', return_value=(6, 6, 6)):
            self.game.start(self.first.token)
        self.assertEqual(self.game.targets[self.first.token], self.second.token)
        pos = next(pos for pos in POSITIONS if pos not in DOORS)
        self.game.place(self.first.token, pos, None, self.game.turn)
        self.assertEqual(self.second.board[pos], SKULL)
        self.assertIsNone(self.first.board[pos])

    def test_rerolls_and_skull_passes(self):
        self.game.state = 'playing'
        for player in self.game.players:
            for pos in DOORS:
                player.board[pos] = 1
        with patch('MathGame1.RNG.choice', side_effect=lambda rolls: self.assertTrue(
                all(roll[0] != 6 or roll[2] == 6 for roll in rolls)) or (1, 1, 1)):
            self.game.next_turn()
        for pos in POSITIONS:
            if pos not in DOORS:
                self.second.board[pos] = 1
        with patch('MathGame1.RNG.choice', return_value=(1, 1, 6)):
            self.game.next_turn()
        self.assertIn(self.first.token, self.game.submitted)
        self.assertNotIn(self.second.token, self.game.submitted)

    def test_complete_game(self):
        with patch('MathGame1.RNG.choice', return_value=(1, 1, 1)):
            self.game.start(self.first.token)
            while self.game.state != 'finished':
                turn = self.game.turn
                if self.game.state == 'between_turns':
                    for player in self.game.players:
                        self.game.continue_turn(player.token, turn)
                    continue
                for player in self.game.players:
                    if player.token in self.game.submitted:
                        continue
                    roll = self.game.roll
                    skull = roll[2] == 6
                    target = self.game.player(self.game.targets[player.token]) if skull else player
                    door = not skull and roll[0] == 6
                    pos = next(pos for pos in POSITIONS if (pos in DOORS) == door and target.board[pos] is None)
                    self.game.place(player.token, pos, None if skull else self.game.choices()[0], turn)
        self.assertTrue(all(all(p.board[pos] is not None for pos in POSITIONS if pos not in DOORS)
                            for p in self.game.players))

    def test_game_finishes_with_empty_doors(self):
        self.game.state = 'playing'
        for player in self.game.players:
            for pos in POSITIONS:
                if pos not in DOORS:
                    player.board[pos] = 1
        self.game.next_turn()
        self.assertEqual(self.game.state, 'finished')
        self.assertIsNone(self.game.roll)

    def test_players_without_matching_cells_pass(self):
        self.game.state = 'playing'
        for pos in POSITIONS:
            if pos not in DOORS:
                self.first.board[pos] = 1
            else:
                self.second.board[pos] = 1
        with patch('MathGame1.RNG.choice', side_effect=lambda rolls: (
                self.assertIn((1, 1, 1), rolls) or (1, 1, 1))):
            self.game.next_turn()
        self.assertIn(self.first.token, self.game.submitted)
        self.assertNotIn(self.second.token, self.game.submitted)
        with patch('MathGame1.RNG.choice', return_value=(6, 1, 1)):
            self.game.next_turn()
        self.assertNotIn(self.first.token, self.game.submitted)
        self.assertIn(self.second.token, self.game.submitted)

    def test_last_normal_placement_finishes_game(self):
        self.game.state = 'playing'
        normal_positions = [pos for pos in POSITIONS if pos not in DOORS]
        for player in self.game.players:
            for pos in normal_positions:
                player.board[pos] = 1
        last = normal_positions[-1]
        self.second.board[last] = None
        with patch('MathGame1.RNG.choice', return_value=(1, 1, 1)):
            self.game.next_turn()
        self.assertIn(self.first.token, self.game.submitted)
        self.game.place(self.second.token, last, 1, self.game.turn)
        self.assertEqual(self.game.state, 'between_turns')
        self.game.continue_turn(self.first.token, self.game.turn)
        self.assertEqual(self.game.state, 'between_turns')
        self.game.continue_turn(self.second.token, self.game.turn)
        self.assertEqual(self.game.state, 'finished')
        self.assertTrue(any(value is None for value in self.second.board.values()))

    def test_scoring(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3,
                      (3, 0): 7, (3, 1): 7, (4, 0): 7,
                      (3, 4): 7, (3, 5): 7, (4, 5): 7,
                      (5, 0): SKULL, (5, 1): 9, (5, 5): SKULL})
        self.assertEqual(score(board), {'secuencias': 3, 'grupos': 3, 'calaveras': 0, 'total': 6})

    def test_only_longest_increasing_sequence_scores(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3, (2, 5): 4,
                      (4, 0): 10, (5, 0): 11, (5, 5): 8})
        analysis = analyze_board(board)
        self.assertEqual(analysis.scores['secuencias'], 4)
        self.assertEqual([board[pos] for pos in analysis.longest_sequence], [1, 2, 3, 4])
        self.assertIn(((4, 0), (5, 0)), analysis.sequence_edges)

    def test_scoring_annotations_match_groups_and_skulls(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(2, 0): 7, (2, 1): 7, (3, 0): 7,
                      (4, 4): 8, (4, 5): 8, (5, 5): 8,
                      (0, 2): SKULL, (1, 1): 9, (5, 0): SKULL})
        analysis = analyze_board(board)
        self.assertEqual(analysis.scores['grupos'], 6)
        self.assertEqual(analysis.group_cells, {(2, 0), (2, 1), (3, 0), (4, 4), (4, 5), (5, 5)})
        self.assertEqual(analysis.positive_skulls, {(0, 2)})
        self.assertEqual(analysis.negative_skulls, {(5, 0)})
        overlay = skull_overlay(analysis)
        self.assertIn('stroke="#dc2626"', overlay)
        self.assertEqual(overlay.count('<path '), 1)
        self.assertNotIn('stroke="#dc2626"', score_overlay(analysis))

    def test_scoring_lines_and_skull_crosses_use_separate_layers(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): SKULL, (2, 0): 1, (2, 1): 2})
        analysis = analyze_board(board)
        overlays = [MagicMock(), MagicMock()]
        with patch('MathGame1.ui') as ui:
            ui.html.side_effect = overlays
            draw_board(board, None, analysis=analysis)
            self.assertIn('stroke="#15803d"', ui.html.call_args_list[0].args[0])
            self.assertNotIn('stroke="#dc2626"', ui.html.call_args_list[0].args[0])
            self.assertIn('stroke="#dc2626"', ui.html.call_args_list[1].args[0])
            self.assertNotIn('stroke="#15803d"', ui.html.call_args_list[1].args[0])
            self.assertIn('z-10', overlays[0].classes.call_args.args[0])
            self.assertIn('z-30', overlays[1].classes.call_args.args[0])

    def test_isolated_number_does_not_score_as_sequence(self):
        board = dict.fromkeys(POSITIONS)
        board[(0, 2)] = 1
        analysis = analyze_board(board)
        self.assertEqual(analysis.scores['secuencias'], 0)
        self.assertEqual(analysis.longest_sequence, [])

    def test_sequence_overlay_only_shows_shorter_complete_paths_of_at_least_three(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3, (2, 5): 4,
                      (3, 0): 7, (4, 0): 8, (5, 0): 9,
                      (4, 4): 12, (5, 5): 13})
        overlay = score_overlay(analyze_board(board))
        self.assertEqual(overlay.count('stroke="#15803d"'), 3)
        self.assertEqual(overlay.count('stroke="#64748b"'), 2)
        self.assertEqual(overlay.count('stroke-dasharray="12 8"'), 2)

    def test_tied_longest_paths_are_not_shown_as_shorter_sequences(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3,
                      (3, 0): 7, (4, 0): 8, (5, 0): 9})
        overlay = score_overlay(analyze_board(board))
        self.assertEqual(overlay.count('stroke="#15803d"'), 2)
        self.assertNotIn('stroke="#64748b"', overlay)

    def test_short_branch_of_long_sequence_is_shown(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3, (2, 5): 4, (1, 2): 3})
        analysis = analyze_board(board)
        self.assertIn(((0, 3), (1, 2)), analysis.shorter_sequence_edges)
        self.assertIn(((0, 2), (0, 3)), analysis.shorter_sequence_edges)
        overlay = score_overlay(analysis)
        self.assertEqual(overlay.count('stroke="#15803d"'), 3)
        self.assertEqual(overlay.count('stroke="#64748b"'), 1)


class GamePageTests(unittest.TestCase):
    def test_nicegui_2_disconnect_handler_does_not_depend_on_stale_tab_id(self):
        game = Game('TEST')
        player = game.add_player('Ana')
        with patch.dict(TOKENS, {player.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.nicegui_version', '2.0.0'), \
                patch('MathGame1.disconnect_player') as disconnect:
            ui.refreshable.side_effect = lambda render: render
            ui.context.client.has_socket_connection = True
            game_page(player.token)
            ui.context.client.on_disconnect.call_args.args[0]()
            disconnect.assert_called_once_with(game, player.token, ui.context.client.id)

    def test_continue_countdown_updates_without_redrawing(self):
        game = Game('TEST', continue_seconds=5)
        ana, luis = game.add_player('Ana'), game.add_player('Luis')
        with patch('MathGame1.time.monotonic', return_value=100), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            game.start(ana.token)
            game.place(ana.token, POSITIONS[0], 2, game.turn)
            game.place(luis.token, POSITIONS[0], 2, game.turn)

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        labels = {}

        def make_label(text):
            label = MagicMock()
            label.classes.return_value = label
            labels[text] = label
            return label

        with patch.dict(TOKENS, {ana.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board, \
                patch('MathGame1.time.monotonic', return_value=100):
            ui.refreshable.side_effect = refreshable
            ui.label.side_effect = make_label
            game_page(ana.token)
            label = labels['Continuación automática en 5 s']
            with patch('MathGame1.time.monotonic', return_value=103):
                ui.timer.call_args.args[1]()
            label.set_text.assert_called_once_with('Continuación automática en 2 s')
            board.assert_not_called()

    def test_clock_updates_without_redrawing_board_and_late_choice_expires(self):
        game = Game('TEST', turn_seconds=10)
        ana, luis = game.add_player('Ana'), game.add_player('Luis')
        with patch('MathGame1.time.monotonic', return_value=100), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            game.start(ana.token)

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(TOKENS, {ana.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board, \
                patch('MathGame1.time.monotonic', return_value=100):
            ui.refreshable.side_effect = refreshable
            labels = {}

            def make_label(text):
                label = MagicMock()
                label.classes.return_value = label
                labels[text] = label
                return label

            ui.label.side_effect = make_label
            game_page(ana.token)
            ui.label.assert_any_call('⏱ 10 s')
            self.assertNotIn('Tu tiempo', labels)
            clock = labels['⏱ 10 s']
            clock.set_text.reset_mock()
            clock.classes.reset_mock()
            update = ui.timer.call_args.args[1]
            choice = next(call.kwargs['on_click'] for call in ui.button.call_args_list
                          if call.args[0] == '2')
            update()
            clock.classes.assert_called_with(add=None, remove='clock-warning')
            with patch('MathGame1.time.monotonic', return_value=101):
                update()
            clock.set_text.assert_called_with('⏱ 9 s')
            clock.classes.assert_called_with(add='clock-warning', remove=None)
            with patch('MathGame1.time.monotonic', return_value=105):
                update()
            self.assertEqual(board.call_count, 1)
            clock.set_text.assert_called_with('⏱ 5 s')
            with patch('MathGame1.time.monotonic', return_value=110), \
                    patch('MathGame1.RNG.choice', side_effect=lambda values: values[0]):
                choice(None)
            self.assertEqual(game.timed_out, {ana.token, luis.token})
            self.assertEqual(game.state, 'between_turns')
            ui.label.assert_any_call('Tiempo agotado · jugada automática')

    def test_each_player_sees_only_their_own_clock_and_status(self):
        game = Game('TEST', turn_seconds=10)
        ana, luis = game.add_player('Ana'), game.add_player('Luis')
        with patch('MathGame1.time.monotonic', return_value=100), \
                patch('MathGame1.RNG.choice', return_value=(2, 3, 4)):
            game.start(ana.token)
            game.place(ana.token, POSITIONS[0], 2, game.turn)

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        for player, expected, other in (
                (ana, 'Turno completado o pasado', '⏱ 10 s'),
                (luis, '⏱ 10 s', 'Turno completado o pasado')):
            with self.subTest(player=player.name), \
                    patch.dict(TOKENS, {player.token: game}, clear=True), \
                    patch('MathGame1.ui') as ui, patch('MathGame1.draw_board'), \
                    patch('MathGame1.time.monotonic', return_value=100):
                ui.refreshable.side_effect = refreshable
                game_page(player.token)
                labels = [call.args[0] for call in ui.label.call_args_list]
                self.assertIn(expected, labels)
                self.assertNotIn(other, labels)

    def test_completed_turn_shows_progress_and_waits_for_each_player(self):
        game = Game('TEST')
        ana = game.add_player('Ana')
        luis = game.add_player('Luis')
        game.state = 'between_turns'
        game.roll = (2, 3, 4)
        game.turn = 1
        game.submitted.update((ana.token, luis.token))

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(TOKENS, {ana.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board:
            ui.refreshable.side_effect = refreshable
            game_page(ana.token)
            ui.linear_progress.assert_called_with(value=1, size='12px', show_value=False)
            board.assert_not_called()
            ui.label.assert_any_call('Turno completado. Pulsa para continuar.')
            ui.button.call_args.kwargs['on_click']()
            self.assertEqual(game.ready, {ana.token})
            self.assertEqual(game.state, 'between_turns')
            ui.label.assert_any_call('Esperando a que los demás jugadores continúen.')
            ui.label.assert_any_call('Jugadores preparados: 1/2')

    def test_skull_target_board_is_dark_and_progress_tracks_submissions(self):
        game = Game('TEST')
        ana = game.add_player('Ana')
        luis = game.add_player('Luis')
        game.state = 'playing'
        game.roll = (2, 3, 6)
        game.turn = 1
        game.targets[ana.token] = luis.token
        game.submitted.add(luis.token)

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(TOKENS, {ana.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board:
            ui.refreshable.side_effect = refreshable
            game_page(ana.token)
            ui.linear_progress.assert_called_with(value=0.5, size='12px', show_value=False)
            self.assertIs(board.call_args.args[0], luis.board)
            self.assertTrue(board.call_args.kwargs['skull_target'])

    def test_results_rank_players_and_open_only_requested_board(self):
        game = Game('TEST')
        ana = game.add_player('Ana')
        luis = game.add_player('Luis')
        maria = game.add_player('María')
        ana.board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3})
        maria.board.update({(0, 2): 4, (0, 3): 5, (1, 4): 6})
        luis.board[(0, 2)] = SKULL
        game.state = 'finished'

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(TOKENS, {ana.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board:
            ui.refreshable.side_effect = refreshable
            game_page(ana.token)
            labels = [call.args[0] for call in ui.label.call_args_list]
            ranking = [label for label in labels if label.startswith(('1.', '3.'))]
            self.assertEqual(ranking, [
                '1. Ana: 3 puntos (secuencias 3, grupos 0, calaveras +0)',
                '1. María: 3 puntos (secuencias 3, grupos 0, calaveras +0)',
                '3. Luis: -2 puntos (secuencias 0, grupos 0, calaveras -2)',
            ])
            board.assert_not_called()
            buttons = {call.args[0]: call.kwargs['on_click'] for call in ui.button.call_args_list}
            ui.label.reset_mock()
            buttons['Ver tablero de Luis'](None)
            self.assertIs(board.call_args.args[0], luis.board)
            ui.label.assert_any_call('-2 puntos (secuencias 0, grupos 0, calaveras -2)')
            ui.label.reset_mock()
            buttons['Ver tablero de Ana'](None)
            self.assertIs(board.call_args.args[0], ana.board)
            ui.label.assert_any_call('3 puntos (secuencias 3, grupos 0, calaveras +0)')
            self.assertEqual(ui.dialog.return_value.clear.call_count, 2)
            self.assertEqual(ui.dialog.return_value.open.call_count, 2)

    def test_number_selection_and_penalty(self):
        game = Game('TEST')
        player = game.add_player('Ana')
        game.add_player('Luis')
        game.state = 'playing'
        game.roll = (2, 3, 4)
        game.turn = 1

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(TOKENS, {player.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board:
            ui.refreshable.side_effect = refreshable
            game_page(player.token)
            calls = ui.button.call_args_list
            self.assertEqual([call.args[0] for call in calls], [str(n) for n in range(1, 16)])
            self.assertIsNone(board.call_args.args[1])

            calls[1].kwargs['on_click'](None)
            self.assertIsNotNone(board.call_args.args[1])
            self.assertEqual(game.submitted, set())

            invalid_click = ui.button.call_args_list[-1].kwargs['on_click']
            with patch('MathGame1.RNG.choice', side_effect=lambda values: values[0]):
                invalid_click(None)
            self.assertIn(player.token, game.submitted)
            self.assertEqual(sum(value is not None for value in player.board.values()), 1)
            ui.notify.assert_called_once()

            invalid_click(None)
            self.assertEqual(sum(value is not None for value in player.board.values()), 1)

    def test_heart_allows_all_numbers_and_selection_resets_next_turn(self):
        game = Game('TEST')
        player = game.add_player('Ana')
        game.add_player('Luis')
        game.state = 'playing'
        game.roll = (2, 6, 4)
        game.turn = 1

        def refreshable(render):
            wrapped = MagicMock(side_effect=render)
            wrapped.refresh.side_effect = render
            return wrapped

        with patch.dict(TOKENS, {player.token: game}, clear=True), \
                patch('MathGame1.ui') as ui, patch('MathGame1.draw_board') as board:
            ui.refreshable.side_effect = refreshable
            game_page(player.token)
            ui.button.call_args_list[-1].kwargs['on_click'](None)
            self.assertIsNotNone(board.call_args.args[1])
            self.assertEqual(game.submitted, set())
            position = next(pos for pos in POSITIONS if pos not in DOORS)
            board.call_args.args[1](position)
            self.assertEqual(player.board[position], 15)

            game.submitted.clear()
            game.turn += 1
            game.revision += 1
            ui.timer.call_args.args[1]()
            self.assertIsNone(board.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
