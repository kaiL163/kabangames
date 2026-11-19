import json
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend import colonist as island, main


class IslandRulesTests(unittest.TestCase):
    def started(self):
        room = {'host': 'creator', 'host_name': 'Ведущий', 'players': {'guest': {'name': 'Друг'}}}
        island.setup(room)
        room['colonist']['bots'] = 1
        island.start(room)
        return room

    def test_initial_placements_and_json_round_trip(self):
        room = self.started()
        game = room['colonist']
        self.assertEqual((len(island.TILES), len(island.VERTICES), len(island.EDGES)), (19, 54, 72))
        self.assertEqual(game['order'], [0, 1, 2, 2, 1, 0])
        island.move(game, 0, {'action': 'home', 'target': 0})
        with self.assertRaisesRegex(ValueError, 'нельзя строить'):
            edge = next(e for e, vertices in enumerate(island.EDGES) if 0 not in vertices)
            island.move(game, 0, {'action': 'road', 'target': edge})
        island.move(game, 0, {'action': 'road', 'target': island.INCIDENT[0][0]})
        self.assertTrue(set(island.NEIGHBORS[0]).isdisjoint(island.available(game, 1)['home']))
        while game['phase'].startswith('setup'):
            self.assertTrue(island.bot_step(game, {0, 1, 2}))
        restored = json.loads(json.dumps(room))
        self.assertEqual(island.view(room, 'creator'), island.view(restored, 'creator'))
        self.assertEqual(len(game['homes']), 6)
        self.assertEqual(len(game['roads']), 6)
        self.assertEqual(game['phase'], 'roll')

    def test_private_hand_and_development_cards(self):
        room = self.started()
        game = room['colonist']
        game['players'][0]['cards'] = [{'kind': 'point', 'turn': 0}]
        game['players'][0]['hand']['ore'] = 4
        host, guest = island.view(room, 'creator'), island.view(room, 'guest')
        self.assertEqual(host['hand']['ore'], 4)
        self.assertEqual(host['players'][0]['points'], 1)
        self.assertEqual(guest['players'][0]['points'], 0)
        self.assertEqual(guest['players'][0]['size'], 4)
        self.assertEqual(guest['cards'], [])
        self.assertNotIn('creator', json.dumps(guest))

    def test_seven_discard_and_trade(self):
        room = self.started()
        game = room['colonist']
        game['phase'] = 'roll'
        hand = game['players'][0]['hand']
        island.transfer(game['bank'], hand, {'wood': 8})
        with patch.object(island.random, 'randint', side_effect=[3, 4]):
            island.move(game, 0, {'action': 'roll'})
        self.assertEqual(game['phase'], 'discard')
        self.assertEqual(game['pending'], {'0': 4})
        island.move(game, 0, {'action': 'discard', 'counts': {'wood': 4}})
        island.move(game, 0, {'action': 'robber', 'target': (game['robber']+1) % 19})
        island.move(game, 0, {'action': 'bank', 'give': 'wood', 'take': 'ore'})
        self.assertEqual(hand['ore'], 1)
        self.assertEqual(game['bank']['wood'], 19)
        other = game['players'][1]['hand']
        island.transfer(game['bank'], other, {'brick': 1})
        island.move(game, 0, {'action': 'offer', 'give': 'ore', 'take': 'brick'})
        island.move(game, 1, {'action': 'accept', 'offer_id': game['offer']['id']})
        self.assertEqual(hand['brick'], 1)
        self.assertEqual(other['ore'], 1)
        self.assertIsNone(game['offer'])

    def test_full_bot_game_reaches_victory(self):
        rng_state = random.getstate()
        self.addCleanup(random.setstate, rng_state)
        random.seed(2026)
        self.assertIn('победа', island.check())


class IslandRoomTests(unittest.IsolatedAsyncioTestCase):
    async def test_room_actions_and_bot_turn_through_normal_endpoints(self):
        with TemporaryDirectory() as data, patch.object(main, 'rooms', {}), patch.object(main, 'ROOMS_FILE', main.Path(data) / 'rooms.json'):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url='http://test') as client:
                created = await client.post('/api/create', json={'name': 'Тестер', 'game_id': 'colonist'})
                self.assertEqual(created.status_code, 200, created.text)
                credentials = {k: created.json()[k] for k in ('code', 'token')}

                async def view():
                    response = await client.post('/api/state', json=credentials)
                    self.assertEqual(response.status_code, 200, response.text)
                    return response.json()['colonist']

                async def action(kind, **fields):
                    game = await view()
                    response = await client.post('/api/colonist/action', json={
                        **credentials, 'instance': game['instance'], 'rev': game['rev'], 'action': kind, **fields,
                    })
                    self.assertEqual(response.status_code, 200, response.text)

                for _ in range(3):
                    await action('add_bot')
                rejected = await client.post('/api/join', json={'code': credentials['code'], 'name': 'Гость'})
                self.assertEqual(rejected.status_code, 409)
                await action('start')
                await action('home', target=(await view())['legal']['home'][0])
                await action('road', target=(await view())['legal']['road'][0])
                with patch.object(island.time, 'time', return_value=10**12):
                    public = await view()
                self.assertEqual(len(public['players']), 4)
                self.assertEqual(public['active'], 1)
                self.assertEqual(len(public['homes']), 2)
