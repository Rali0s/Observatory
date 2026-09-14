(()=>{document.querySelectorAll('svg[data-chart]').forEach(svg=>{const data=JSON.parse(document.getElementById(svg.dataset.chart).textContent),ns='http://www.w3.org/2000/svg';
const add=(tag,attrs,text)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text)e.textContent=text;svg.append(e);return e;};
const ceiling=svg.dataset.autoScale?Math.max(1,...data.map(r=>r.score)):1;
for(let i=0;i<=4;i++){const y=230-i*45;add('line',{x1:45,y1:y,x2:960,y2:y,stroke:'#d7dccc'});add('text',{x:5,y:y+5,fill:'#52624e','font-size':14},String(Math.round(i/4*ceiling*100)/100));}
const x=i=>45+i*915/Math.max(1,data.length-1),y=v=>230-v/ceiling*180;
const keys=data[0]?.series?Object.keys(data[0].series):['Open clues'],colors=['#254D3C','#956542','#577e97','#87659a'];
keys.forEach((key,j)=>{const val=r=>r.series?r.series[key]:r.score,color=colors[j%colors.length];
add('text',{x:45+j*220,y:22,fill:color,'font-size':14},key);
add('polyline',{points:data.map((r,i)=>`${x(i)},${y(val(r))}`).join(' '),fill:'none',stroke:color,'stroke-width':3});
data.forEach((r,i)=>{const dot=add('circle',{cx:x(i),cy:y(val(r)),r:4,fill:color,tabindex:0});const t=document.createElementNS(ns,'title');t.textContent=`${r.label} · ${key}: ${val(r)}`;dot.append(t);});});
add('text',{x:45,y:270,fill:'#52624e','font-size':14},'Beginning');add('text',{x:920,y:270,fill:'#52624e','font-size':14},'End');});})();
