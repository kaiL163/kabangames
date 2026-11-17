import copy
import json
import time
import unittest
from unittest.mock import patch
from backend import tabletop as tt

class TabletopTests(unittest.TestCase):
    def room(self,kind='boss',count=10):
        room={'host':'p0','host_name':'Player 0','players':{f'p{i}':{'name':f'Player {i}'} for i in range(1,count)}}
        if kind=='domination':room={'host':'gm','host_name':'Game Master','players':{f'p{i}':{'name':f'Player {i}'} for i in range(count)}}
        tt.setup(room,kind)
        for i in range(count):
            self.act(room,f'p{i}','seat',team='join' if kind=='boss' else str(i%2))
            self.act(room,f'p{i}','ready')
        if kind=='domination':self.act(room,'gm','ready')
        return room
    def act(self,room,token,action,**kw):
        if room['host']=='gm' and token=='p0' and action in ('advance','start','reset'):token='gm'
        g=room['tabletop'];return tt.action(room,token,dict(instance=g['instance'],revision=g['revision'],action=action,**kw))
    def start(self,kind='boss',count=10):
        r=self.room(kind,count);self.act(r,'p0','start');return r
    def token(self,r,p):return next(t for t,x in r['tabletop']['members'].items() if x['id']==p['id'])
    def test_hat_deal_balanced_and_secret(self):
        r=self.start();g=r['tabletop']
        self.assertEqual(sum(p['color']=='blue' for p in tt.members(g)),5)
        self.assertEqual(sum(p['room']=='A' for p in tt.members(g)),5)
        self.assertEqual(sum(p['role']=='boss' for p in tt.members(g)),1)
        self.assertEqual(sum(p['role']=='saboteur' for p in tt.members(g)),1)
        for token,p in g['members'].items():
            v=tt.view(r,token)
            self.assertEqual(len(v['players']),5)
            self.assertTrue(all('role' not in x and x['color'] is None for x in v['players']))
            self.assertEqual(v['me']['role'],p['role'])
        self.assertEqual(tt.view(r,'observer')['players'],[])
    def test_readiness_minimum_and_even_count(self):
        for n in (4,7):
            r=self.room(count=n)
            with self.assertRaises(ValueError):self.act(r,'p0','start')
        r=self.room();r['tabletop']['members']['p1']['ready']=False
        with self.assertRaises(ValueError):self.act(r,'p0','start')
    def test_hat_chat_isolation_and_escaping_input(self):
        r=self.start();g=r['tabletop'];p=g['members']['p0']
        self.act(r,'p0','chat',text='<script>hello</script>')
        self.assertEqual(len(tt.view(r,'p0')['messages']),1)
        other=next(t for t,x in g['members'].items() if x['room']!=p['room'])
        self.assertEqual(tt.view(r,other)['messages'],[])
        self.assertEqual(tt.view(r,'observer')['messages'],[])
    def test_hat_commissar_and_quiet(self):
        r=self.start();g=r['tabletop']
        officer=next(p for p in tt.members(g) if p['role']=='commissar');token=self.token(r,officer)
        target=next(p for p in tt.members(g) if p['room']==officer['room'] and p!=officer)
        self.act(r,token,'check',target=target['id'])
        self.assertEqual(tt.view(r,token)['me']['checked']['role'],target['role'])
        self.assertIsNone(tt.view(r,self.token(r,target))['me']['checked'])
        with self.assertRaises(ValueError):self.act(r,token,'check',target=target['id'])
        quiet=next(p for p in tt.members(g) if p['role']=='quiet')
        with self.assertRaises(ValueError):self.act(r,self.token(r,quiet),'show')
    def test_cross_room_actions_rejected(self):
        r=self.start();g=r['tabletop'];p=g['members']['p0']
        other=next(x for x in tt.members(g) if x['room']!=p['room'])
        with self.assertRaises(ValueError):self.act(r,'p0','vote',target=other['id'])
    def test_hat_election_exchange_simultaneous_and_final(self):
        r=self.start();g=r['tabletop']
        for round_number in range(3):
            self.act(r,'p0','advance')
            a=tt.by_id(g,g['hats']['A']);b=tt.by_id(g,g['hats']['B'])
            self.act(r,self.token(r,a),'send',target=a['id'])
            self.assertEqual(a['room'],'A')
            self.assertNotIn('sent',tt.view(r,self.token(r,b)))
            self.act(r,self.token(r,b),'send',target=b['id'])
            self.assertEqual(a['room'],'B');self.assertEqual(b['room'],'A')
        self.assertEqual(g['phase'],'finished')
        boss=next(p for p in tt.members(g) if p['role']=='boss');bomb=next(p for p in tt.members(g) if p['role']=='saboteur')
        self.assertEqual(g['winner'],'red' if boss['room']==bomb['room'] else 'blue')
    def test_hat_timeout_does_not_skip_exchange(self):
        r=self.start();g=r['tabletop'];g['deadline']=0;tt.tick(g)
        self.assertEqual(g['phase'],'exchange');self.assertEqual(g['round'],1)
    def test_world_start_capacity_and_ownership(self):
        r=self.room('domination',6)
        r['players']['p6']={'name':'Player 6'}
        with self.assertRaises(ValueError):self.act(r,'p6','seat',team='0')
        with self.assertRaises(ValueError):self.act(r,'p1','seat',team='gm')
        self.act(r,'p0','start');g=r['tabletop']
        self.assertEqual(len(g['countries']),2)
        self.act(r,'p0','invest',city='0',target='1')
        self.assertEqual(tt.team(g,'0')['money'],400);self.assertEqual(tt.team(g,'0')['cities'][0]['level'],1)
        self.assertEqual(tt.team(g,'1')['cities'][0]['level'],0)
    def test_world_spending_and_limits(self):
        r=self.start('domination',2);g=r['tabletop'];t=tt.team(g,'0')
        for _ in range(3):self.act(r,'p0','invest',city='0')
        with self.assertRaises(ValueError):self.act(r,'p0','invest',city='0')
        self.act(r,'p0','eco');self.assertEqual(t['money'],50)
        with self.assertRaises(ValueError):self.act(r,'p0','shield',city='0')
        self.assertEqual(t['money'],50)
    def test_world_income_sanctions_once(self):
        r=self.start('domination',2);g=r['tabletop']
        self.act(r,'p0','sanction',target='1')
        self.act(r,'p0','advance')
        self.act(r,'p0','advance')
        self.assertEqual(g['phase'],'review')
        self.assertEqual(tt.team(g,'0')['money'],650);self.assertEqual(tt.team(g,'1')['money'],620)
        for _ in range(4):tt.view(r,'p0')
        self.assertEqual(tt.team(g,'1')['money'],620)
        self.act(r,'p0','advance');self.assertFalse(tt.team(g,'1')['sanction'])
    def test_world_research_build_shield_attack(self):
        r=self.start('domination',2);g=r['tabletop']
        with self.assertRaises(ValueError):self.act(r,'p0','build')
        self.act(r,'p0','research');self.act(r,'p1','shield',city='0')
        self.act(r,'p0','advance');self.act(r,'p0','advance');self.act(r,'p0','advance')
        self.act(r,'p0','build');self.assertEqual(tt.team(g,'0')['nukes'],1)
        self.act(r,'p0','attack',target='1',city='0')
        self.assertFalse(tt.team(g,'1')['cities'][0]['shield']);self.assertFalse(tt.team(g,'1')['cities'][0]['destroyed'])
        with self.assertRaises(ValueError):self.act(r,'p0','attack',target='1',city='0')
        with self.assertRaises(ValueError):self.act(r,'p0','build')
    def test_world_team_chat_private_and_direct(self):
        r=self.start('domination',2)
        self.act(r,'p0','chat',team='team',text='secret')
        self.assertEqual(tt.view(r,'p1')['messages'],[])
        self.act(r,'p0','advance');self.act(r,'p0','negotiate',target='1')
        invitation=tt.view(r,'p1')['negotiations'][0]['id']
        self.act(r,'p1','accept',negotiation=invitation)
        self.act(r,'p0','chat',target='1',text='alliance?')
        self.assertEqual(len(tt.view(r,'p1')['messages']),1)
    def test_world_done_and_authority(self):
        r=self.start('domination',2);g=r['tabletop']
        with self.assertRaises(ValueError):self.act(r,'p1','advance')
        with self.assertRaises(ValueError):self.act(r,'p0','reward',target='1',amount=1000)
        self.act(r,'p0','done')
        with self.assertRaises(ValueError):self.act(r,'p0','invest',city='0')
        self.act(r,'p1','done');self.assertEqual(g['phase'],'talk')
    def test_world_tied_victory_and_last_country(self):
        r=self.start('domination',2);g=r['tabletop'];tt.finish_world(g)
        self.assertIn(tt.COUNTRIES[0],g['winner']);self.assertIn(tt.COUNTRIES[1],g['winner'])
    def test_world_full_five_rounds(self):
        r=self.start('domination',2);g=r['tabletop']
        for round_number in range(1,6):
            self.assertEqual(g['round'],round_number)
            self.act(r,'p0','done');self.act(r,'p1','done')
            self.act(r,'p0','advance')
            self.assertEqual(g['phase'],'review')
            self.act(r,'p0','advance')
        self.assertEqual(g['phase'],'finished')
        self.assertEqual(tt.team(g,'0')['money'],1250)

    def test_gm_rewards_are_private_and_bounded(self):
        r=self.room('domination',3);self.act(r,'gm','start');self.act(r,'gm','advance');self.act(r,'gm','advance')
        self.act(r,'gm','reward',target='1',amount=200)
        self.assertEqual(tt.team(r['tabletop'],'1')['money'],850)
        self.assertIn('200',tt.view(r,'p1')['log'][-1]['text'])
        with self.assertRaises(ValueError):self.act(r,'gm','reward',target='1',amount=-1000)
        with self.assertRaises(ValueError):self.act(r,'p1','reward',target='1',amount=200)

    def test_serialization_stale_and_reset(self):
        r=self.start();g=r['tabletop'];restored=json.loads(json.dumps(r))
        self.assertEqual(tt.view(restored,'p0')['me']['role'],g['members']['p0']['role'])
        stale={'instance':g['instance'],'revision':g['revision'],'action':'advance'}
        self.act(r,'p0','advance')
        with self.assertRaises(ValueError):tt.action(r,'p0',stale)
        self.act(r,'p0','reset')
        with self.assertRaises(ValueError):tt.action(r,'p0',stale)

if __name__=='__main__':unittest.main()
