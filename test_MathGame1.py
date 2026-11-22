import unittest
from unittest.mock import patch

from MathGame1 import DOORS, POSITIONS, SKULL, Game, analyze_board, score, score_overlay


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
        with patch('MathGame1.RNG.choice', return_value=(1, 2, 3)):
            self.game.place(self.second.token, door, 2, turn)
        self.assertEqual(self.game.turn, turn + 1)
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
        while self.game.state == 'playing':
            turn = self.game.turn
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
        overlay = score_overlay(analysis)
        self.assertIn('stroke="#dc2626"', overlay)
        self.assertEqual(overlay.count('<path '), 1)

    def test_isolated_number_does_not_score_as_sequence(self):
        board = dict.fromkeys(POSITIONS)
        board[(0, 2)] = 1
        analysis = analyze_board(board)
        self.assertEqual(analysis.scores['secuencias'], 0)
        self.assertEqual(analysis.longest_sequence, [])

    def test_sequence_overlay_marks_scoring_and_other_connections(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3, (4, 0): 10, (5, 0): 11})
        overlay = score_overlay(analyze_board(board))
        self.assertEqual(overlay.count('stroke="#15803d"'), 2)
        self.assertEqual(overlay.count('stroke="#64748b"'), 1)


if __name__ == '__main__':
    unittest.main()
