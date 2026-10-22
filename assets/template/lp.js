(function(){
  'use strict';
  /* クライアント固有の値は build_lp.py が lp.json から差し込む（ここは書き換えない） */
  /*CFG*/
  window.dataLayer = window.dataLayer || [];
  const push = o => window.dataLayer.push(o);
  const $ = id => document.getElementById(id);
  const smooth = () => matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
  const toForm = () => $('form').scrollIntoView({behavior:smooth(), block:'start'});
  document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => { push({event:'cta_click', cta_from: b.closest('[id]')?.id || ''}); toForm(); }));

  /* 計測：どの章まで読んだか（manga_reach） */
  if('IntersectionObserver' in window){
    const seen = new Set();
    const io = new IntersectionObserver(es => es.forEach(e => {
      const k = e.target.dataset.ch;
      if(e.isIntersecting && !seen.has(k)){ seen.add(k); push({event:'manga_reach', manga_ch:k}); }
    }), {threshold:.3});
    document.querySelectorAll('[data-ch]').forEach(el => io.observe(el));
  }

  /* 追従CTA：フォームが見えている間は隠す */
  const st = $('sticky');
  if(st && 'IntersectionObserver' in window){
    const vis = new Map();
    const io2 = new IntersectionObserver(es => {
      es.forEach(e => vis.set(e.target.id, e.isIntersecting));
      const on = ![...vis.values()].some(Boolean);
      st.classList.toggle('off', !on); st.querySelector('button').tabIndex = on ? 0 : -1;
    });
    io2.observe($('form'));
  }

  /* タブ */
  document.querySelectorAll('[data-tabs]').forEach(t => {
    const btns = [...t.querySelectorAll('[role=tab]')];
    btns.forEach(b => b.addEventListener('click', () => btns.forEach(x => {
      const on = x === b; x.setAttribute('aria-selected', on); $(x.getAttribute('aria-controls')).hidden = !on;
    })));
  });

  /* FAQ */
  const fq = $('faq');
  if(fq) CFG.faq.forEach(([q,a]) => {
    const d = document.createElement('details'); d.className = 'acc';
    const s = document.createElement('summary'); s.textContent = 'Q. ' + q;
    const p = document.createElement('div'); p.className = 'in';
    p.textContent = 'A. ' + a;
    d.append(s, p); fq.append(d);
  });

  /* ===== シミュレーション＋フォーム =====
     STEPS の最後は連絡先。1問目だけ漫画の途中（#simQ1）にも置き、選ぶとフォームへ移って2問目から続ける。
     選択肢に持たせる値：save/year（サンクスの想定額）・bill・intent（スコア）・qualify（対象者）・key（PLANの見出し） */
  const STEPS = CFG.steps.concat([{contact:true, q:CFG.contactTitle}]);
  const PREFS = CFG.prefs;
  const NQ = STEPS.length - 1;
  const PLAN = CFG.plan;

  const ans = {}; let cur = 0, fromSim = false;
  const LOADED = Date.now();
  const area = $('stepArea'), bar = $('progBar'), lab = $('stepLab');
  const el = (t,c,txt) => { const e = document.createElement(t); if(c) e.className = c; if(txt != null) e.textContent = txt; return e; };
  const optBtn = (o, on, fn) => {
    const b = el('button','opt'); b.type = 'button';
    b.append(el('span','emo',o.emoji), el('span','',o.t));
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.addEventListener('click', fn); return b;
  };
  const backBtn = () => { const b = el('button','back','戻る'); b.type = 'button'; b.addEventListener('click', () => { cur--; render(); }); return b; };
  const answer = (i, o) => {
    ans[i] = o;
    push({event:'diag_answer', question:i+1, question_text:STEPS[i].q, answer:o.t});
    cur = i + 1; render();
  };

  const simQ1 = $('simQ1');
  if(simQ1) STEPS[0].options.forEach(o => simQ1.append(optBtn(o, false, () => {
    if(!fromSim) push({event:'sim_start'});
    fromSim = true;
    [...simQ1.children].forEach(b => b.setAttribute('aria-pressed', b.textContent.endsWith(o.t) ? 'true' : 'false'));
    answer(0, o);
    push({event:'sim_to_form'});
    setTimeout(toForm, 200);
  })));

  function render(){
    area.replaceChildren();
    const s = STEPS[cur];
    bar.style.width = (cur/STEPS.length*100 + 100/STEPS.length) + '%';
    lab.textContent = s.contact ? '最後に、ご連絡先' : ('Q' + (cur+1) + ' / ' + NQ + (s.qualifier ? '（対象確認）' : ''));
    area.append(el('p','hd sm',s.q));
    if(s.note) area.append(el('p','q-note',s.note));
    if(!s.contact){
      const box = el('div','opts cards');
      s.options.forEach(o => box.append(optBtn(o, ans[cur] === o, () => answer(cur, o))));
      area.append(box);
      if(cur > 0) area.append(backBtn());
      if(cur === 0) push({event:'diag_start', step:1});
    }else{
      push({event:'form_view'});
      const n1 = el('label','field'); n1.htmlFor = 'in-name'; n1.append('お名前');
      const ni = document.createElement('input'); ni.type = 'text'; ni.id = 'in-name'; ni.autocomplete = 'name'; ni.placeholder = '山田 太郎'; n1.append(ni);
      const p1 = el('label','field'); p1.htmlFor = 'in-pref'; p1.append('都道府県');
      const ps = document.createElement('select'); ps.id = 'in-pref'; ps.autocomplete = 'address-level1';
      const o0 = el('option','','選択してください'); o0.value = ''; ps.append(o0);
      PREFS.forEach(v => { const op = el('option','',v); op.value = v; ps.append(op); });
      p1.append(ps);
      const t1 = el('label','field'); t1.htmlFor = 'in-tel'; t1.append('電話番号');
      const ti = document.createElement('input'); ti.id = 'in-tel'; ti.type = 'tel'; ti.autocomplete = 'tel'; ti.inputMode = 'numeric'; ti.placeholder = '090-1234-5678'; t1.append(ti);
      const err = el('p','err'); err.setAttribute('role','alert');
      const sb = el('button','btn',CFG.submitLabel); sb.type = 'submit';
      const pv = el('p','fine'); pv.style.textAlign = 'center';
      pv.append('送信により');
      const a = el('a','','プライバシーポリシー'); a.href = 'privacy-policy.html'; a.target = '_blank'; a.rel = 'noopener'; pv.append(a, 'に同意したものとみなします。ご入力情報はご案内以外に使用しません。');
      area.append(n1, p1, t1, err, sb, pv, backBtn());
    }
  }

  /* 送信：本番ドメイン以外（localhost・確認用URL）では送信しない。テストのリードが入らないように */
  const IS_LOCAL = !new RegExp(CFG.prodHostRe).test(location.hostname);

  $('dxForm').addEventListener('submit', e => {
    e.preventDefault();
    const ni = $('in-name'), ps = $('in-pref'), ti = $('in-tel'), err = area.querySelector('[role=alert]');
    if(!ni) return;
    const tel = (ti.value || '').replace(/\s/g,'');
    if(!ni.value.trim()){ err.textContent = 'お名前を入力してください'; ni.focus(); return; }
    if(!ps.value){ err.textContent = '都道府県を選んでください'; ps.focus(); return; }
    if(!/^[0-9\-]{10,13}$/.test(tel)){ err.textContent = '正しい電話番号を入力してください'; ti.focus(); return; }

    const q = i => ans[i] || {};
    const pick = f => { for(let i = 0; i < NQ; i++){ if(q(i)[f] != null) return q(i)[f]; } return null; };
    const isTarget = STEPS.some(s => s.qualifier) ? !!pick('qualify') : true;
    const bill = pick('bill') || 0, intent = pick('intent') || 0, save = pick('save') || 0, year = pick('year') || 0;
    const key = pick('key');
    const score = intent + bill;
    const payload = {
      form: CFG.formId,
      title: CFG.payloadTitle,
      qa: STEPS.filter(s => !s.contact).map((s,i) => ({q:s.q, a:ans[i] ? ans[i].t : '(未回答)'})),
      contact: {name: ni.value.trim(), pref: ps.value, tel: tel},
      thanksAlt: save ? ('削減' + save + '円') : '',
      isTarget: isTarget,
      interest: key || '',
      bill: bill,
      intent: intent,
      score: score,
      hp: $('in-website').value,
      elapsed: Math.round((Date.now() - LOADED)/1000)
    };
    const k2 = key || CFG.planDefault;
    const keyStep = STEPS.findIndex((s,i) => !s.contact && q(i).key != null);
    sessionStorage.setItem('diagResult', JSON.stringify({
      isTarget, q1text:q(0).t || '', save, year,
      q3text: keyStep >= 0 ? q(keyStep).t : '', q4text: q(NQ-1).t || '', interest:k2, plan:PLAN[k2] || null
    }));
    push({event:'diag_complete', is_target:isTarget, score:score, sim_used:fromSim});
    push({event:'form_submit', is_target:isTarget, score:score});

    if(IS_LOCAL || CFG.preview){
      console.log('▼ 送信データ（本番ドメイン以外のため未送信）', payload);
      location.href = 'thanks.html';
      return;
    }
    const sb = area.querySelector('button[type=submit]');
    if(sb){ sb.disabled = true; sb.textContent = '送信中…'; }
    const toMail = CFG.mailEndpoint ? fetch(CFG.mailEndpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).catch(() => {}) : Promise.resolve();
    const toSheet = CFG.gasUrl ? fetch(CFG.gasUrl, {method:'POST', mode:'no-cors', body:JSON.stringify(payload)}).catch(() => {}) : Promise.resolve();
    Promise.all([toMail, toSheet]).finally(() => { location.href = 'thanks.html'; });
  });

  render();
})();
