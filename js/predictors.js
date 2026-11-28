(()=>{
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>v===null||v===undefined||String(v).trim()===''?null:(Number.isFinite(Number(v))?Number(v):null);
const rankfmt=v=>n(v)==null?'?':Number(v).toLocaleString('en-IN',{maximumFractionDigits:2});
const status=(el,msg)=>{if(el)el.textContent=msg};
async function load(name){const r=await fetch(`../data/${name}`);if(!r.ok)throw Error(`Could not load ${name}; serve this site over HTTP(S).`);const data=await r.json(); Object.assign(collegePlacements,data.collegePlacements); return data}
function badge(chance){const cls=chance==='Safe'?'chance-safe':chance==='Moderate'?'chance-moderate':chance==='Ambitious'?'chance-ambitious':'chance-reference';const label=chance==='Ambitious'?'Ambitious / Spot Round':chance||'Reference only';return `<span class="chance-badge ${cls}">${esc(label)}</span>`}
function chanceFor(rank,close){rank=n(rank);close=n(close);if(!rank||!close)return 'Reference only';if(rank<=close*.85)return 'Safe';if(rank<=close*1.15)return 'Moderate';if(rank<=close*1.20)return 'Ambitious';return 'Outside range'}
function trendMarkup(rec){if(rec.instituteType==='IIT')return `<span class="trend trend-na">${ENGINEERING_CUTOFF_LABEL}</span>`;const year=Number(rec.year)||2025,rawRound=String(rec.round||''),round=rawRound?` · ${/^\d+$/.test(rawRound)?`R${rawRound}`:rawRound.replace(/^Round\s*/i,'R')}`:'',basis=year===2026?`Based on 2026 counseling data${round}`:`Based on latest available ${year} counseling data; 2026 row unavailable${round}`;return `<span class="trend trend-na" title="${esc(basis)}">${ENGINEERING_CUTOFF_LABEL}</span><span class="small"> · ${esc(basis)}</span>`}
function stat(label,value,sub=''){return `<div class="stat-card"><span>${esc(label)}</span><strong>${esc(value)}</strong>${sub?`<small class="small">${esc(sub)}</small>`:''}</div>`}
const categoryRankFactor={OPEN:1,EWS:.105,'OBC-NCL':.30,SC:.18,ST:.075,UR:1,OBC:.30};
function categoryRank(air,category,ratios){if(n(air)==null)return null;const f=n(ratios?.[category]??categoryRankFactor[category]??1)||1;return Math.max(1,Math.round(Number(air)*f))}
const JEE_ADVANCED_AIR_CURVE=[[0,200000],[95,22000],[125,13000],[165,6000],[210,2000],[260,500],[310,100],[360,1]];
function estimateJeeAdvancedAir(marks,difficulty){const shifts={easy:-10,moderate:0,tough:10},score=Math.max(0,Math.min(360,marks+(shifts[difficulty]||0)));for(let i=1;i<JEE_ADVANCED_AIR_CURVE.length;i++){const [upperMarks,upperRank]=JEE_ADVANCED_AIR_CURVE[i];if(score<=upperMarks){const [lowerMarks,lowerRank]=JEE_ADVANCED_AIR_CURVE[i-1];return Math.max(1,Math.round(lowerRank+(score-lowerMarks)*(upperRank-lowerRank)/(upperMarks-lowerMarks)))}}return 1}
function estimatedAirRange(air){return{low:Math.max(1,Math.floor(air*.85)),high:Math.ceil(air*1.15),estimate:air}}
const NEET_2025_APPEARED=2209318;
const NEET_CUTOFF_LABEL='2027 Projected Cutoff';
const ENGINEERING_CUTOFF_LABEL='2027 Projected Cutoff';
function stateFor(name=''){
 const s=String(name).toLowerCase();const rules=[['tiruchirappalli|trichy','Tamil Nadu'],['calicut|kozhikode','Kerala'],['surathkal|karnataka','Karnataka'],['warangal','Telangana'],['bhubaneswar|rourkela','Odisha'],['hamirpur','Himachal Pradesh'],['jalandhar','Punjab'],['jaipur|malaviya','Rajasthan'],['kurukshetra','Haryana'],['agartala','Tripura'],['silchar','Assam'],['patna','Bihar'],['raipur','Chhattisgarh'],['durgapur','West Bengal'],['malda','West Bengal'],['jamshedpur','Jharkhand'],['bhopal','Madhya Pradesh'],['allahabad|prayagraj','Uttar Pradesh'],['srinagar','Jammu and Kashmir'],['surat','Gujarat'],['nagpur','Maharashtra'],['goa','Goa'],['delhi','Delhi'],['manipur','Manipur'],['meghalaya','Meghalaya'],['mizoram','Mizoram'],['nagaland','Nagaland'],['sikkim','Sikkim'],['uttarakhand','Uttarakhand'],['pondicherry|puducherry','Puducherry'],['arunachal','Arunachal Pradesh'],['andhra pradesh','Andhra Pradesh']];
 for(const [pattern,state] of rules)if(new RegExp(pattern,'i').test(s))return state;return ''
}
function makeId(prefix,r){if(prefix==='neet')return [prefix,r.college,r.course||r.program,r.quota==='State'?'SQ':r.quota,r.category].join('|');return [prefix,r.year,r.collegeCode||r.college,r.program||r.course,r.quota,r.category,r.gender||'',r.round||''].join('|')}
const choiceKey=prefix=>`campuskit-counseling-choices-${prefix}`;
function readChoices(prefix){try{return JSON.parse(localStorage.getItem(choiceKey(prefix))||'[]')}catch{return []}}
function writeChoices(prefix,items){localStorage.setItem(choiceKey(prefix),JSON.stringify(items))}
function csvValue(s){return `"${String(s??'').replace(/"/g,'""')}"`}
const collegePlacements = Object.create(null);
function placementFor(prefix, record) {
 const exam=prefix==='kcet'?(record.exam||(String(record.quota||'').includes('COMEDK')?'COMEDK':'KCET')):'JEE';
 return collegePlacements[`${exam}|${record.college}`]||record;
}
function placementSummary(report = {}) {
 return report.highestLpaDisplay?`<span class="placement-peak">${esc(report.highestLpaDisplay)}</span>`:'';
}
function medicalValue(value, kind='text') {
 if(value===null||value===undefined||String(value).trim()==='')return 'Data pending';
 if(typeof value==='number'&&Number.isFinite(value)){
  if(kind==='money')return `₹${value.toLocaleString('en-IN')}/year`;
  if(kind==='lpa')return `₹${value.toLocaleString('en-IN')} LPA`;
  if(kind==='stipend')return `₹${value.toLocaleString('en-IN')}/month`;
 }
 return String(value);
}
function medicalCollegeSummary(details) {
 details=details||{};
 const bondClass=details.hasBond?'neet-bond-applies':'neet-no-bond';
 const bondLabel=details.hasBond?'Bond applies':'No Bond';
 const bond=`<span class="neet-college-metric neet-bond-badge ${bondClass}" title="${esc(details.serviceBond||'')}"><strong>Service Bond</strong> ${esc(bondLabel)} · ${esc(medicalValue(details.serviceBond))}</span>`;
 return `<span class="neet-college-summary"><span class="neet-college-metric"><strong>Internship Stipend</strong> ${esc(medicalValue(details.internshipStipend))}</span><span class="neet-college-metric"><strong>Annual Fee · supplied fee schedule</strong> ${esc(medicalValue(details.annualFeeDisplay))}</span>${bond}</span>`;
}
function downloadCsv(prefix,items){if(!items.length)return;if(prefix==='neet'){downloadNeetCsv(items);return}const cols=['priority','college','program','quota','category','closingRank','collegeHighestPackage','collegeHighestLpaNumeric','branchAveragePackage','branchAvgLpaNumeric','placementSource','source'];const lines=[cols.join(','),...items.map((x,i)=>{const placement=placementFor(prefix,x);return[i+1,x.college,x.program||x.course,x.quota,x.category,x.closingRank,placement.highestLpaDisplay,placement.highestLpaNumeric,x.branchAvgLpa,x.branchAvgLpaNumeric,placement.placementSource,x.source].map(csvValue).join(',')})];const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`campuskit-${prefix}-choice-list.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function downloadNeetCsv(items){const cols=['priority','college','state','city','course','collegeType','quota','category','cutoffLabel','projectedClosingAIR','historicalSourceYear','exactHistoricalClosingRank','model','internshipStipend','annualFeeDisplay','applicableAnnualFee','serviceBond','eligibilityNote','historicalSource'];const lines=[cols.join(','),...items.map((x,i)=>[i+1,x.college,x.state,x.city,x.course,x.collegeType,x.quotaLabel||x.counsellingQuota,x.category,NEET_CUTOFF_LABEL,x.closingRank,x.sourceYear??x.historicalReference?.year,x.historicalClosingRank??x.historicalReference?.closingRank,x.model,x.internshipStipend,x.annualFeeDisplay,x.annualFeeNumeric,x.serviceBond,x.eligibilityNote,x.historicalReference?.source||x.source].map(csvValue).join(','))];const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='campuskit-neet-choice-list.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function renderChoices(prefix){const items=readChoices(prefix),box=$(`#${prefix}-choice-list`),count=$(`#${prefix}-choice-count`);if(count)count.textContent=`${items.length} saved`;if(!box)return;box.innerHTML=items.length?items.map((x,i)=>`<div class="choice-item"><span class="choice-index">${i+1}</span><span><strong>${esc(x.college)}</strong><br><span class="small">${esc(x.program||x.course||'')} · ${esc(prefix==='neet'?(x.quotaLabel||x.quota):x.quota||'')} · ${esc(x.category||'')}</span>${prefix==='neet'?`<br><span class="small">${esc(NEET_CUTOFF_LABEL)} · ${x.available===false?'Route / intake unconfirmed':`AIR ${rankfmt(x.closingRank)}`}</span>`:''}</span><span class="choice-actions"><button type="button" data-choice-move="${i}" data-dir="-1" aria-label="Move up" ${i===0?'disabled':''}>↑</button><button type="button" data-choice-move="${i}" data-dir="1" aria-label="Move down" ${i===items.length-1?'disabled':''}>↓</button><button type="button" data-choice-remove="${i}" aria-label="Remove">×</button></span></div>`).join(''):'<p class="empty-state">No courses saved yet. Use ☆ in a course card to add choices.</p>'}
function initChoices(prefix,state){renderChoices(prefix);const box=$(`#${prefix}-choice-list`);box?.addEventListener('click',e=>{const move=e.target.closest('[data-choice-move]'),remove=e.target.closest('[data-choice-remove]');let a=readChoices(prefix);if(move){const i=+move.dataset.choiceMove,j=i+(+move.dataset.dir);if(j>=0&&j<a.length)[a[i],a[j]]=[a[j],a[i]];writeChoices(prefix,a);renderChoices(prefix)}if(remove){a.splice(+remove.dataset.choiceRemove,1);writeChoices(prefix,a);renderChoices(prefix)}});$(`#${prefix}-export-csv`)?.addEventListener('click',()=>downloadCsv(prefix,readChoices(prefix)));$(`#${prefix}-clear-choices`)?.addEventListener('click',()=>{writeChoices(prefix,[]);renderChoices(prefix)});$("[data-print-choices='"+prefix+"']")?.addEventListener('click',()=>{document.body.classList.add('campuskit-print-choices');window.print();setTimeout(()=>document.body.classList.remove('campuskit-print-choices'),1000)});document.body.addEventListener('click',e=>{const b=e.target.closest(`[data-save-choice][data-prefix="${prefix}"]`);if(!b)return;const rec=state.byId.get(b.dataset.saveChoice);if(!rec)return;let list=readChoices(prefix);const id=makeId(prefix,rec),at=list.findIndex(x=>makeId(prefix,x)===id);if(at>=0)list.splice(at,1);else list.push(rec);writeChoices(prefix,list);renderChoices(prefix);b.classList.toggle('saved',at<0);b.textContent=at<0?'★ Shortlisted':'☆ + Shortlist';b.setAttribute('aria-pressed',at<0?'true':'false');b.setAttribute('aria-label',at<0?'Remove from counseling choice list':'Add to counseling choice list')})}
function chanceFilter(prefix){return $(`[data-chance-filter].active`)?.dataset.chanceFilter||'all'}
function setupSearchAndFilters(prefix,state,draw){const q=$(`#${prefix}-search`);q?.addEventListener('input',draw);$$(`[data-chance-filter]`).forEach(b=>b.addEventListener('click',()=>{const group=b.closest('.chance-filters');group?.querySelectorAll('[data-chance-filter]').forEach(x=>x.classList.toggle('active',x===b));draw()}));if(prefix==='neet'){const sort=$('#neet-sort'),fee=$('#neet-max-fee');sort?.addEventListener('change',draw);fee?.addEventListener('input',draw)}else $(`#${prefix}-sort`)?.addEventListener('change',draw)}
function formatTrend(rec,year){const currentYear=Number(rec.year)||2025,previousYear=Number(rec.previousYear)||year||currentYear-1;if(rec.previousYearClosingRank)return `${previousYear} ${rankfmt(rec.previousYearClosingRank)} → ${currentYear} ${rankfmt(rec.closingRank)}`;return `${currentYear} cutoff reference`}
function neetTrendMarkup(rec){const reference=rec.historicalReference,exact=rec.projectionMethod==='unchanged-historical-baseline',basis=reference?(exact?`Based on ${reference.year} counselling · source AIR ${rankfmt(reference.closingRank)} retained exactly`:`Category scenario using ${reference.year} reference · not an observed category cutoff`):'Planning assumption · no matching historical cutoff';return `<span class="trend trend-na">${esc(NEET_CUTOFF_LABEL)}</span><br><span class="small">${esc(basis)}</span>`}
function neetSeatQuotaPriority(record){const seat=String(record.seatQuota||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();if(['all india','open seat quota','govt quota','government quota'].some(x=>seat.includes(x)))return 0;if(['deemed paid','self financed merit'].some(x=>seat.includes(x)))return 1;if(seat.includes('management quota'))return 3;if(['employees state insurance','esi','nri','foreign'].some(x=>seat.includes(x)))return 4;return 2}
function neetRoundOrder(record){const round=String(record.round||'').toLowerCase();if(round.includes('stray'))return 100;if(round.includes('mop'))return 90;return Number(round.match(/round\s*(\d+)/)?.[1])||0}
function chooseNeetCutoff(records){return [...records].sort((a,b)=>neetSeatQuotaPriority(a.cutoff)-neetSeatQuotaPriority(b.cutoff)||neetRoundOrder(b.cutoff)-neetRoundOrder(a.cutoff)||Number(b.cutoff.closingRank||0)-Number(a.cutoff.closingRank||0)||String(a.cutoff.seatQuota||'').localeCompare(String(b.cutoff.seatQuota||'')))[0]}
function flattenNeetCutoffs(records){const grouped=new Map();for(const record of records)for(const cutoff of record.cutoffs||[]){const pool=cutoff.quota==='State'?'SQ':cutoff.quota,key=JSON.stringify([record.college,record.course,pool,cutoff.category]),previous=grouped.get(key),priority=c=>Number(c.status==='projected')*10000+Number(c.year||0);if(!previous||priority(cutoff)>priority(previous.cutoff))grouped.set(key,{record,cutoff,pool})}return [...grouped.values()].map(({record,cutoff,pool})=>{const {cutoffs,historicalCutoffs,...details}=record;return{...details,...cutoff,year:2027,projectionYear:2027,yearLabel:NEET_CUTOFF_LABEL,course:record.course,program:record.course,type:record.collegeType,counsellingQuota:pool,quota:pool}})}
function syncNeetChoices(records){const saved=readChoices('neet');if(!Array.isArray(saved)||!saved.length)return;const rows=flattenNeetCutoffs(records),current=new Map(rows.map(r=>[makeId('neet',r),r])),aliases=new Map();for(const record of records)for(const alias of [record.college,record.sourceName,...(record.aliases||[]),...(record.historicalCutoffs||[]).map(c=>c.sourceCollege)].filter(Boolean))aliases.set(JSON.stringify([alias,record.course]),record.college);const seen=new Set(),updated=[];for(const old of saved){const college=aliases.get(JSON.stringify([old.college,old.course||old.program]))||old.college,key=makeId('neet',{...old,college}),row=current.get(key)||old;if(seen.has(key))continue;seen.add(key);updated.push(row)}writeChoices('neet',updated)}
function renderTable(prefix,state,renderer){const q=($(`#${prefix}-search`)?.value||'').trim().toLowerCase(),chance=chanceFilter(prefix),maxFee=prefix==='neet'?n($('#neet-max-fee')?.value):null;let rows=state.rows.filter(r=>(!q||r._search.includes(q))&&(chance==='all'||r.chance===chance)&&(maxFee===null||(n(r.annualFeeNumeric)!==null&&n(r.annualFeeNumeric)<=maxFee)));const distanceSort=(a,b)=>(a._distance??Infinity)-(b._distance??Infinity);const descendingSort=key=>(a,b)=>{const x=n(a[key]),y=n(b[key]);return x===null?(y===null?distanceSort(a,b):1):y===null?-1:y-x||distanceSort(a,b)};if(prefix==='neet'){const sort=$('#neet-sort')?.value||'rank';if(sort==='fee')rows.sort((a,b)=>{const x=n(a.annualFeeNumeric),y=n(b.annualFeeNumeric);return x===null?(y===null?distanceSort(a,b):1):y===null?-1:x-y||distanceSort(a,b)});else if(sort==='stipend')rows.sort(descendingSort('stipendNumeric'));else if(sort==='bond')rows.sort((a,b)=>Number(Boolean(a.hasBond))-Number(Boolean(b.hasBond))||distanceSort(a,b));else rows.sort(distanceSort)}else{const sort=$(`#${prefix}-sort`)?.value||'rank';if(sort==='branch-lpa')rows.sort(descendingSort('branchAvgLpaNumeric'));else if(sort==='peak-lpa')rows.sort(descendingSort('highestLpaNumeric'));else rows.sort(distanceSort)}const total=rows.length,collegeTotal=new Set(rows.map(r=>r.college)).size,eligibleCollegeTotal=new Set(rows.filter(r=>r.chance!=='Reference only').map(r=>r.college)).size,limit=prefix==='neet'?700:400;renderer(rows.slice(0,limit));const count=$(`#${prefix}-stats .stat-card:last-child strong`);if(count)count.textContent=eligibleCollegeTotal.toLocaleString();return {total,collegeTotal,eligibleCollegeTotal,shown:Math.min(total,limit)}}
function saveButton(prefix,r){const id=makeId(prefix,r),saved=readChoices(prefix).some(x=>makeId(prefix,x)===id);return `<button class="save-choice ${saved?'saved':''}" type="button" data-prefix="${prefix}" data-save-choice="${esc(id)}" aria-label="${saved?'Remove from':'Add to'} counseling choice list" aria-pressed="${saved}">${saved?'★ Shortlisted':'☆ + Shortlist'}</button>`}
function rankChange(rank,closing){rank=n(rank);closing=n(closing);return rank&&closing?Math.abs(rank-closing)/closing:null}
function attachSearch(r,prefix){r._search=[r.college,r.program,r.course,r.branch,r.city,r.state,r.quota,r.category,r.gender].filter(Boolean).join(' ').toLowerCase();return r}
function matchCategory(dataValue,wanted){const x=String(dataValue||'').toUpperCase().trim(),w=String(wanted||'').toUpperCase().trim();return x===w||x.startsWith(`${w} `)||x.startsWith(`${w}(`)}
function toggleInputs(select,sets){const apply=()=>{for(const [selector,values] of Object.entries(sets))$$(selector).forEach(el=>el.hidden=!values.includes(select.value))};select.addEventListener('change',apply);apply()}
function setupTwoStep(prefix,form,mode,directModes){const panel=$(`#${prefix}-result-panel`),view=$(`#${prefix}-view-colleges`),stats=$(`#${prefix}-stats`),submit=form.querySelector('button[type="submit"]'),direct=()=>directModes.includes(mode.value);function reset(){panel.hidden=true;view.disabled=true;stats.innerHTML='';submit.textContent=direct()?'Find colleges by known rank':'Estimate rank'}mode.addEventListener('change',reset);form.addEventListener('reset',()=>setTimeout(reset,0));view.addEventListener('click',()=>{if(view.disabled)return;panel.hidden=false;view.disabled=true;panel.scrollIntoView({behavior:'smooth',block:'start'})});reset();return{reset,complete(){if(direct()){panel.hidden=false;view.disabled=true}else{panel.hidden=true;view.disabled=false}}}}
function projectedAirRange(percentile,lowPool,highPool){const fraction=(100-Math.max(0,Math.min(100,Number(percentile))))/100;return{low:Math.max(1,Math.round(lowPool*fraction)),high:Math.max(1,Math.round(highPool*fraction)),estimate:Math.max(1,Math.round(((lowPool+highPool)/2)*fraction))}}
function probabilityPercent(rank,closing){rank=n(rank);closing=n(closing);if(!rank||!closing)return null;return Math.max(5,Math.min(99,Math.round(50+280*(1-rank/closing))))}
function probabilityMarkup(rank,closing,chance){const percent=probabilityPercent(rank,closing);if(percent==null||chance==='Reference only')return `${badge(chance)}<span class="small">Chance not comparable across rank lists</span>`;return `<div class="course-chance"><div><strong>${percent}%</strong> chance ${badge(chance)}</div><span class="probability-track" role="meter" aria-label="Heuristic seat chance" aria-valuemin="5" aria-valuemax="99" aria-valuenow="${percent}"><span class="probability-fill chance-${chance.toLowerCase()}" style="width:${percent}%"></span></span></div>`}
function inferCity(name=''){const s=String(name).toLowerCase(),rules=[['tiruchirappalli|trichy','Tiruchirappalli'],['calicut|kozhikode','Kozhikode'],['surathkal','Surathkal'],['warangal','Warangal'],['bhubaneswar','Bhubaneswar'],['rourkela','Rourkela'],['hamirpur','Hamirpur'],['jalandhar','Jalandhar'],['jaipur','Jaipur'],['kurukshetra','Kurukshetra'],['agartala','Agartala'],['silchar','Silchar'],['patna','Patna'],['raipur','Raipur'],['durgapur','Durgapur'],['malda','Malda'],['jamshedpur','Jamshedpur'],['bhopal','Bhopal'],['allahabad|prayagraj','Prayagraj'],['srinagar','Srinagar'],['surat','Surat'],['nagpur','Nagpur'],['bengaluru|bangalore','Bengaluru'],['mysuru|mysore','Mysuru'],['mangaluru|mangalore','Mangaluru'],['belagavi|belgaum','Belagavi'],['hubballi|hubli','Hubballi'],['dharwad','Dharwad'],['new delhi|delhi','New Delhi'],['guwahati','Guwahati'],['chennai','Chennai'],['mumbai','Mumbai'],['pune','Pune'],['hyderabad','Hyderabad'],['kolkata','Kolkata'],['ahmedabad','Ahmedabad'],['kochi','Kochi'],['thiruvananthapuram|trivandrum','Thiruvananthapuram']];for(const [pattern,city] of rules)if(new RegExp(pattern,'i').test(s))return city;return ''}
function collegeLocation(r,prefix){const usable=value=>{const text=String(value??'').trim();return text&&!/^(?:location\s+(?:not\s+updated|not\s+published|unavailable|not\s+available|not\s+found)|(?:city|state|location)\s+(?:not\s+updated|unknown|unavailable)|not\s+updated|unknown|unavailable|n\/?a|none|null)$/i.test(text)?text:''},city=usable(r.city)||inferCity(r.college),stateName=usable(r.state)||usable(r.collegeState)||stateFor(r.college)||(prefix==='kcet'?'Karnataka':'');return [city,stateName].filter(Boolean).join(', ')||usable(r.instituteType)||usable(r.collegeType)||'All-India Institute'}
function collegeQuota(r,prefix){if(prefix==='jee')return r.quota==='HS'?'Home State':r.quota==='OS'?'Other State':r.quota==='AI'?'All India':r.quota;if(prefix==='neet')return r.quotaLabel||(['State','SQ'].includes(r.counsellingQuota)?'SQ — state counselling':'AIQ / open counselling');return r.quota==='HK'?'KCET · 371J / HK':'KCET / COMEDK'}
function renderCollegeCards(prefix,state,rows){
 const box=$(`#${prefix}-results`);
 if(!rows.length){box.innerHTML='<p class="empty-state">No matching courses. Check your rank basis and filters.</p>';return}
 const groups=new Map();
 for(const row of rows){const key=row.college||'College not named';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row)}
 box.innerHTML=[...groups.entries()].map(([college,courses])=>{
  const first=courses[0],type=prefix==='jee'?(first.instituteType||'Engineering institute'):prefix==='neet'?(first.collegeType||'Medical college'):(first.exam==='COMEDK'?'Private Engineering':'Engineering college');
  const quotas=[...new Set(courses.map(r=>collegeQuota(r,prefix)))].join(' / '),courseKinds=new Set(courses.map(r=>String(r.program||r.course||r.branch||'').toUpperCase())),seenMedicalCourses=new Set();
  const medicalCardSummary=prefix==='neet'&&courseKinds.size===1?medicalCollegeSummary(first):'',collegePlacement=prefix==='neet'?null:placementFor(prefix,first);
  return `<details class="college-card" open><summary class="college-card-summary"><span class="college-card-title"><strong>${esc(college)}</strong><small>${esc(collegeLocation(first,prefix))} · ${esc(type)}</small>${medicalCardSummary}</span><span class="college-card-meta"><span>${esc(quotas)}</span>${prefix==='neet'?'':placementSummary(collegePlacement)}<span>${courses.length} course${courses.length===1?'':'s'}</span></span></summary><div class="course-list">${courses.map(r=>{
   const courseKey=String(r.program||r.course||r.branch||'').toUpperCase();let courseMedicalSummary='';
   if(prefix==='neet'&&courseKinds.size>1&&!seenMedicalCourses.has(courseKey)){courseMedicalSummary=medicalCollegeSummary(r);seenMedicalCourses.add(courseKey)}
   const branchPlacement=prefix==='neet'?'':`<div class="course-package"><span class="small">Branch Avg LPA</span><strong>${esc(r.branchAvgLpa?r.branchAvgLpa.replace(/^Avg:\s*/i,''):'Not listed')}</strong></div>`;
   const medicalNotes=prefix==='neet'?`<span class="small">${esc(r.categoryBasis||'')}</span><span class="small">${esc(r.eligibilityNote||'')}</span><span class="small">${esc(r.annualFeeBasis||'Applicable annual fee')}: ${esc(medicalValue(r.annualFeeNumeric,'money'))}</span>`:'';
   return `<article class="${prefix==='neet'?'course-row':'course-row engineering-course-row'}"><div class="course-main"><strong>${esc(r.program||r.course||r.branch||'Course not named')}</strong><span class="small">${esc(r.branch||r.course||'')} · ${esc(collegeQuota(r,prefix))} · ${esc(r.category||'Category not published')}${r.gender?` · ${esc(r.gender)}`:''}${r.rankBasis?` · ${esc(r.rankBasis)}`:''}</span>${medicalNotes}</div><div class="course-rank"><span class="small">${prefix==='neet'?'Projected closing AIR':'Closing rank'}</span><strong>${rankfmt(r.closingRank)}</strong></div>${branchPlacement}<div class="course-probability">${prefix==='neet'?badge(r.chance):probabilityMarkup(state.rank,r.closingRank,r.chance)}</div><div class="course-insights">${courseMedicalSummary}<span>${prefix==='neet'?neetTrendMarkup(r):trendMarkup(r)}</span></div><div class="course-save">${saveButton(prefix,r)}</div></article>`
  }).join('')}</div></details>`
 }).join('');
}

async function initJee(){
 const prefix='jee',form=$('#jee-form');if(!form)return;
 const state={rows:[],byId:new Map(),rank:null,air:null,categoryRank:null};
 let data,marksData;
 try{[data,marksData]=await Promise.all([load('josaa-cutoffs.json'),load('jee-marks-percentile.json')])}catch(e){status($('#jee-result-note'),e.message);return}
 const exam=$('#jee-exam'),mode=$('#jee-input-mode'),homeState=$('#jee-home-state'),homeStateField=$('#jee-home-state-field'),advancedQuotaNote=$('#jee-advanced-quota-note'),marksInput=$('#jee-marks'),shiftInput=$('#jee-shift'),percentileOption=mode.querySelector('option[value="percentile"]'),twoStep=setupTwoStep(prefix,form,mode,['air']);
 function updateModeFields(){const advanced=exam.value==='advanced';$('.jee-marks-field').hidden=mode.value!=='marks';$('.jee-shift-field').hidden=mode.value!=='marks';$('.jee-percentile-field').hidden=advanced||mode.value!=='percentile';$('.jee-air-field').hidden=mode.value!=='air'}
 function updateExamForm(){
  const advanced=exam.value==='advanced';
  percentileOption.hidden=advanced;
  if(advanced&&mode.value==='percentile')mode.value='marks';
  $('#jee-input-mode option[value="marks"]').textContent=advanced?'Expected JEE Advanced marks + paper difficulty':'Expected JEE Main marks + shift';
  $('#jee-input-mode option[value="percentile"]').textContent='Known JEE Main percentile';
  $('#jee-input-mode option[value="air"]').textContent=advanced?'Known JEE Advanced AIR / Category Rank':'Known AIR / category rank';
  $('#jee-marks-label').textContent=advanced?'Expected JEE Advanced Marks (out of 360)':'Expected JEE Main Marks (out of 300)';
  marksInput.max=advanced?'360':'300';
  marksInput.placeholder=advanced?'e.g. 165':'e.g. 150';
  if(!advanced&&Number(marksInput.value)>300)marksInput.value='300';
  $('#jee-shift-label').textContent=advanced?'JEE Advanced Paper Difficulty':'JEE Main Shift Difficulty';
  const difficultyLabels=advanced?{moderate:'Moderate Paper',tough:'Tough Paper',easy:'Easy Paper'}:{moderate:'Moderate',easy:'Easy',tough:'Tough'};
  for(const value of advanced?['moderate','tough','easy']:['moderate','easy','tough']){
   const option=shiftInput.querySelector(`option[value="${value}"]`);
   option.textContent=difficultyLabels[value];
   shiftInput.append(option)
  }
  homeStateField.hidden=advanced;
  homeState.disabled=advanced;
  homeState.required=!advanced;
  advancedQuotaNote.hidden=!advanced;
  $('#jee-rank-label').textContent=advanced?'Known JEE Advanced AIR / category rank':'Rank';
  $('#jee-rank').placeholder=advanced?'AIR for OPEN; JEE Advanced category rank for reserved seats':'AIR for OPEN; category rank for reserved seats';
  updateModeFields()
 }
 exam.addEventListener('change',()=>{updateExamForm();twoStep.reset()});
 mode.addEventListener('change',()=>{updateModeFields();twoStep.reset()});
 form.addEventListener('reset',()=>setTimeout(updateExamForm,0));
 updateExamForm();
 function draw(){const result=renderTable(prefix,state,rows=>renderCollegeCards(prefix,state,rows));status($('#jee-result-note'),`${result.total.toLocaleString()} eligible course rows across ${result.eligibleCollegeTotal.toLocaleString()} colleges${result.total>result.shown?` - showing first ${result.shown}`:''}. Chances are rank-based heuristics; placement figures come from the supplied college list.`);return result}
 setupSearchAndFilters(prefix,state,draw);initChoices(prefix,state);
 form.addEventListener('submit',e=>{
  e.preventDefault();twoStep.reset();
  try{
   const type=exam.value,category=$('#jee-category').value,imode=mode.value,home=homeState.value;
   let air=null,catRank=null,percentile=null,sourceLabel='',airRange=null;
   if(imode==='marks'){
    const marks=Number(marksInput.value),maxMarks=type==='advanced'?360:300;
    if(!Number.isFinite(marks)||marks<0||marks>maxMarks)throw Error(`Enter valid marks from 0 to ${maxMarks}.`);
    if(type==='advanced'){
     air=estimateJeeAdvancedAir(marks,shiftInput.value);
     catRank=categoryRank(air,category,marksData.categoryRankRatios);
     airRange=estimatedAirRange(air);
     sourceLabel=`JEE Advanced 360-mark curve · ${shiftInput.options[shiftInput.selectedIndex].text}`;
    }else{
     const curve=marksData.curves?.[shiftInput.value];
     if(!curve?.length)throw Error('JEE Main marks curve is missing.');
     const point=curve[Math.round(marks)];
     percentile=point.percentile;
     airRange=projectedAirRange(percentile,1450000,1550000);
     air=airRange.estimate;
     catRank=categoryRank(air,category,marksData.categoryRankRatios);
     sourceLabel=`${shiftInput.value} shift estimate · 2025 curve`
    }
   }else if(imode==='percentile'){
    if(type==='advanced')throw Error('JEE Advanced does not use a percentile input. Choose marks or a known AIR / category rank.');
    percentile=Number($('#jee-percentile').value);
    if(!Number.isFinite(percentile)||percentile<0||percentile>100)throw Error('Enter a percentile from 0 to 100.');
    airRange=projectedAirRange(percentile,1450000,1550000);
    air=airRange.estimate;
    catRank=categoryRank(air,category,marksData.categoryRankRatios);
    sourceLabel='2027 planning estimate - 1.45-1.55M candidates'
   }else{
    const entered=Number($('#jee-rank').value);
    if(!Number.isInteger(entered)||entered<1)throw Error('Enter a positive whole-number rank.');
    if(category==='OPEN'){air=entered;catRank=entered;sourceLabel='known AIR'}
    else{
     catRank=entered;
     if(type==='advanced'){sourceLabel='known JEE Advanced category rank; AIR not inferred'}
     else{const factor=n(data.categoryRankRatios?.[category]??categoryRankFactor[category]??1);air=Math.round(entered/(factor||1));sourceLabel='known category rank; AIR back-calculated with approximate category ratio'}
    }
   }
   state.air=air;state.rank=category==='OPEN'?air:catRank;state.categoryRank=catRank;
   const wants=[...$$('input[name="jee-branch"]:checked')].map(x=>x.value),pwd=$('#jee-pwd').checked,gender=$('#jee-gender').value,specialQuotaState={GO:'Goa',JK:'Jammu and Kashmir',LA:'Ladakh'};
   const rows=data.records.filter(r=>{
    const isIit=r.instituteType==='IIT',rowQuota=String(r.quota||'').toUpperCase();
    if(type==='advanced'?(!isIit||rowQuota!=='AI'):isIit)return false;
    const rowcat=String(r.category||'').toUpperCase();
    if(pwd?!rowcat.includes('PWD'):rowcat.includes('PWD'))return false;
    if(!matchCategory(rowcat,category)||r.gender!==gender)return false;
    if(wants.length&&!wants.includes(r.branch))return false;
    const stateName=r.collegeState||stateFor(r.college);
    if(type==='main'&&rowQuota==='HS'&&(!home||stateName!==home))return false;
    if(type==='main'&&rowQuota==='OS'&&stateName===home&&home)return false;
    if(type==='main'&&['HS','OS'].includes(rowQuota)&&!home&&rowQuota==='HS')return false;
    if(type==='main'&&specialQuotaState[rowQuota]&&home!==specialQuotaState[rowQuota])return false;
    const close=n(r.closingRank);
    if(!close)return false;
    const chance=r.isPreparatory?'Reference only':chanceFor(state.rank,close);
    if(chance==='Outside range')return false;
    r.chance=chance;r._distance=r.isPreparatory?Infinity:Math.abs(state.rank-close);r._id=makeId(prefix,r);r.year=r.year||2025;
    return true
   });
   state.rows=rows.map(r=>attachSearch(r,prefix));state.byId=new Map(state.rows.map(r=>[makeId(prefix,r),r]));
   const result=draw(),airSummary=type==='advanced'?(air===null?'—':rankfmt(air)):(percentile===null?'—':Number(percentile).toFixed(4)),airLabel=type==='advanced'?'EXPECTED AIR':'PERCENTILE',airSub=type==='advanced'?(imode==='air'?sourceLabel:`${sourceLabel} · estimate`):'marks curve is an estimate',airRangeLabel=imode==='air'?(type==='advanced'&&category!=='OPEN'?'Entered category rank':category==='OPEN'?'Entered AIR':'Approx. AIR'):'Estimated AIR range',airRangeValue=airRange?`${rankfmt(airRange.low)}-${rankfmt(airRange.high)}`:rankfmt(imode==='air'&&type==='advanced'&&category!=='OPEN'?catRank:air),categorySub=category==='OPEN'?'same as CRL':type==='advanced'?(imode==='air'?'entered category rank':'estimated from category-rank ratio'):'ratio-based planning estimate';
   $('#jee-stats').innerHTML=[stat(airLabel,airSummary,airSub),stat(airRangeLabel,airRangeValue,airRange?'planning estimate - not official':sourceLabel),stat('Category rank',rankfmt(catRank),categorySub),stat('Eligible colleges',result.eligibleCollegeTotal.toLocaleString(),'within 20% of matched cutoff')].join('');
   twoStep.complete()
  }catch(err){$('#jee-stats').innerHTML='';status($('#jee-result-note'),err.message)}
 })
}

function interpolateAir(score,table){const x=table?.find(r=>r.score===Math.round(score));return x||table?.find(r=>r.score===score)||null}
async function initNeet(){const prefix='neet',form=$('#neet-form');if(!form)return;const state={rows:[],byId:new Map(),rank:null};let data;try{data=await load('neet-cutoffs.json')}catch(e){status($('#neet-result-note'),e.message);return}
 syncNeetChoices(data.records);
 const mode=$('#neet-input-mode'),scoreTable=data.scoreToRank||data.scoreAir;toggleInputs(mode,{'.neet-marks-field':['marks'],'.neet-rank-field':['rank']});const twoStep=setupTwoStep(prefix,form,mode,['rank']);
 form.addEventListener('reset',()=>setTimeout(()=>{mode.dispatchEvent(new Event('change'));$('#neet-search').value='';$('#neet-max-fee').value='';$('#neet-sort').value='rank';$$('#neet-result-panel [data-chance-filter]').forEach(b=>b.classList.toggle('active',b.dataset.chanceFilter==='all'));state.rows=[];state.byId.clear()},0));
 function draw(){const result=renderTable(prefix,state,rows=>renderCollegeCards(prefix,state,rows));status($('#neet-result-note'),`${result.collegeTotal.toLocaleString()} colleges match your planning scenario${result.total>result.shown?` · showing first ${result.shown} options; narrow your search for more`:''}. Projected ranks do not establish admission eligibility.`);return result}
 setupSearchAndFilters(prefix,state,draw);initChoices(prefix,state);
 form.addEventListener('submit',e=>{e.preventDefault();twoStep.reset();const inputMode=mode.value,category=$('#neet-category').value,stateName=$('#neet-state').value,quota=$('#neet-quota').value,course=$('#neet-course').value;let rank=null,score=null,airRange='',rankRange=null;
 if(quota==='SQ'&&!stateName){status($('#neet-result-note'),'Choose your domicile state to see state-quota scenarios.');$('#neet-stats').innerHTML=stat('Domicile needed','Choose a state','State-quota options depend on domicile eligibility.');return}
 if(inputMode==='marks'){score=n($('#neet-score').value);const point=score===null?null:interpolateAir(score,scoreTable);if(!point||point.airEstimate==null){state.rank=null;state.rows=[];state.byId.clear();draw();$('#neet-stats').innerHTML=[stat('Score',score===null?'Enter a score':`${score}/720`),stat('Estimated AIR','Unavailable','enter a supported score or a known AIR'),stat('Category rank','Not inferred','compare AIR only'),stat('Matching colleges','0')].join('');return}const scenarioRank=(baseRank,pool)=>Math.max(1,Math.round(baseRank*pool/NEET_2025_APPEARED));rankRange={low:scenarioRank(point.airLow,2300000),high:scenarioRank(point.airHigh,2500000),estimate:scenarioRank(point.airEstimate,2400000)};rank=rankRange.estimate;airRange='2025 score bands scaled to a 2.3–2.5 million candidate scenario; not official'}else{rank=n($('#neet-rank').value);if(!Number.isInteger(rank)||rank<1){$('#neet-stats').innerHTML=stat('Invalid AIR','Enter a positive whole rank');return}}state.rank=rank;
 const rows=flattenNeetCutoffs(data.records).filter(r=>{if(r.available===false||r.category!==category||r.rankBasis!=='NEET All India Rank'||n(r.closingRank)===null)return false;if(course==='BDS'&&r.course!=='BDS')return false;if((course==='Govt MBBS'||course==='Deemed/Private')&&r.course!=='MBBS')return false;if(course==='Govt MBBS'&&!['Govt MBBS','AIIMS / Central Govt'].includes(r.collegeType))return false;if(course==='Deemed/Private'&&r.collegeType!=='Deemed / Private')return false;if(quota!=='all'&&r.counsellingQuota!==quota)return false;if(r.counsellingQuota==='SQ'&&(!stateName||r.state!==stateName))return false;r.chance=chanceFor(rank,r.closingRank);r._distance=Math.abs(rank-Number(r.closingRank));r._id=makeId(prefix,r);return r.chance!=='Outside range'}).map(r=>attachSearch(r,prefix));state.rows=rows;state.byId=new Map(rows.map(r=>[makeId(prefix,r),r]));const result=draw();$('#neet-stats').innerHTML=[stat('Score',score==null?'Known AIR':`${score}/720`,airRange),stat(inputMode==='marks'?'Estimated AIR range':'Entered AIR',rankRange?`${rankfmt(rankRange.low)}–${rankfmt(rankRange.high)}`:rankfmt(rank),'2027 planning scenarios'),stat('Category rank','Not inferred','AIR is used for all comparisons'),stat('Matching colleges',result.eligibleCollegeTotal.toLocaleString(),'within 20% of the projected closing AIR')].join('');twoStep.complete()});
}

function kcetCategoryMatch(actual,wanted,rural,kannada,exam){const a=String(actual||'').toUpperCase();if(exam==='COMEDK')return wanted==='KKR'?a.includes('KKR'):a==='GM';if(a===wanted)return true;if(wanted==='GM')return(rural&&a==='GMR')||(kannada&&a==='GMK');const stem=wanted.slice(0,-1);if(rural&&a===`${stem}R`)return true;if(kannada&&a===`${stem}K`)return true;return false}
async function initKcet(){const prefix='kcet',form=$('#kcet-form');if(!form)return;const state={rows:[],byId:new Map(),rank:null,score:null};let data;try{data=await load('kcet-cutoffs.json')}catch(e){status($('#kcet-result-note'),e.message);return}
 const mode=$('#kcet-input-mode'),exam=$('#kcet-exam'),category=$('#kcet-category'),twoStep=setupTwoStep(prefix,form,mode,['rank']),hasComedkKkr=data.comedk.some(r=>String(r.category||'').toUpperCase().includes('KKR')),kkrOption=$('#kcet-category option[value="KKR"]'),comedkNote=$('#kcet-comedk-data-note');if(kkrOption)kkrOption.disabled=!hasComedkKkr;function toggle(){const composite=mode.value==='composite'&&exam.value==='KCET';$$('.kcet-composite-field').forEach(x=>x.hidden=!composite);$$('.kcet-rank-field').forEach(x=>x.hidden=mode.value!=='rank'||(exam.value==='COMEDK'&&mode.value!=='rank'));if(comedkNote){comedkNote.hidden=exam.value!=='COMEDK'||hasComedkKkr;if(!comedkNote.hidden)comedkNote.textContent='COMEDK KKR closing-rank data is unavailable; only published GM cutoffs are shown.'}if(exam.value==='COMEDK'&&mode.value==='composite'){mode.value='rank';toggle()}twoStep.reset()}mode.addEventListener('change',toggle);exam.addEventListener('change',()=>{if(exam.value==='COMEDK'&&!hasComedkKkr&&category.value==='KKR')category.value='GM';toggle()});toggle();
 function draw(){const result=renderTable(prefix,state,rows=>renderCollegeCards(prefix,state,rows));status($('#kcet-result-note'),`${result.total.toLocaleString()} matching course rows across ${result.collegeTotal.toLocaleString()} colleges${result.total>result.shown?` - showing first ${result.shown}`:''}. Chances are rank-based heuristics; placement figures come from the supplied college list.`);return result}
 setupSearchAndFilters(prefix,state,draw);initChoices(prefix,state);
 form.addEventListener('submit',e=>{e.preventDefault();twoStep.reset();const examType=exam.value,modeType=mode.value,category=$('#kcet-category').value,board=+$('#kcet-board').value,marks=+$('#kcet-marks').value;let rank,rankRange=null;if(modeType==='rank')rank=+$('#kcet-rank').value;else{if(!Number.isFinite(board)||board<0||board>100||!Number.isFinite(marks)||marks<0||marks>180){status($('#kcet-result-note'),'Enter valid board PCM (0-100%) and KCET marks (0-180).');return}const composite=(board+(marks/180*100))/2;rank=Math.max(1,Math.round(350000*Math.pow(Math.max(0,1-composite/100),2.05)));rankRange={low:Math.max(1,Math.floor(rank*.85)),high:Math.ceil(rank*1.15)};state.score=composite}if(!rank){status($('#kcet-result-note'),'Enter a valid rank or both composite inputs.');return}state.rank=rank;const branches=$$('input[name="kcet-branch"]:checked').map(x=>x.value),rural=$('#kcet-rural').checked,kannada=$('#kcet-kannada').checked,hk=$('#kcet-hk').checked;let sourceRows=examType==='KCET'?data.kea:data.comedk; const rows=sourceRows.filter(r=>{if(examType==='KCET'&&((hk&&r.quota!=='HK')||(!hk&&r.quota==='HK')))return false;if(!kcetCategoryMatch(r.category,category,rural,kannada,examType))return false;if(branches.length&&!branches.includes(r.branch))return false;const close=n(r.closingRank);if(!close)return false;r.exam=examType;r.chance=chanceFor(rank,close);r._distance=Math.abs(rank-close);r.year=r.year||2025;r._id=makeId(prefix,r);return r.chance!=='Outside range'}).map(r=>attachSearch(r,prefix));state.rows=rows;state.byId=new Map(rows.map(r=>[makeId(prefix,r),r]));const result=draw();$('#kcet-stats').innerHTML=[stat('Composite score',modeType==='rank'?'Known rank':`${state.score.toFixed(2)}%`,'50% board PCM + 50% KCET marks'),stat(modeType==='rank'?'Known rank':'Estimated rank range',rankRange?`${rankfmt(rankRange.low)}-${rankfmt(rankRange.high)}`:rankfmt(rank),modeType==='rank'?'known rank':'broad KCET heuristic - approx. 15% planning band'),stat('Category rank',category==='GM'?rankfmt(rank):'Estimate only',category==='GM'?'GM rank basis':'category cutoffs remain source ranks'),stat('Eligible colleges',result.eligibleCollegeTotal.toLocaleString(),'within 20% of matched closing rank')].join('');twoStep.complete()});
}

document.addEventListener('DOMContentLoaded',()=>{const kind=$('.predictor')?.dataset.predictor;if(!kind)return;const run={jee:initJee,neet:initNeet,kcet:initKcet}[kind];run?.().catch(e=>{const note=$(`#${kind}-result-note`);status(note,e.message)})});
})();
