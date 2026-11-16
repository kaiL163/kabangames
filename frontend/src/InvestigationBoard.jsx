import React, {useEffect,useRef,useState} from 'react'
import {CaseDialog,CaseEmpty,EvidenceImage} from './DetectiveUI.jsx'

const RELATIONS=['Подтверждает','Противоречит','Общее время','Связаны с человеком','Нужно проверить']
const EMPTY={cards:{},links:[],timeline:[]}

export default function InvestigationBoard({caseData,onAction,mode,onOpenItem,onGoMaterials,initialEvent,onConsumeEvent}) {
 const board=caseData.board||EMPTY
 const items=caseData.items.filter(item=>item.text)
 const byId=Object.fromEntries(items.map(item=>[item.id,item]))
 const ids=Object.keys(board.cards).filter(id=>byId[id])
 const [selected,setSelected]=useState('')
 const [picker,setPicker]=useState(false)
 const [query,setQuery]=useState('')
 const [view,setView]=useState('map')
 const [linkFrom,setLinkFrom]=useState('')
 const [linkTo,setLinkTo]=useState('')
 const [relation,setRelation]=useState(RELATIONS[0])
 const [eventEditor,setEventEditor]=useState(initialEvent?{id:'',time:'',text:'',item_id:initialEvent}:null)
 const [busy,setBusy]=useState(false)
 const [message,setMessage]=useState('')
 const [draft,setDraft]=useState(null)
 const drag=useRef(null),actionPending=useRef(false),inspector=useRef(null)
 useEffect(()=>{if(selected&&window.matchMedia('(max-width: 800px)').matches&&!linkFrom)inspector.current?.scrollIntoView({behavior:'smooth',block:'start'})},[selected,linkFrom])
 const readOnly=Boolean(caseData.result)
 async function act(body){if(actionPending.current)return false;actionPending.current=true;setBusy(true);try{const ok=await onAction({instance:caseData.instance,...body});if(ok)setMessage('Сохранено для команды');return Boolean(ok)}finally{actionPending.current=false;setBusy(false)}}
 function choose(id){if(linkFrom&&id!==linkFrom){setLinkTo(id);return}setSelected(id)}
 async function pin(item){const count=ids.length;const ok=await act({action:'pin',item_id:item.id,x:30+(count%4)*235,y:25+Math.floor(count/4)*100%460});if(ok){setSelected(item.id);setPicker(false)}}
 function position(id){return draft?.id===id?draft:board.cards[id]}
 function startDrag(e,id){if(readOnly||busy||linkFrom)return;e.currentTarget.setPointerCapture(e.pointerId);drag.current={id,x:e.clientX,y:e.clientY,start:position(id),width:e.currentTarget.closest('.ib-map').getBoundingClientRect().width};setSelected(id)}
 function moveDrag(e){const d=drag.current;if(!d)return;const scale=1000/d.width;setDraft({id:d.id,x:Math.round(Math.max(0,Math.min(800,d.start.x+(e.clientX-d.x)*scale))),y:Math.round(Math.max(0,Math.min(500,d.start.y+(e.clientY-d.y)*scale)))})}
 async function endDrag(){const d=drag.current;drag.current=null;if(draft&&d)await act({action:'move',item_id:d.id,x:draft.x,y:draft.y});setDraft(null)}
 async function arrange(){if(!window.confirm('Разложить карточки по сетке для всей команды?'))return;for(let i=0;i<ids.length;i++){if(!await act({action:'move',item_id:ids[i],x:20+(i%4)*245,y:Math.round(10+Math.floor(i/4)*Math.min(160,480/Math.max(1,Math.ceil(ids.length/4)-1)))}))break}}
 async function remove(id){const connected=board.links.filter(link=>link.source===id||link.target===id);if(connected.length&&!window.confirm('Снять материал и его связи? Сам материал останется в деле.'))return;if(await act({action:'remove',item_id:id}))setSelected('')}
 const selectedItem=byId[selected]
 const selectedLinks=board.links.filter(link=>link.source===selected||link.target===selected)
 const editor=eventEditor
 const editable=!readOnly&&!busy
 return <section className="ib-workspace">
 <div className="ib-toolbar"><div><h2>{mode==='Доска'?'Доска расследования':'Хронология'}</h2><p>{mode==='Доска'?`${ids.length} материалов · ${board.links.length} связей`:'События и рабочие версии команды'}</p></div><button className="dc-primary" disabled={!editable} onClick={()=>mode==='Доска'?setPicker(true):setEventEditor({id:'',time:'',text:'',item_id:''})}>＋ {mode==='Доска'?'Материал':'Событие'}</button></div>
 {readOnly&&<p className="dc-notice">Дело закрыто. Всё расследование сохранено для просмотра.</p>}
 <span className="dc-save-status" role="status">{busy?'Сохраняем…':message||'Общее пространство · изменения видны команде'}</span>
 {mode==='Доска'?<>
 {ids.length>0?<>
 <div className="ib-view-controls"><div className="dc-segment"><button className={view==='map'?'active':''} onClick={()=>setView('map')}>Схема</button><button className={view==='list'?'active':''} onClick={()=>setView('list')}>Карточки</button></div><button className="dc-text-button ib-arrange" disabled={!editable} onClick={arrange}>Выровнять</button></div>
 {linkFrom&&<div className="dc-notice">Связываем: <strong>{byId[linkFrom]?.title}</strong>. Выбери второй материал.<button onClick={()=>{setLinkFrom('');setLinkTo('')}}>Отмена</button></div>}
 <div className="ib-layout"><div className="ib-main">
 <div className={`ib-map-wrap ${view==='list'?'ib-map-off':''}`}><div className="ib-map"><svg viewBox="0 0 1000 680" aria-hidden="true">{board.links.map(link=>{const a=position(link.source),b=position(link.target);if(!a||!b)return null;const highlighted=selected===link.source||selected===link.target;return <g key={link.id} className={highlighted?'highlighted':''}><path d={`M ${a.x+95} ${a.y+65} Q ${(a.x+b.x)/2+120} ${(a.y+b.y)/2+20} ${b.x+95} ${b.y+65}`}/></g>})}</svg>{ids.map(id=>{const item=byId[id],pos=position(id);return <div key={id} className={`ib-node ${id===selected||id===linkFrom?'selected':''}`} style={{left:`${pos.x/10}%`,top:`${pos.y/6.8}%`}}><div className="ib-node-handle" onPointerDown={e=>startDrag(e,id)} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={()=>{drag.current=null;setDraft(null)}}>⠿ {item.group}</div><button onClick={()=>choose(id)}><EvidenceImage item={item}/><strong>{item.title}</strong></button></div>})}</div></div>
 <div className={`ib-card-list ${view==='list'?'ib-list-forced':''}`}>{ids.map(id=><button key={id} className={`ib-list-card ${selected===id?'selected':''}`} onClick={()=>choose(id)}><EvidenceImage item={byId[id]}/><span><small>{byId[id].group}</small><strong>{byId[id].title}</strong><small>{board.links.filter(link=>link.source===id||link.target===id).length} связей</small></span><b>↗</b></button>)}</div>
 </div><aside className="ib-inspector" ref={inspector}>{selectedItem?<><span className="dc-kicker">В ФОКУСЕ</span><h3>{selectedItem.title}</h3><p>{selectedItem.text}</p><div className="ib-inspector-actions"><button className="dc-secondary" onClick={()=>onOpenItem(selectedItem)}>Открыть материал</button><button className="dc-primary" disabled={!editable||ids.length<2} onClick={()=>{setLinkFrom(selected);setLinkTo('')}}>Связать с…</button></div><h4>Связи · {selectedLinks.length}</h4>{selectedLinks.map(link=>{const other=link.source===selected?link.target:link.source;return <div className="ib-relation" key={link.id}><small>{link.label}</small><button onClick={()=>setSelected(other)}>{byId[other]?.title} ↗</button><button className="dc-text-button" disabled={!editable} onClick={()=>act({action:'unlink',entry_id:link.id})}>Удалить связь</button></div>})}{!selectedLinks.length&&<p className="dc-muted">Пока без связей. С чем стоит сопоставить этот материал?</p>}<button className="dc-text-button danger" disabled={!editable} onClick={()=>remove(selected)}>Снять с доски</button></>:<CaseEmpty icon="↖" title="Выбери материал">Здесь появятся его содержание, связи и действия.</CaseEmpty>}</aside></div>
 </>:<CaseEmpty icon="⌁" title="С чего начинается версия?" action={<button className="dc-primary" disabled={!editable} onClick={()=>items.length?setPicker(true):onGoMaterials()}>{items.length?'Закрепить первый материал':'Осмотреть место преступления'}</button>}>Добавь изученные материалы. Выбери карточку, нажми «Связать с…» и укажи вторую. Команда увидит вашу цепочку рассуждений.</CaseEmpty>}
 {board.links.length>0&&<details className="ib-all-links"><summary>Все связи команды · {board.links.length}</summary>{board.links.map(link=><button key={link.id} onClick={()=>setSelected(link.source)}>{byId[link.source]?.title} <em>{link.label}</em> {byId[link.target]?.title} ↗</button>)}</details>}
 </>:<>
 <div className="dc-notice">Хронология — ваша реконструкция. Источник подтверждает материал, но не гарантирует правильность вывода.</div>
 {board.timeline.length?<ol className="ib-timeline">{[...board.timeline].sort((a,b)=>(a.time||'99:99').localeCompare(b.time||'99:99')).map(entry=><li key={entry.id}><div className="ib-time"><time>{entry.time||'— : —'}</time><small>{entry.time?'Время события':'Не установлено'}</small></div><article><p>{entry.text}</p>{entry.item_id&&byId[entry.item_id]?<button className="ib-source" onClick={()=>onOpenItem(byId[entry.item_id])}>↗ {byId[entry.item_id].title}</button>:<span className="ib-hypothesis">Гипотеза · без источника</span>}<div className="ib-event-footer"><small>Добавил(а): {entry.author}</small>{editable&&<><button onClick={()=>setEventEditor({...entry})}>Изменить</button><button className="danger" onClick={()=>{if(window.confirm('Удалить событие из общей хронологии?'))act({action:'delete_event',entry_id:entry.id})}}>Удалить</button></>}</div></article></li>)}</ol>:<CaseEmpty icon="◷" title="Соберём вечер по минутам" action={<button className="dc-primary" disabled={!editable} onClick={()=>setEventEditor({id:'',time:'',text:'',item_id:''})}>Первое событие</button>}>Начни с записи камеры, переписки или показаний. Если точного времени нет, оставь его неизвестным.</CaseEmpty>}
 </>}
 {picker&&<CaseDialog title="Закрепить материал" onClose={()=>setPicker(false)}><label className="dc-field">Найти среди изученного<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Название материала…" autoFocus/></label><div className="ib-picker">{items.filter(item=>!board.cards[item.id]&&item.title.toLowerCase().includes(query.toLowerCase())).map(item=><button key={item.id} disabled={!editable} onClick={()=>pin(item)}><EvidenceImage item={item}/><span><small>{item.group}</small><strong>{item.title}</strong></span><b>＋</b></button>)}</div>{items.every(item=>board.cards[item.id])&&<p>Все изученные материалы уже на доске.</p>}<button className="dc-text-button" onClick={()=>{setPicker(false);onGoMaterials()}}>Перейти к материалам дела ↗</button></CaseDialog>}
 {linkFrom&&linkTo&&<CaseDialog title="Что связывает материалы?" onClose={()=>setLinkTo('')}><div className="ib-link-preview"><span>{byId[linkFrom]?.title}</span><b>↔</b><span>{byId[linkTo]?.title}</span></div><div className="ib-relation-presets">{RELATIONS.map(value=><button key={value} className={relation===value?'active':''} onClick={()=>setRelation(value)}>{value}</button>)}</div><form onSubmit={async e=>{e.preventDefault();if(await act({action:'link',item_id:linkFrom,target:linkTo,label:relation})){setLinkFrom('');setLinkTo('')}}}><label className="dc-field">Подпись связи<input maxLength={120} required value={relation} onChange={e=>setRelation(e.target.value)}/></label><button className="dc-primary" disabled={!editable||!relation.trim()}>Сохранить связь</button></form></CaseDialog>}
 {editor&&<CaseDialog title={editor.id?'Изменить событие':'Новое событие'} onClose={()=>{setEventEditor(null);onConsumeEvent?.()}}><form onSubmit={async e=>{e.preventDefault();if(await act({action:editor.id?'update_event':'event',entry_id:editor.id,time:editor.time,text:editor.text,item_id:editor.item_id})){setEventEditor(null);onConsumeEvent?.()}}}><label className="dc-field">Время <small>Неизвестно? Оставь пустым.</small><input type="time" value={editor.time} onChange={e=>setEventEditor({...editor,time:e.target.value})}/></label><label className="dc-field">Что произошло?<textarea required maxLength={300} value={editor.text} onChange={e=>setEventEditor({...editor,text:e.target.value})} placeholder="Кто, где и что сделал?"/></label><label className="dc-field">Источник<select value={editor.item_id} onChange={e=>setEventEditor({...editor,item_id:e.target.value})}><option value="">Гипотеза без источника</option>{items.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label><button className="dc-primary" disabled={!editable||!editor.text.trim()}>Сохранить для команды</button></form></CaseDialog>}
 </section>
}
