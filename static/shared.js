async function jfetch(url, opts={}){
  const res = await fetch(url, Object.assign({headers: {"Content-Type":"application/json"}}, opts));
  if(!res.ok){
    let txt = await res.text();
    throw new Error(`HTTP ${res.status}: ${txt}`);
  }
  return res.json();
}
function ensureToastContainer(){
  let c = document.querySelector('.toast-container');
  if(!c){
    c = document.createElement('div');
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  return c;
}
function showToast(type, title, message, timeoutMs=3500){
  const c = ensureToastContainer();
  c.querySelectorAll('.toast').forEach(n => n.remove());
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const close = document.createElement('button');
  close.className = 'close';
  close.textContent = '×';
  close.onclick = ()=> t.remove();
  const ttl = document.createElement('div');
  ttl.className = 'title';
  ttl.textContent = title || (type === 'success' ? 'Success' : 'Error');
  const msg = document.createElement('div');
  msg.textContent = message || '';
  t.appendChild(close);
  t.appendChild(ttl);
  t.appendChild(msg);
  c.appendChild(t);
  requestAnimationFrame(()=> t.classList.add('show'));
  if(timeoutMs){
    setTimeout(()=>{
      t.classList.remove('show');
      setTimeout(()=> t.remove(), 200);
    }, timeoutMs);
  }
}
