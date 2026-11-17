import time
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import quiz,party,writing_game,spy_game

def room(count=4):return {'host':'host','host_name':'Host','players':{f'p{i}':{'name':f'Player {i}'} for i in range(count-1)}}

class PartyUpgradeTests(unittest.TestCase):
 def test_banks_have_100_unique_prompts_and_adult_removed(self):
  self.assertNotIn('adultquiz',quiz.BANK)
  for mode in ('quiz','emoji','truefalse','words','cinema','filmguess'):
   items=quiz.BANK[mode]['items'];self.assertGreaterEqual(len(items),100,mode)
   self.assertEqual(len(items),len({item[0] for item in items}),mode)
  self.assertGreaterEqual(len(writing_game.PROMPTS),100);self.assertGreaterEqual(len(party.WHO),100)
 def test_every_logo_asset_exists(self):
  root=Path(__file__).resolve().parents[1]/'frontend'/'public'/'car-logos'
  self.assertGreaterEqual(len(quiz.CAR_BRANDS),100)
  for name,asset in quiz.CAR_BRANDS.items():self.assertTrue((root/asset).is_file(),name)
 def test_wordmarks_never_selected_and_safe_regions_valid(self):
  for brand in ('Jaecoo','Jeep','Ford','Kia','GMC','BYD','Haval'):
   self.assertNotIn(brand,quiz.CAR_PUZZLES)
  self.assertGreaterEqual(len(quiz.CAR_PUZZLES),100)
  for brand,data in quiz.CAR_PUZZLES.items():
   self.assertIn(brand,quiz.CAR_BRANDS)
   self.assertTrue(all(value>0 for value in data['size']))
   for x,y,w,h in [data['crop'],*data['cover']]:
    self.assertTrue(0<=x<100 and 0<=y<100 and w>0 and h>0 and x+w<=100 and y+h<=100,brand)
  r=room();quiz.start(r,'carquiz',100)
  self.assertTrue(all(item[1] in quiz.CAR_PUZZLES for item in r['quiz']['questions']))
  self.assertIsNotNone(quiz.view(r,'host')['emblem'])
 def test_old_wordmark_round_is_retired_on_restore(self):
  r=room();quiz.start(r,'carquiz',5);q=r['quiz'];q['correct']='Jaecoo'
  q['questions'].append(['Legacy text logo','Jeep'])
  self.assertEqual(quiz.view(r,'host')['phase'],'result')
  quiz.next_round(r)
  self.assertTrue(all(item[1] in quiz.CAR_PUZZLES for item in q['questions'][q['index']:]))
 def test_expanded_emblems_have_local_sources_and_no_duplicate_options(self):
  import json
  root=Path(__file__).resolve().parents[1]/'frontend'/'public'/'car-logos'
  self.assertGreaterEqual(len(quiz.CAR_PUZZLES),200)
  sources=json.loads((root/'sources.json').read_text(encoding='utf-8'))
  for item in sources:
   self.assertTrue((root/item['asset']).is_file())
   self.assertTrue(item['url'].startswith('https://'))
  for name,config in quiz.CAR_PUZZLES.items():
   self.assertTrue((root/config.get('asset',quiz.CAR_BRANDS[name])).is_file())
  r=room();quiz.start(r,'carquiz',100)
  self.assertEqual(len({row[1] for row in r['quiz']['questions']}),100)
 def test_clean_symbol_is_used_before_reveal_and_original_after(self):
  r=room();quiz.start(r,'carquiz',5);g=r['quiz']
  g.update(correct='Acura',image='/car-logos/'+quiz.CAR_BRANDS['Acura'],options=['Acura','Honda','Toyota','Audi'])
  before=quiz.view(r,'host')
  self.assertEqual(before['image'],'/car-logos/'+quiz.CAR_PUZZLES['Acura']['asset'])
  self.assertEqual(before['emblem']['crop'],[0,0,100,100]);self.assertEqual(before['emblem']['cover'],[])
  quiz.finish_if_needed(r,True)
  after=quiz.view(r,'host');self.assertEqual(after['image'],'/car-logos/'+quiz.CAR_BRANDS['Acura'])
  self.assertEqual(after['correct'],'Acura');self.assertIsNone(after['emblem'])
 def test_speed_scores_are_server_timed_and_awarded_once(self):
  r=room(3)
  with patch.object(quiz.time,'time',return_value=100):quiz.start(r,'quiz')
  q=r['quiz'];correct=q['options'].index(q['correct'])
  with patch.object(quiz.time,'time',return_value=100):quiz.answer(r,'host',correct)
  with patch.object(quiz.time,'time',return_value=115):quiz.answer(r,'p0',correct)
  with patch.object(quiz.time,'time',return_value=129):quiz.answer(r,'p1',correct)
  self.assertEqual(q['scores']['host']['score'],300);self.assertEqual(q['scores']['p0']['score'],200)
  self.assertGreater(q['scores']['p1']['score'],100)
  before=q['scores']['host']['score'];quiz.finish_if_needed(r,True);self.assertEqual(before,q['scores']['host']['score'])
 def test_wrong_answer_and_late_answer_do_not_award_speed_points(self):
  r=room(2);quiz.start(r,'quiz');q=r['quiz'];wrong=next(i for i,a in enumerate(q['options']) if a!=q['correct'])
  quiz.answer(r,'host',wrong);q['deadline']=0
  with self.assertRaises(ValueError):quiz.answer(r,'p0',0)
  self.assertEqual(q['scores']['host']['score'],0)
 def test_car_masks_shared_stable_and_do_not_repeat(self):
  r=room();quiz.start(r,'carquiz',100,'hard')
  self.assertEqual(len(r['quiz']['questions']),100)
  for _ in range(12):
   a=quiz.view(r,'host');b=quiz.view(r,'p0')
   self.assertEqual(a['mask'],b['mask']);self.assertEqual(a['difficulty'],'hard');self.assertNotIn('correct',a)
   self.assertEqual(len(set(a['options'])),4)
   old=a['mask'];quiz.finish_if_needed(r,True);quiz.next_round(r)
   self.assertNotEqual(old,quiz.view(r,'host')['mask'])
 def test_car_options_similar_shapes(self):
  choices=quiz.car_options('Aston Martin',set())
  self.assertEqual(len(choices),3)
  self.assertTrue(set(choices)<=set(quiz.LOGO_FAMILIES[0]));self.assertNotIn('Aston Martin',choices)
 def test_emoji_choices_vary_between_rounds(self):
  r=room();quiz.start(r,'emoji',50);last=set(r['quiz']['options'])
  for _ in range(15):
   quiz.finish_if_needed(r,True);quiz.next_round(r);current=set(r['quiz']['options'])
   self.assertEqual(len(current),4);self.assertLessEqual(len(last&current),1);last=current
 def test_long_writing_game_uses_distinct_prompts(self):
  r=room();writing_game.start(r,100);self.assertEqual(len(r['writing']['prompts']),100)
  self.assertEqual(len(set(r['writing']['prompts'])),100)
 def test_cannot_vote_for_yourself_in_who(self):
  r=room();party.start(r,'who',50);g=r['party'];own=next(c for c in g['choices'] if c['owner']=='host')
  with self.assertRaises(ValueError):party.action(r,'host','vote',own['id'])
  self.assertEqual(g['total_rounds'],50)
 def test_facts_get_two_minutes(self):
  r=room()
  with patch.object(party.time,'time',return_value=100):party.start(r,'twotruths')
  self.assertEqual(r['party']['deadline'],220)
 def test_screenwriter_custom_text_anonymous_and_scored(self):
  r=room(3);party.start(r,'screenwriter',25);g=r['party']
  self.assertEqual(g['phase'],'write');self.assertEqual(g['total_rounds'],25)
  party.action(r,'host','write','Кот стал детективом')
  self.assertNotIn('choices',party.view(r,'p0'))
  party.action(r,'p0','write','Робот забыл пароль');party.action(r,'p1','write','Повар нашёл портал')
  v=party.view(r,'host');self.assertEqual(v['phase'],'vote')
  self.assertTrue(all('owner' not in c for c in v['choices']))
  own=next(c for c in g['choices'] if c['owner']=='host')
  with self.assertRaises(ValueError):party.action(r,'host','vote',own['id'])
  for token in g['eligible']:
   choice=next(c for c in g['choices'] if c['owner']!=token);party.action(r,token,'vote',choice['id'])
  self.assertEqual(g['phase'],'result');self.assertEqual(len(g['story']),1)
  self.assertEqual(sum(p['score'] for p in g['scores'].values()),300)
 def test_screenwriter_timeout_preserves_single_answer(self):
  r=room(3);party.start(r,'screenwriter');party.action(r,'host','write','Одинокое начало')
  r['party']['deadline']=0;party.update(r)
  self.assertEqual(r['party']['phase'],'result');self.assertEqual(r['party']['story'][0]['answer'],'Одинокое начало')
 def test_spy_custom_question_chat_and_voice_answer(self):
  r=room();spy_game.start(r,5);g=r['party'];asker,target=spy_game.pair(g)
  spy_game.action(r,asker,'ask','Сколько здесь обычно окон?')
  self.assertEqual(g['phase'],'answer');self.assertEqual(g['question'],'Сколько здесь обычно окон?')
  spy_game.action(r,target,'voice_answer','');self.assertEqual(g['phase'],'ask')
  spy_game.action(r,asker,'chat','Обсудим ответ')
  self.assertEqual(spy_game.view(r,target)['chat'][0]['text'],'Обсудим ответ')
  self.assertNotIn('location',spy_game.view(r,g['spy']))
  with self.assertRaises(ValueError):spy_game.action(r,target,'voice_answer','')
 def test_spy_discussion_can_finish_when_everyone_ready(self):
  r=room();spy_game.start(r);g=r['party'];g['phase']='discuss';g['deadline']=time.time()+120
  for token in g['eligible']:spy_game.action(r,token,'ready_vote','')
  self.assertEqual(g['phase'],'vote')

if __name__=='__main__':unittest.main()
