import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend import accounts, main, sandbox


class SandboxTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.account_id = 100
        self.role = 'tester'
        self.client = AsyncClient(transport=ASGITransport(app=main.app), base_url='http://testserver')
        self.addAsyncCleanup(self.client.aclose)
        self.addCleanup(sandbox.sessions.clear)
        profile = patch.object(accounts, 'current_profile', side_effect=self.profile)
        profile.start()
        self.addCleanup(profile.stop)

    async def profile(self, request):
        request.state.account_id = self.account_id
        return {'admin_role': self.role, 'nickname': 'Ведущий', 'avatar': 'brand'}

    async def open_room(self, game, bots=3):
        response = await self.client.post('/api/admin/sandbox', json={'game': game, 'bots': bots})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['id']

    async def seat(self, test_id, player=None):
        response = await self.client.post(f'/api/admin/sandbox/{test_id}/seat', json={'seat': player})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def play(self, test_id, player, path='state', **fields):
        return await self.client.post(f'/api/{path}',
                                      json={'code': player['code'], 'token': player['token'], **fields},
                                      headers={'X-Kaban-Test-Room': test_id})

    async def bots(self, test_id, player):
        response = await self.client.post(f'/api/admin/sandbox/{test_id}/step', json={'seat': player['seat']})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['actions']

    async def test_quiz_lobby_plays_the_same_round_from_both_seats(self):
        test_id = await self.open_room('quiz')
        host = await self.seat(test_id)
        bot = await self.seat(test_id, 'bot1')
        self.assertNotIn(sandbox.TEST_CODE, main.rooms)
        self.assertTrue(host['host'])
        self.assertFalse(bot['host'])
        self.assertNotEqual(host['token'], bot['token'])
        self.assertEqual(len(host['participants']), 4)
        self.assertEqual(await self.bots(test_id, host), 3)
        start = await self.play(test_id, host, 'quiz/start', game_id='quiz', rounds=5)
        self.assertEqual(start.status_code, 200, start.text)
        state = (await self.play(test_id, bot)).json()
        self.assertFalse(state['is_host'])
        self.assertIsNone(state['video'])
        self.assertEqual(state['quiz']['instance'], start.json()['instance'])
        self.assertEqual(await self.bots(test_id, bot), 2)
        state = (await self.play(test_id, bot)).json()
        self.assertFalse(state['quiz']['answered'])
        self.assertEqual(state['quiz']['answers_count'], 2)
        for player in (host, bot):
            response = await self.play(test_id, player, 'quiz/answer', round=1, instance=state['quiz']['instance'], choice=0)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.play(test_id, bot)).json()['quiz']['phase'], 'result')

    async def test_access_is_scoped_to_an_active_role_and_room_owner(self):
        test_id = await self.open_room('detective')
        player = await self.seat(test_id)
        public = await self.client.post('/api/state', json={'code': player['code'], 'token': player['token']})
        self.assertEqual(public.status_code, 404)
        self.account_id = 101
        self.assertEqual((await self.play(test_id, player)).status_code, 404)
        self.assertEqual((await self.client.get('/api/admin/sandbox')).json()['rooms'], [])
        self.account_id = 100
        self.role = None
        self.assertEqual((await self.play(test_id, player)).status_code, 403)
        self.role = 'tester'
        self.assertEqual((await self.client.delete(f'/api/admin/sandbox/{test_id}')).status_code, 200)
        self.assertEqual((await self.play(test_id, player)).status_code, 404)

    async def test_codenames_switch_keeps_server_side_role_privacy(self):
        test_id = await self.open_room('codenames', 3)
        host = await self.seat(test_id)
        setup = (await self.play(test_id, host)).json()['codenames']
        credentials = {'instance': setup['instance'], 'turn': setup['turn_number']}
        for fields in ({'action': 'seat', 'team': 'red', 'role': 'captain'}, {'action': 'ready'}):
            response = await self.play(test_id, host, 'codenames/action', **(credentials | fields))
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(await self.bots(test_id, host), 3)
        response = await self.play(test_id, host, 'codenames/action', **(credentials | {'action': 'start'}))
        self.assertEqual(response.status_code, 200, response.text)
        for participant in host['participants']:
            player = await self.seat(test_id, participant['id'])
            view = (await self.play(test_id, player)).json()['codenames']
            visible = any(card['color'] is not None for card in view['cards'])
            self.assertEqual(visible, view['me']['role'] == 'captain')

    async def test_world_bots_leave_the_viewed_country_under_player_control(self):
        test_id = await self.open_room('domination', 3)
        host = await self.seat(test_id)
        bot = await self.seat(test_id, 'bot1')
        self.assertEqual(await self.bots(test_id, host), 3)
        for action in ('ready', 'start'):
            game = (await self.play(test_id, host)).json()['tabletop']
            response = await self.play(test_id, host, 'tabletop/action', instance=game['instance'],
                                       revision=game['revision'], action=action)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(await self.bots(test_id, bot), 1)
        after = (await self.play(test_id, bot)).json()['tabletop']
        self.assertEqual(after['phase'], 'dev')
        self.assertEqual(len(after['countries']), 1)
        self.assertFalse(after['countries'][0]['done'])
        self.assertEqual(after['countries'][0]['money'], 500)
