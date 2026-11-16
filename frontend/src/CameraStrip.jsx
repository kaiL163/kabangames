import React, {createContext, useContext, useEffect, useRef, useState} from 'react'
import {createPortal} from 'react-dom'
export const CameraContext = createContext(null)

function useDesktop() {
 const [desktop,setDesktop]=useState(()=>window.matchMedia('(min-width: 1024px) and (pointer: fine)').matches)
 useEffect(()=>{const query=window.matchMedia('(min-width: 1024px) and (pointer: fine)');const update=()=>setDesktop(query.matches);query.addEventListener('change',update);return()=>query.removeEventListener('change',update)},[])
 return desktop
}
function CameraZoom({src,name,onClose}) {
 const dialog=useRef(null)
 useEffect(()=>{dialog.current.showModal();return()=>dialog.current?.close()},[])
 return createPortal(<dialog ref={dialog} className="camera-zoom" onCancel={onClose} onClick={event=>{if(event.target===event.currentTarget)onClose()}}><div className="camera-zoom-header"><strong>{name}</strong><button autoFocus onClick={onClose} aria-label="Закрыть увеличенную камеру">Закрыть ×</button></div><iframe title={`Увеличенная камера: ${name}`} src={src} allow="autoplay; fullscreen" referrerPolicy="no-referrer"/></dialog>,document.body)
}
export function CameraTile({stream, name}) {
 const {video, myCamera} = useContext(CameraContext)
 const [zoom,setZoom]=useState(false)
 const desktop=useDesktop()
 if (!video || !stream) return <div className="player-camera-placeholder">☺</div>
 if (stream === myCamera) return <div className="player-camera-placeholder">Ты</div>
 const params = new URLSearchParams({room:video.room,password:video.password,scene:'',view:stream,noaudio:'',cleanoutput:''})
 const src=`https://vdo.ninja/#${params}`
 function popout(){window.open(src,'_blank','popup=yes,width=960,height=600,resizable=yes,scrollbars=yes,noopener,noreferrer')}
 return <div className="player-camera"><iframe title={`Камера: ${name}`} src={src} allow="autoplay; fullscreen" referrerPolicy="no-referrer"/><div className="camera-tile-actions"><button type="button" onClick={()=>setZoom(true)} aria-label={`Увеличить камеру: ${name}`} title="Увеличить">⛶</button>{desktop&&<button type="button" onClick={popout} aria-label={`Камера ${name} в отдельном окне`} title="В отдельное окно">↗</button>}</div>{zoom&&<CameraZoom src={src} name={name} onClose={()=>setZoom(false)}/>}</div>
}
export function CameraPlayers() {
 const {hostCamera,hostName,players,video} = useContext(CameraContext)
 const [open,setOpen] = useState(()=>sessionStorage.getItem('kaban-cameras-open')==='true')
 if (!video) return null
 function toggle(){const next=!open;setOpen(next);sessionStorage.setItem('kaban-cameras-open',String(next))}
 return <section className="game-camera-section" aria-label="Камеры игроков"><button className="game-camera-toggle" onClick={toggle} aria-expanded={open} aria-controls="game-camera-list"><span>Камеры игроков · {players.length+1}</span><span>{open?'Свернуть ↑':'Показать ↓'}</span></button><div id="game-camera-list" className={`game-cameras ${open?'':'cameras-hidden'}`} inert={open?undefined:''}>{[{camera_id:hostCamera,name:hostName},...players].map(player=><div className="game-camera-item" key={player.camera_id}><CameraTile stream={player.camera_id} name={player.name}/><span>{player.name}</span></div>)}</div></section>
}
export default function CameraStrip() {
 const {video,enabled,setEnabled,myCamera} = useContext(CameraContext)
 const [confirming,setConfirming] = useState(false)
 const [expanded,setExpanded] = useState(false)
 if (!video || !myCamera) return null
 const params = new URLSearchParams({room:video.room,password:video.password,push:myCamera,view:'',label:video.name,audiodevice:'0',webcam:'',autostart:''})
 return <aside className={`camera-publisher camera-tools ${enabled&&expanded?'preview-open':''} ${confirming&&!enabled?'confirm-open':''}`} aria-label="Моя камера">
  <div className="camera-publisher-bar"><span className={`my-camera-icon ${enabled?'is-on':''}`} aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="6" width="12" height="12" rx="3"/><path d="m15 10 5-3v10l-5-3"/></svg></span><strong>{enabled?'Камера включена':'Камера'}</strong>{enabled?<><button onClick={()=>setExpanded(!expanded)}>{expanded?'Скрыть превью':'Превью'}</button><button onClick={()=>setEnabled(false)}>Выключить</button></>:<button onClick={()=>setConfirming(true)}>Включить</button>}</div>
  {confirming&&!enabled&&<div className="camera-publisher-confirm"><p>Разреши доступ к камере, чтобы друзья увидели тебя. Микрофон отключён.</p><button onClick={()=>{setEnabled(true);setExpanded(window.matchMedia('(min-width: 701px)').matches);setConfirming(false)}}>Продолжить</button><button onClick={()=>setConfirming(false)}>Отмена</button></div>}
  {enabled&&<div className={expanded?'camera-publisher-frame':'camera-publisher-frame collapsed'}><iframe title="Настройка моей камеры" src={`https://vdo.ninja/#${params}`} allow="camera; autoplay" referrerPolicy="no-referrer"/></div>}
 </aside>
}
