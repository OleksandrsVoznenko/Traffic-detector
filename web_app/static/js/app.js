/*****************************************************************
 *  Palīdzības funkcijas: galvenes un bloka augstuma izlīdzināšana
 *  ar ekrāna pārtraukumiem vai plūsmas izmaiņām
 *****************************************************************/
function syncHeaderHeight(){
  const video=document.getElementById('live');
  const head =document.getElementById('site-head');
  if(video&&head){
    const h=video.clientHeight;
    if(h) head.style.height=(h/3)+'px';
  }
}
function syncViolBlockHeight(){
  const video=document.getElementById('live');
  const viol =document.getElementById('viol-block');
  if(video&&viol){
    const h=video.clientHeight;
    if(h) viol.style.maxHeight=h+'px';      // Scroll bloka iekšpusē
  }
}
function adjustLayout(){
  syncHeaderHeight();
  syncViolBlockHeight();
}
window.addEventListener('resize',adjustLayout);


 // PĀRKĀPUMI
function appendViolation(v){
  const list=document.getElementById('viol-list');
  if(list.querySelector(`li[data-file="${v.file}"]`))return;

  const li=document.createElement('li');
  li.className='violation';
  li.dataset.file=v.file;
  li.innerHTML=`
      <img src="/violation_img/${v.file}" alt="screenshot">
      <div class="meta"><span class="time">${v.ts}</span></div>`;
  li.addEventListener('click',openModal);
  list.prepend(li);
}

const modal=document.getElementById('modal');
const modalImg=document.getElementById('modal-img');
const modalDownload=document.getElementById('modal-download');

function openModal(){
  const url=`/violation_img/${this.dataset.file}`;
  modalImg.src=url; modalDownload.href=url;
  modal.classList.remove('hidden'); adjustLayout();
}
document.getElementById('modal-close').onclick=()=>modal.classList.add('hidden');
modal.onclick=e=>{ if(e.target===modal) modal.classList.add('hidden'); };

// Sākotnējā ielāde
function loadInitialViolations(){
  fetch('/api/violations')
    .then(r=>r.json())
    .then(list=>{
      list.reverse().forEach(appendViolation);
      adjustLayout();
    });
}
loadInitialViolations();

// SSE straume jauno pārkāpumi
const evts=new EventSource('/viol_stream');
evts.onmessage=ev=>{
  appendViolation(JSON.parse(ev.data));
  updateStats();
  adjustLayout();
};

// Chart.js
let chart=null;
function renderChart(labels,values){
  const ctx=document.getElementById('viol-chart').getContext('2d');
  if(chart)chart.destroy();
  chart=new Chart(ctx,{
    type:'bar',
    data:{labels,datasets:[{
      label:'Pārkāpumu skaits',
      data:values,
      backgroundColor:'#ff0000',
      borderColor:'#b30000',
      borderWidth:1
    }]},
    options:{
      responsive:true,
      plugins:{legend:{labels:{color:'#fff'}}},
      scales:{
        x:{ticks:{color:'#fff'},title:{display:true,text:'Datums',color:'#fff'},grid:{color:'#444',lineWidth:0.5}},
        y:{beginAtZero:true,ticks:{stepSize:1,precision:0,color:'#fff'},title:{display:true,text:'Pārkāpumu skaits',color:'#fff'},grid:{color:'#444',lineWidth:0.5}}
      }
    }
  });
}
function updateStats(){
  fetch('/api/violations_stats')
    .then(r=>r.json())
    .then(d=>renderChart(d.labels,d.values));
}
updateStats();

// Izkārtojuma korekcija, kad parādās kāds kadrs
document.getElementById('live').addEventListener('load',adjustLayout);

// DETECTORS  ON / OFF
const liveImg  =document.getElementById('live');
const toggleBtn=document.getElementById('detector-btn');

function setDetectorUI(running){
  if(running){
    toggleBtn.textContent='Izslēgt detektoru';
    toggleBtn.classList.add('running');
    liveImg.src='/video_feed?'+Date.now();
  }else{
    toggleBtn.textContent='Ieslēgt detektoru';
    toggleBtn.classList.remove('running');
    liveImg.src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAJiTEJUAAAAASUVORK5CYII=';
  }
  adjustLayout();
}
async function refreshDetectorStatus(){
  try{
    const r=await fetch('/api/detector_status');
    const {running}=await r.json();
    setDetectorUI(running);
  }catch{/* ignore */}
}
toggleBtn.addEventListener('click',async()=>{
  toggleBtn.disabled=true;
  try{ await fetch('/api/detector_toggle',{method:'POST'}); }
  finally{
    await refreshDetectorStatus();
    toggleBtn.disabled=false;
  }
});
refreshDetectorStatus();
