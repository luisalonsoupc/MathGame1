import unittest
from unittest.mock import patch

from MathGame1 import DOORS, POSITIONS, SKULL, Game, score


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
        self.assertTrue(all(all(value is not None for value in p.board.values()) for p in self.game.players))
        self.assertGreaterEqual(self.game.turn, 30)

    def test_scoring(self):
        board = dict.fromkeys(POSITIONS)
        board.update({(0, 2): 1, (0, 3): 2, (1, 4): 3,
                      (3, 0): 7, (3, 1): 7, (4, 0): 7,
                      (3, 4): 7, (3, 5): 7, (4, 5): 7,
                      (5, 0): SKULL, (5, 1): 9, (5, 5): SKULL})
        self.assertEqual(score(board), {'secuencias': 3, 'grupos': 3, 'calaveras': 0, 'total': 6})


if __name__ == '__main__':
    unittest.main()
