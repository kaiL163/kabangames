import React, {createContext, useContext, useState} from 'react'
export const CameraContext=createContext(null)
export default function CameraStrip(){
 const {video,enabled,setEnabled}=useContext(CameraContext)
 const [confirming,setConfirming]=useState(false)
 const [expanded,setExpanded]=useState(true)
 if(!video)return null
 const params=new URLSearchParams({room:video.room,password:video.password,label:video.name,showlabels:'',webcam:'',autostart:''})
 const src=`https://vdo.ninja/#${params.toString()}`
 return <aside className={`camera-dock ${enabled?'is-enabled':''} ${expanded?'is-expanded':''}`} aria-label="Видеосвязь">
  <div className="camera-dock-bar"><div><span className="camera-live-dot"/><strong>{enabled?'Видеосвязь включена':'Камеры компании'}</strong><small>ЛОББИ {video.code}</small></div><div className="camera-dock-actions">{enabled&&<button type="button" onClick={()=>setExpanded(!expanded)}>{expanded?'Свернуть':'Показать'}</button>}{enabled?<button type="button" onClick={()=>setEnabled(false)}>Выключить</button>:<button type="button" onClick={()=>setConfirming(true)}>Включить камеру</button>}</div></div>
  {confirming&&!enabled&&<div className="camera-confirm"><p>Друзья в лобби увидят и услышат тебя. Браузер запросит доступ к камере и микрофону.</p><div className="camera-confirm-actions"><button type="button" className="button" onClick={()=>{setEnabled(true);setConfirming(false)}}>Разрешить и включить</button><button type="button" className="outline-button" onClick={()=>setConfirming(false)}>Отмена</button></div></div>}
  {enabled&&<div className={`camera-video ${expanded?'':'is-collapsed'}`}><iframe title="Видеосвязь игроков через VDO.Ninja" src={src} allow="camera; microphone; autoplay; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="no-referrer"/></div>}
 </aside>
}
