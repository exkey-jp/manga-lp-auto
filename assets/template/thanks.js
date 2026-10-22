(function(){
  /* クライアント固有の値は build_lp.py が lp.json の thanks から差し込む */
  /*CFG*/
  window.dataLayer = window.dataLayer || [];
  let d = null;
  try { d = JSON.parse(sessionStorage.getItem('diagResult') || 'null'); } catch(e){}
  // 確認用：?demo=1 でサンプル表示
  if(!d && new URLSearchParams(location.search).has('demo')) d = T.demo;
  const out = document.getElementById('out');
  const el = (t,c,txt) => { const e = document.createElement(t); if(c) e.className = c; if(txt != null) e.textContent = txt; return e; };
  if(!d || (T.amount && !d.save)){
    out.append(el('h1','','診断結果が見つかりませんでした'), el('p','lead','お手数ですが、もう一度シミュレーションからお試しください。'));
    const a = el('a','btn','シミュレーションをやり直す'); a.href = 'index.html#sim'; out.append(a);
    return;
  }
  window.dataLayer.push({event:'form_complete', lp:T.lpName, is_target:d.isTarget});
  const yen = n => (n || 0).toLocaleString('ja-JP');

  out.append(el('h1','',T.h1), el('p','lead',T.lead));

  if(T.amount){
    const box = el('div','box');
    box.append(el('span','lb',T.amount.label));
    const amt = el('p','amt'); amt.style.margin = '0';
    amt.append(T.amount.pre, el('b','',yen(d.save)), T.amount.post);
    const yr = el('p','yr'); yr.style.margin = '0';
    yr.append(T.amount.yearPre, el('b','','約' + yen(d.year) + '円'), T.amount.yearPost);
    box.append(amt, yr);
    out.append(box);
    out.append(el('p','fine',T.amount.fine.replace('{q1}', d.q1text)));
  }

  if(!d.isTarget && T.notTarget){
    const n = el('div','notarget');
    n.append(T.notTarget[0], el('b','',T.notTarget[1]), T.notTarget[2]);
    out.append(n);
  }

  if(T.pairImg){
    const pair = el('div','pair');
    const img = el('img'); img.src = T.pairImg; img.alt = ''; img.width = 800; img.height = 800;
    pair.append(img, el('p','',T.pairText));
    out.append(pair);
  }

  if(T.phone) out.append(el('div','phone',T.phone));

  if(d.plan){
    const pl = el('div','plan');
    pl.append(el('h2','',T.planPrefix + d.plan.h));
    const ul = el('ul'); d.plan.items.forEach(t => ul.append(el('li','',t)));
    pl.append(ul); out.append(pl);
  }

  const st = el('div','steps');
  T.flow.forEach(t => st.append(el('div','',t)));
  out.append(el('p','lead','このあとの流れ'), st);
  if(T.closing) out.append(el('p','fine',T.closing));

  const tr = el('div','trust'); T.trust.forEach(t => tr.append(el('span','',t)));
  out.append(tr);
})();
