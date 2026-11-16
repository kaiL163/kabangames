import copy
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from backend import codenames as cn


def request(game, action, **values):
    defaults = dict(instance=game['instance'], turn=game['turn_number'], action=action,
                    team='spectator', role='operative', traitor=False, seconds=0,
                    word='', number=1, card_id='')
    defaults.update(values)
    return SimpleNamespace(**defaults)


class CodenamesTests(unittest.TestCase):
    def make_room(self, traitor=False, three=False):
        tokens=['rc','r1','r2','bc','b1','b2'] if traitor else ['rc','r1','bc','b1']
        if three:tokens+=['gc','g1','g2'] if traitor else ['gc','g1']
        room={'host':'rc','host_name':'Red Captain','players':{token:{'name':token} for token in tokens if token!='rc'}}
        cn.setup(room)
        g=room['codenames']
        g['traitor']=traitor;g['team_count']=3 if three else 2
        for token in tokens:
            cn.action(room,token,request(g,'seat',team={'r':'red','b':'blue','g':'green'}[token[0]],role='captain' if token.endswith('c') else 'operative'))
            cn.action(room,token,request(g,'ready'))
        return room

    def started(self, traitor=False):
        room=self.make_room(traitor)
        cn.action(room,'rc',request(room['codenames'],'start'))
        return room

    def current(self, room):
        g=room['codenames']
        team=g['turn']
        return next(t for t,s in cn.seats(g,team) if s['role']=='captain'),next(t for t,s in cn.seats(g,team) if s['role']!='captain')

    def give_clue(self,room,number=1):
        captain,agent=self.current(room)
        cn.action(room,captain,request(room['codenames'],'clue',word='Ассоциация',number=number))
        return captain,agent

    def test_word_bank_and_deck(self):
        room=self.started();g=room['codenames']
        self.assertGreaterEqual(len(cn.WORDS),2000)
        self.assertLessEqual(len(cn.WORDS),3000)
        for theme in cn.THEMES.values():
            self.assertGreater(len(theme['words']),200)
            self.assertEqual(len(theme['words']),len(set(theme['words'])))
        self.assertEqual(len({c['word'] for c in g['cards']}),25)
        self.assertEqual(cn.remaining(g,g['turn']),9)
        self.assertEqual(cn.remaining(g,cn.other(g['turn'])),8)
        self.assertEqual(sum(c['color']=='assassin' for c in g['cards']),1)

    def test_hidden_keys_and_traitor_privacy(self):
        room=self.started(True);g=room['codenames']
        room['players']['viewer']={'name':'viewer'}
        self.assertTrue(all(c['color'] is None for c in cn.view(room,'viewer')['cards']))
        for token,seat in g['seats'].items():
            data=cn.view(room,token)
            for actual,visible in zip(g['cards'],data['cards']):
                expected=seat['role']=='captain' or seat['role']=='traitor' and actual['color'] in (cn.other(seat['team']),'assassin')
                self.assertEqual(visible['color'],actual['color'] if expected else None)
            self.assertNotIn('traitor',[p['role'] for team in data['teams'].values() for p in team])
        self.assertEqual(sum(s['role']=='traitor' for s in g['seats'].values()),2)

    def test_requires_ready_and_complete_teams(self):
        room=self.make_room();g=room['codenames']
        g['seats']['r1']['ready']=False
        with self.assertRaises(ValueError):cn.begin(room)
        g['seats']['r1']['ready']=True;g['traitor']=True
        with self.assertRaises(ValueError):cn.begin(room)

    def test_captain_slot_and_settings_reset_readiness(self):
        room=self.make_room();g=room['codenames']
        with self.assertRaises(ValueError):cn.action(room,'r1',request(g,'seat',team='red',role='captain'))
        cn.action(room,'rc',request(g,'configure',traitor=True,seconds=120))
        self.assertFalse(any(seat['ready'] for seat in g['seats'].values()))

    def test_unlimited_guesses_and_zero_clue(self):
        room=self.started();g=room['codenames'];_,agent=self.give_clue(room,0)
        turn=g['turn_number']
        own=[c for c in g['cards'] if c['color']==g['turn']][:3]
        for card in own:cn.action(room,agent,request(g,'guess',card_id=card['id']))
        self.assertEqual(g['phase'],'guess');self.assertEqual(g['turn_number'],turn)
        self.assertTrue(all(c['revealed'] for c in own))

    def test_wrong_card_passes_turn_and_stale_click_rejected(self):
        room=self.started();g=room['codenames'];_,agent=self.give_clue(room)
        old=g['turn'];card=next(c for c in g['cards'] if c['color']=='neutral')
        stale=request(g,'guess',card_id=card['id'])
        cn.action(room,agent,stale)
        self.assertEqual(g['turn'],cn.other(old))
        with self.assertRaises(ValueError):cn.action(room,agent,stale)

    def test_assassin_loses_and_finished_key_is_revealed(self):
        room=self.started();g=room['codenames'];_,agent=self.give_clue(room)
        old=g['turn'];card=next(c for c in g['cards'] if c['color']=='assassin')
        cn.action(room,agent,request(g,'guess',card_id=card['id']))
        self.assertEqual(g['winner'],cn.other(old));self.assertEqual(g['phase'],'finished')
        self.assertTrue(all(c['color'] is not None for c in cn.view(room,agent)['cards']))
        with self.assertRaises(ValueError):cn.action(room,agent,request(g,'end_turn'))

    def test_reveal_opponents_last_word_gives_them_victory(self):
        room=self.started();g=room['codenames'];_,agent=self.give_clue(room)
        opponent=cn.other(g['turn']);cards=[c for c in g['cards'] if c['color']==opponent]
        for card in cards[:-1]:card['revealed']=True
        cn.action(room,agent,request(g,'guess',card_id=cards[-1]['id']))
        self.assertEqual(g['winner'],opponent)

    def test_wrong_clue_penalty_then_new_clue(self):
        room=self.started();g=room['codenames'];captain,_=self.give_clue(room)
        old=g['turn'];cn.action(room,captain,request(g,'invalid_clue'))
        self.assertEqual(g['phase'],'penalty');self.assertEqual(g['turn'],cn.other(old))
        captain,agent=self.current(room)
        wrong=next(c for c in g['cards'] if c['color']=='neutral')
        with self.assertRaises(ValueError):cn.action(room,captain,request(g,'guess',card_id=wrong['id']))
        own=next(c for c in g['cards'] if c['color']==g['turn'])
        cn.action(room,captain,request(g,'guess',card_id=own['id']))
        self.assertTrue(own['revealed']);self.assertEqual(g['phase'],'clue')

    def test_clue_format_and_permissions(self):
        room=self.started();g=room['codenames'];captain,agent=self.current(room)
        for word in ('', 'x'*201, 'строка\nдругая'):
            with self.assertRaises(ValueError):cn.action(room,captain,request(g,'clue',word=word))
        with self.assertRaises(ValueError):cn.action(room,agent,request(g,'clue',word='Африка'))
        with self.assertRaises(ValueError):cn.action(room,captain,request(g,'guess',card_id='0'))
        cn.action(room,captain,request(g,'clue',text='Африка — 2 или без числа'))
        self.assertEqual(g['clue'],{'text':'Африка — 2 или без числа'})

    def test_timer_and_restart_instance(self):
        room=self.started();g=room['codenames'];g['clocks']={team:60 for team in cn.teams(g)};g['running_since']=time.time()-61
        old=g['turn'];cn.tick(g)
        self.assertEqual(g['turn'],cn.other(old));self.assertEqual(g['phase'],'clue')
        self.assertEqual(g['eliminated'],[]);self.assertIsNone(g['winner'])
        self.assertEqual(g['clocks'][old],60)
        stale=request(g,'ready');cn.action(room,'rc',request(g,'reset'))
        with self.assertRaises(ValueError):cn.action(room,'rc',stale)
        self.assertEqual(room['codenames']['phase'],'setup')

    def test_three_teams_deck_turns_and_elimination(self):
        room=self.make_room(three=True);g=room['codenames'];cn.begin(room)
        self.assertEqual(len(g['cards']),36)
        self.assertEqual(cn.remaining(g,g['turn']),10)
        self.assertEqual(sorted(cn.remaining(g,t) for t in cn.teams(g)),[9,9,10])
        first=g['turn']
        for _ in range(3):cn.next_turn(g)
        self.assertEqual(first,g['turn'])
        _,agent=self.give_clue(room)
        black=next(c for c in g['cards'] if c['color']=='assassin')
        cn.action(room,agent,request(g,'guess',card_id=black['id']))
        self.assertEqual(g['eliminated'],[first]);self.assertEqual(g['phase'],'clue')
        self.assertTrue(all(c['revealed'] for c in g['cards'] if c['color']==first))
        for _ in range(4):
            self.assertNotEqual(g['turn'],first);cn.next_turn(g)
        with self.assertRaises(ValueError):cn.action(room,agent,request(g,'end_turn'))
        cn.eliminate(g,'test timeout')
        self.assertEqual(g['phase'],'finished');self.assertEqual(len(g['eliminated']),2)

    def test_three_team_traitor_key(self):
        room=self.make_room(traitor=True,three=True);cn.begin(room);g=room['codenames']
        self.assertEqual(sum(s['role']=='traitor' for s in g['seats'].values()),3)
        token=next(t for t,s in g['seats'].items() if s['team']=='green' and s['role']=='traitor')
        for actual,visible in zip(g['cards'],cn.view(room,token)['cards']):
            self.assertEqual(visible['color'],actual['color'] if actual['color'] in ('red','blue','assassin') else None)

    def test_individual_turn_limits_reset_and_penalty_pause(self):
        room=self.make_room();g=room['codenames']
        cn.action(room,'rc',request(g,'configure',time_red=120,time_blue=300))
        for seat in g['seats'].values():seat['ready']=True
        with patch.object(cn.time,'time',return_value=100):cn.begin(room)
        first=g['turn'];opponent=cn.other(first);initial=g['clocks'][first]
        with patch.object(cn.time,'time',return_value=110):
            self.assertEqual(cn.clocks(g)[first],initial-10)
            self.assertEqual(cn.clocks(g)[opponent],g['time_limits'][opponent])
            cn.next_turn(g)
        self.assertEqual(g['clocks'][first],initial)
        self.assertEqual(g['clocks'][g['turn']],g['time_limits'][g['turn']])
        with patch.object(cn.time,'time',return_value=120):cn.next_turn(g,penalty=True)
        with patch.object(cn.time,'time',return_value=999):
            before=cn.clocks(g);cn.tick(g)
            self.assertEqual(cn.clocks(g),before);self.assertEqual(g['phase'],'penalty')

    def test_three_team_timeout_passes_without_eliminating(self):
        room=self.make_room(three=True);g=room['codenames'];cn.begin(room)
        lost=g['turn'];g['clocks'][lost]=0;cn.tick(g)
        self.assertEqual(g['eliminated'],[]);self.assertEqual(g['phase'],'clue')
        self.assertEqual(g['clocks'][lost],60)
        self.assertFalse(any(c['revealed'] for c in g['cards']))
        self.assertNotEqual(g['turn'],lost)

    def test_themed_decks_and_removing_third_team(self):
        for theme in cn.THEMES:
            room=self.make_room(three=True);g=room['codenames'];g['theme']=theme;cn.begin(room)
            self.assertTrue(all(c['word'] in cn.THEMES[theme]['words'] for c in g['cards']))
        room=self.make_room(three=True);g=room['codenames']
        cn.action(room,'rc',request(g,'configure',team_count=2))
        self.assertFalse(cn.seats(g,'green'))
        self.assertNotIn('green',cn.view(room,'rc')['teams'])

    def test_default_minute_restarts_every_round_and_clue_keeps_time(self):
        room=self.make_room();g=room['codenames']
        self.assertTrue(all(value==60 for value in g['time_limits'].values()))
        with patch.object(cn.time,'time',return_value=100):cn.begin(room)
        first=g['turn']
        with patch.object(cn.time,'time',return_value=120):
            self.give_clue(room)
            self.assertEqual(cn.clocks(g)[first],40)
            cn.next_turn(g)
        with patch.object(cn.time,'time',return_value=150):cn.next_turn(g)
        self.assertEqual(g['turn'],first)
        with patch.object(cn.time,'time',return_value=150):self.assertEqual(cn.clocks(g)[first],60)

    def test_old_time_banks_migrate_to_one_minute_turns(self):
        room=self.started();g=room['codenames']
        g.pop('timer_mode');g['time_limits']={team:600 for team in cn.teams(g)}
        g['clocks']={team:3 for team in cn.teams(g)}
        with patch.object(cn.time,'time',return_value=100):
            cn.tick(g)
            self.assertEqual(cn.clocks(g)[g['turn']],60)
            self.assertEqual(g['timer_mode'],'turn')

    def test_serialization_does_not_publish_secrets(self):
        import json
        room=self.started(True)
        restored=json.loads(json.dumps(room))
        agent=next(t for t,s in restored['codenames']['seats'].items() if s['role']=='operative')
        self.assertTrue(all(c['color'] is None for c in cn.view(restored,agent)['cards']))

if __name__=='__main__':unittest.main()
