import React, {createContext, useContext, useState} from 'react'
export const CameraContext = createContext(null)

export function CameraTile({stream, name}) {
 const {video, myCamera} = useContext(CameraContext)
 if (!video || !stream) return <div className="player-camera-placeholder">☺</div>
 if (stream === myCamera) return <div className="player-camera-placeholder">Ты</div>
 const params = new URLSearchParams({room:video.room,password:video.password,scene:'',view:stream,noaudio:'',cleanoutput:''})
 return <div className="player-camera"><iframe title={`Камера: ${name}`} src={`https://vdo.ninja/#${params}`} allow="autoplay; fullscreen" referrerPolicy="no-referrer" /></div>
}
export function CameraPlayers() {
 const {hostCamera,hostName,players,video} = useContext(CameraContext)
 if (!video) return null
 return <aside className="game-cameras" aria-label="Камеры игроков">{[{camera_id:hostCamera,name:hostName},...players].map(player=><div className="game-camera-item" key={player.camera_id}><CameraTile stream={player.camera_id} name={player.name}/><span>{player.name}</span></div>)}</aside>
}
export default function CameraStrip() {
 const {video,enabled,setEnabled,myCamera} = useContext(CameraContext)
 const [confirming,setConfirming] = useState(false)
 const [expanded,setExpanded] = useState(true)
 if (!video || !myCamera) return null
 const params = new URLSearchParams({room:video.room,password:video.password,push:myCamera,view:'',label:video.name,audiodevice:'0',webcam:'',autostart:''})
 return <aside className="camera-publisher" aria-label="Моя камера">
  <div className="camera-publisher-bar"><strong>Моя камера</strong>{enabled?<><button onClick={()=>setExpanded(!expanded)}>{expanded?'Свернуть':'Показать'}</button><button onClick={()=>setEnabled(false)}>Выключить</button></>:<button onClick={()=>setConfirming(true)}>Включить</button>}</div>
  {confirming&&!enabled&&<div className="camera-publisher-confirm"><p>Разреши доступ к камере, чтобы друзья увидели тебя. Микрофон отключён.</p><button onClick={()=>{setEnabled(true);setExpanded(true);setConfirming(false)}}>Продолжить</button><button onClick={()=>setConfirming(false)}>Отмена</button></div>}
  {enabled&&<div className={expanded?'camera-publisher-frame':'camera-publisher-frame collapsed'}><iframe title="Настройка моей камеры" src={`https://vdo.ninja/#${params}`} allow="camera; autoplay" referrerPolicy="no-referrer"/></div>}
 </aside>
}
