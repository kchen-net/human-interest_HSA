async function refreshBalance(){
  try{
    const me = await jfetch('/api/me');
    const el = document.getElementById('current-balance');
    if(el) el.textContent = (me.balance_dollars ?? 0).toFixed(2);
    return me;
  }catch(e){ console.error(e); }
}
async function doDeposit(){
  try{
    const me = await refreshBalance();
    const account_id = me.account_id;
    const amount_dollars = parseFloat(document.getElementById('deposit-amount').value);
    const out = await jfetch('/api/deposit', {method:'POST', body: JSON.stringify({account_id, amount_dollars})});
    showToast('success', 'Deposit successful', `New balance: $${out.balance_dollars}`);
    const el = document.getElementById('current-balance');
    if(el) el.textContent = (out.balance_dollars ?? 0).toFixed(2);
  }catch(e){ showToast('error', 'Error', e.message); }
}
document.addEventListener('DOMContentLoaded', ()=>{
  document.getElementById('btn-deposit').onclick = doDeposit;
});

window.addEventListener('pageshow', ()=>{ refreshBalance(); });
