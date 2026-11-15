import React, {createContext, useContext, useEffect, useState} from 'react'
export const CameraContext=createContext(null)
export default function CameraStrip(){
 const {video,enabled,setEnabled}=useContext(CameraContext)
 const [confirming,setConfirming]=useState(false)
 const [cameraMode,setCameraMode]=useState(false)
 const [expanded,setExpanded]=useState(false)
 useEffect(()=>{document.body.classList.toggle('camera-dock-active',Boolean(video));document.body.classList.toggle('camera-dock-expanded',Boolean(video&&enabled&&expanded));return()=>{document.body.classList.remove('camera-dock-active','camera-dock-expanded')}},[video?.code,enabled,expanded])
 if(!video)return null
 const params=new URLSearchParams({room:video.room,password:video.password,label:video.name,showlabels:'',audiodevice:'0',chatbutton:'',...(cameraMode?{webcam2:''}:{videodevice:'0'})})
 const src=`https://vdo.ninja/#${params.toString()}`
 function join(withCamera){setCameraMode(withCamera);setExpanded(true);setEnabled(true);setConfirming(false)}
 return <aside className={`camera-dock ${enabled?'is-enabled':''} ${expanded?'is-expanded':''}`} aria-label="Видеосвязь">
  <div className="camera-dock-bar"><div><span className="camera-live-dot"/><strong>{enabled?cameraMode?'Камера подключена':'Ты в чате без камеры':'Видеочат компании'}</strong><small>ЛОББИ {video.code}</small></div><div className="camera-dock-actions">{enabled&&<><button type="button" onClick={()=>setExpanded(!expanded)}>{expanded?'Свернуть':'Показать'}</button>{cameraMode&&<button type="button" onClick={()=>join(false)}>Выключить камеру</button>}<button type="button" onClick={()=>{setEnabled(false);setExpanded(false);setConfirming(false)}}>Выйти из чата</button></>}{!enabled&&<><button type="button" onClick={()=>join(false)}>Войти без камеры</button><button type="button" onClick={()=>setConfirming(true)}>Войти с камерой</button></>}</div></div>
  {confirming&&!enabled&&<div className="camera-confirm"><p>Камера будет видна участникам лобби. Микрофон отключён. Браузер запросит доступ к камере.</p><div className="camera-confirm-actions"><button type="button" className="button" onClick={()=>join(true)}>Продолжить с камерой</button><button type="button" className="outline-button" onClick={()=>setConfirming(false)}>Отмена</button></div></div>}
  {enabled&&<div className={`camera-video ${expanded?'':'is-collapsed'}`}><iframe title="Видеочат игроков через VDO.Ninja" src={src} allow="camera; autoplay; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="no-referrer"/></div>}
 </aside>
}
