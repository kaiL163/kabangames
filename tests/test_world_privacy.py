import json
import unittest
from backend import tabletop as tt

class WorldPrivacyTests(unittest.TestCase):
 def action(self,r,token,action,**kw):
  g=r['tabletop'];tt.action(r,token,{'instance':g['instance'],'revision':g['revision'],'action':action,**kw})
 def setup(self,voice=False):
  r={'host':'gm','host_name':'Ведущий','players':{f'p{i}':{'name':f'Игрок {i}'} for i in range(3)}}
  tt.setup(r,'domination')
  if voice:self.action(r,'gm','configure',seconds=900,comm_mode='voice',talk_seconds=180)
  self.action(r,'gm','ready')
  for i in range(3):self.action(r,f'p{i}','seat',team=str(i));self.action(r,f'p{i}','ready')
  self.action(r,'gm','start');return r
 def talk(self,r):self.action(r,'gm','advance')
 def negotiate(self,r):
  self.talk(r);self.action(r,'p0','negotiate',target='1');n=tt.view(r,'p1')['negotiations'][0]['id'];self.action(r,'p1','accept',negotiation=n);return n
 def test_country_statistics_stay_private_in_every_phase(self):
  r=self.setup();g=r['tabletop'];tt.team(g,'1').update(money=987654,nukes=17,eco=71)
  for phase in ('dev','talk','review','finished'):
   g['phase']=phase;g['deadline']=None
   for i in range(3):
    data=tt.view(r,f'p{i}');self.assertEqual([t['id'] for t in data['countries']],[str(i)])
    self.assertTrue(all(set(t)=={'id','name'} for t in data['directory']))
    if i!=1:self.assertNotIn('987654',json.dumps(data))
   self.assertEqual(tt.view(r,'observer')['countries'],[])
 def test_gm_receives_statistics_only_in_third_phase(self):
  r=self.setup();g=r['tabletop']
  for phase in ('dev','talk','finished'):
   g['phase']=phase;g['deadline']=None;self.assertEqual(tt.view(r,'gm')['countries'],[])
  g['phase']='review';v=tt.view(r,'gm');self.assertTrue(v['can_report']);self.assertEqual(len(v['countries']),3)
 def test_host_cannot_play_a_country(self):
  r={'host':'gm','host_name':'GM','players':{}};tt.setup(r,'domination')
  self.assertEqual(r['tabletop']['members']['gm']['team'],'gm')
  with self.assertRaises(ValueError):self.action(r,'gm','seat',team='0')
 def test_active_country_cannot_be_promoted_to_gm(self):
  r=self.setup()
  with self.assertRaises(ValueError):tt.transfer_host(r,'p0')
  self.assertEqual(r['tabletop']['members']['p0']['team'],'0')
  self.assertEqual(r['tabletop']['members']['gm']['team'],'gm')
 def test_spectator_can_replace_gm_without_revealing_private_history(self):
  r=self.setup();r['players']['newgm']={'name':'Новый ведущий'}
  self.action(r,'p0','chat',text='Секрет страны');tt.transfer_host(r,'newgm')
  r['players']['gm']={'name':'Прежний ведущий'};r['players'].pop('newgm');r['host']='newgm';r['host_name']='Новый ведущий'
  self.assertNotIn('gm',r['tabletop']['members'])
  self.assertTrue(tt.view(r,'newgm')['is_gm']);self.assertEqual(tt.view(r,'newgm')['countries'],[])
  self.action(r,'newgm','advance');self.action(r,'newgm','advance')
  self.assertEqual(len(tt.view(r,'newgm')['countries']),3)
  self.assertEqual(tt.view(r,'newgm')['messages'],[])
  self.assertEqual(tt.view(r,'gm')['countries'],[])
 def test_invitation_and_messages_are_private_to_two_countries(self):
  r=self.setup();self.talk(r);self.action(r,'p0','negotiate',target='1')
  n=tt.view(r,'p1')['negotiations'][0]
  self.assertNotIn('room',n);self.assertNotIn('password',n)
  self.assertEqual(tt.view(r,'p2')['negotiations'],[]);self.assertEqual(tt.view(r,'gm')['negotiations'],[])
  with self.assertRaises(ValueError):self.action(r,'p0','chat',target='1',text='premature')
  with self.assertRaises(ValueError):self.action(r,'p2','accept',negotiation=n['id'])
  self.action(r,'p1','accept',negotiation=n['id']);self.action(r,'p0','chat',target='1',text='Секретный договор')
  self.assertEqual(tt.view(r,'p1')['messages'][0]['text'],'Секретный договор')
  for token in ('p2','gm','observer'):self.assertEqual(tt.view(r,token)['messages'],[])
  r['tabletop']['phase']='finished';self.assertEqual(tt.view(r,'p2')['messages'],[])
 def test_closed_negotiation_blocks_messages(self):
  r=self.setup();n=self.negotiate(r);self.action(r,'p1','close',negotiation=n)
  with self.assertRaises(ValueError):self.action(r,'p0','chat',target='1',text='after close')
 def test_no_global_country_chat(self):
  r=self.setup();self.action(r,'p0','chat',team='all',text='Only our country')
  for token in ('p1','p2','gm'):self.assertEqual(tt.view(r,token)['messages'],[])
 def test_actions_are_not_published_in_other_countries_logs(self):
  r=self.setup();self.action(r,'p0','research')
  self.assertIn('разработка',tt.view(r,'p0')['log'][-1]['text'])
  for token in ('p1','p2','gm'):self.assertNotIn('разработка',json.dumps(tt.view(r,token)['log'],ensure_ascii=False))
 def test_voice_channels_only_exist_in_voice_mode(self):
  r=self.setup();self.assertEqual(tt.view(r,'p0')['voice_channels'],[])
  r=self.setup(True);self.assertEqual(len(tt.view(r,'p0')['voice_channels']),1)
  self.assertNotEqual(tt.view(r,'p0')['voice_channels'][0]['password'],tt.view(r,'p1')['voice_channels'][0]['password'])
 def test_private_voice_credentials_only_reach_accepted_participants(self):
  r=self.setup(True);n=self.negotiate(r)
  channel=next(c for c in tt.view(r,'p0')['voice_channels'] if c['id']==n)
  peer=next(c for c in tt.view(r,'p1')['voice_channels'] if c['id']==n)
  self.assertEqual(channel['room'],peer['room']);self.assertEqual(channel['password'],peer['password'])
  for token in ('p2','gm','observer'):self.assertNotIn(channel['password'],json.dumps(tt.view(r,token)))
  self.action(r,'gm','advance')
  self.assertNotIn(channel['password'],json.dumps(tt.view(r,'p0')))
  self.assertTrue(next(c for c in tt.view(r,'p0')['voice_channels'] if c['id'].startswith('report:'))['listen_only'])
  self.assertFalse(tt.view(r,'gm')['voice_channels'][0]['listen_only'])
 def test_research_in_later_round_still_requires_waiting(self):
  r=self.setup();g=r['tabletop'];g['round']=2;country=tt.team(g,'0');country['money']=2000
  self.action(r,'p0','research');self.assertEqual(country['research_round'],2)
  with self.assertRaises(ValueError):self.action(r,'p0','build')
  g['round']=3;self.action(r,'p0','build');self.assertEqual(country['nukes'],1)
 def test_final_review_precedes_finish_without_disclosing_stats(self):
  r=self.setup();g=r['tabletop'];g['round']=5;self.talk(r);self.action(r,'gm','advance')
  self.assertEqual(g['phase'],'review');self.assertEqual(len(tt.view(r,'gm')['countries']),3)
  self.action(r,'gm','advance');self.assertEqual(g['phase'],'finished')
  self.assertEqual(len(tt.view(r,'p0')['countries']),1)
 def test_reward_is_unavailable_outside_report(self):
  r=self.setup()
  with self.assertRaises(ValueError):self.action(r,'gm','reward',target='1',amount=-100)
  self.talk(r);self.action(r,'gm','advance');self.action(r,'gm','reward',target='1',amount=100)
  self.assertNotIn('баланс',json.dumps(tt.view(r,'p2')['log'],ensure_ascii=False))
 def test_legacy_public_economy_logs_are_removed(self):
  r=self.setup();g=r['tabletop'];g.pop('privacy_version');g['log'].append({'id':'old','scope':'all','text':'Чужая казна 123456'})
  self.assertNotIn('123456',json.dumps(tt.view(r,'p0')))
 def test_manual_report_only_visible_in_current_review(self):
  r=self.setup();self.talk(r);self.action(r,'gm','advance');self.action(r,'gm','announce',text='Ведущий оглашает сводку')
  self.assertEqual(len(tt.view(r,'p0')['announcements']),1)
  self.action(r,'gm','advance');self.assertEqual(tt.view(r,'p0')['announcements'],[])
 def test_hidden_city_state_is_not_an_attack_error_oracle(self):
  r=self.setup();g=r['tabletop'];attacker=tt.team(g,'0');target=tt.team(g,'1');attacker['nukes']=2
  target['cities'][0]['destroyed']=True
  self.action(r,'p0','attack',target='1',city='0');self.assertEqual(attacker['nukes'],1)
  self.assertNotIn('shield',json.dumps(tt.view(r,'p0')['directory']))

if __name__=='__main__':unittest.main()
