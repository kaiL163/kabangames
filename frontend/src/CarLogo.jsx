import React,{useState,useId} from 'react'
import './car-logo.css'
const masks=['Фрагмент','Жалюзи','Мозаика','Монохром','Прорезь']
export default function CarLogo({image,emblem,mask=0,difficulty='normal',revealed=false,answer}){
 const [failed,setFailed]=useState(false)
 const clipId=useId()
 const variant=((mask%5)+5)%5
 const hard=difficulty==='hard'
 const [w,h]=emblem?.size||[100,100],crop=emblem?.crop||[0,0,100,100]
 const box=[crop[0]*w/100,crop[1]*h/100,crop[2]*w/100,crop[3]*h/100].join(' ')
 return <figure className={`car-puzzle ${revealed?'is-revealed':`is-hidden variant-${variant}`} ${hard?'is-hard':'is-normal'}`} aria-label={revealed?`Эмблема марки ${answer}`:'Задание: узнай марку по замаскированной эмблеме'}>
 <div className="car-puzzle-top"><span>{revealed?'ПОЛНАЯ ЭМБЛЕМА':hard?'СЛОЖНАЯ ЭМБЛЕМА':'УЗНАЙ ЭМБЛЕМУ'}</span><b>{revealed?'✓ Ответ открыт':masks[variant]}</b></div>
 <div className="car-puzzle-stage">{failed?<p role="status">Не удалось загрузить эмблему. Проверь соединение.</p>:<>{revealed?<img key={image} src={image} alt={answer} draggable="false" onLoad={()=>setFailed(false)} onError={()=>setFailed(true)}/>:emblem?<svg className="car-emblem" viewBox={box} role="img" aria-label="Эмблема без названия марки" xmlns="http://www.w3.org/2000/svg"><defs><clipPath id={clipId} clipPathUnits="userSpaceOnUse"><rect x={crop[0]*w/100} y={crop[1]*h/100} width={crop[2]*w/100} height={crop[3]*h/100}/></clipPath></defs><g clipPath={`url(#${clipId})`}><image href={image} width={w} height={h} onError={()=>setFailed(true)}/>{emblem?.cover.map(([x,y,width,height],index)=><rect key={index} x={x*w/100} y={y*h/100} width={width*w/100} height={height*h/100} fill="white"/>)}</g></svg>:<p role="status">Эмблема обновляется. Подождите следующего раунда.</p>}{!revealed&&variant===2&&<div className="car-puzzle-tiles" aria-hidden="true">{Array.from({length:24},(_,i)=><i key={i} className={(i*7+variant*11)%24<(hard?13:8)?'covered':''}/>)}</div>}</>}</div>
 <figcaption>{revealed?<><strong>{answer}</strong><span>Сравни полный знак с тем, что было видно в задании.</span></>:<><strong>{hard?'Узнай по деталям формы':'Узнай по форме'}</strong><span>Полный логотип откроется после завершения раунда.</span></>}</figcaption>
 </figure>
}
