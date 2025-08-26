async function loadCards(){
  try{
    const data = await jfetch('/api/my-cards');
    const tb = document.querySelector('#cards-table tbody');
    if(!tb) return;
    tb.innerHTML = '';
    for(const c of data.cards){
      const tr = document.createElement('tr');
      const exp = `${String(c.exp_month).padStart(2,'0')}/${String(c.exp_year).slice(-2)}`;
      tr.innerHTML = `<td>${c.pan}</td><td>${c.cardholder_name||''}</td><td>${exp}</td><td>${c.status}</td>`;
      tb.appendChild(tr);
    }
  }catch(e){ console.error(e); }
}

async function issueCard(){
  try{
    const cardholder_name = document.getElementById('cardholder-name').value.trim();
    const out = await jfetch('/api/card', {method:'POST', body: JSON.stringify({cardholder_name})});
    showToast('success', 'Card issued', `${cardholder_name ? cardholder_name + ' – ' : ''}Card **** **** **** ${String(out.pan).slice(-4)} (CVV ${out.cvv})`);
    await loadCards();
  }catch(e){ showToast('error', 'Error', e.message); }
}
document.addEventListener('DOMContentLoaded', async ()=>{
  document.getElementById('btn-card').onclick = issueCard;
  await loadCards();
});
