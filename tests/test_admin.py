import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend import accounts, main


class AdminTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncClient(transport=ASGITransport(app=main.app), base_url='http://testserver')
        self.addAsyncCleanup(self.client.aclose)

    async def test_checks_require_a_privileged_account(self):
        for profile, status in [(None, 401), ({'admin_role': None}, 403)]:
            with self.subTest(status=status), patch.object(accounts, 'current_profile', return_value=profile):
                self.assertEqual((await self.client.get('/api/admin/checks')).status_code, status)
                self.assertEqual((await self.client.post('/api/admin/checks', json={})).status_code, status)

    async def test_tester_can_only_run_checks(self):
        with patch.object(accounts, 'current_profile', return_value={'admin_role': 'tester'}):
            self.assertEqual((await self.client.get('/api/admin/access')).status_code, 403)
            self.assertEqual((await self.client.post('/api/admin/access', json={'username': 'test', 'enabled': True})).status_code, 403)
            self.assertEqual((await self.client.post('/api/admin/checks', json={'game': 'unlisted'})).status_code, 404)
            response = await self.client.post('/api/admin/checks', json={'game': 'quiz'}, headers={'Origin': 'https://other.example'})
            self.assertEqual(response.status_code, 403)

    async def test_every_registered_game_has_a_passing_check(self):
        existing_rooms = dict(main.rooms)
        with patch.object(accounts, 'current_profile', return_value={'admin_role': 'tester'}):
            response = await self.client.post('/api/admin/checks', json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        results = response.json()['results']
        self.assertEqual([result['game'] for result in results], list(main.GAME_MODES))
        self.assertEqual([result for result in results if not result['ok']], [])
        self.assertEqual(main.rooms, existing_rooms)
