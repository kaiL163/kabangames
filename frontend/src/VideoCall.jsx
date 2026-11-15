import React, {useEffect, useMemo, useState} from 'react'

export default function VideoCall({video, lobbyCode}) {
  const [connected,setConnected] = useState(false)
  const [minimized,setMinimized] = useState(false)
  useEffect(()=>{setConnected(false);setMinimized(false)},[video.room])
  const src=useMemo(()=>{
    const params=new URLSearchParams({room:video.room,password:video.password,label:video.name,showlabels:''})
    return `https://vdo.ninja/#${params.toString()}`
  },[video.room,video.password,video.name])
  return <aside className={`video-panel ${minimized?'video-minimized':''}`} aria-label="Видеосвязь лобби">
    <div className="video-header"><div><span className="video-indicator" aria-hidden="true"/><strong>Видеосвязь</strong><small>ЛОББИ {lobbyCode}</small></div><div className="video-controls">{connected&&<button type="button" onClick={()=>setMinimized(!minimized)} aria-label={minimized?'Развернуть видео':'Свернуть видео'}>{minimized?'Развернуть':'Свернуть'}</button>}{connected&&<button type="button" onClick={()=>{setConnected(false);setMinimized(false)}}>Выйти</button>}</div></div>
    {!connected?<div className="video-intro"><p>Видьте и слышьте друг друга во время игры.</p><p className="video-note">Видеосвязь работает через VDO.Ninja. При подключении браузер может запросить доступ к камере и микрофону.</p><button type="button" className="video-primary" onClick={()=>setConnected(true)}>Подключить видео ↗</button></div>:<div className="video-frame-wrap" aria-hidden={minimized}><iframe title="Видеосвязь VDO.Ninja" src={src} allow="camera; microphone; autoplay; fullscreen" allowFullScreen referrerPolicy="no-referrer" tabIndex={minimized?-1:0}/></div>}
  </aside>
}
