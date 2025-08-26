
let eligibleItemsCache = [];

function recalcTotal(){
  const container = document.getElementById('items');
  const rows = container ? container.querySelectorAll('.item-row') : [];
  let total = 0;
  rows.forEach(r => {
    const codeSel = r.querySelector('select[name="item-code"]');
    const amtInput = r.querySelector('input[name="item-amount"]');
    const val = parseFloat(amtInput?.value || '0');

    // Find eligibility from our cached item list
    const itemMeta = eligibleItemsCache.find(x => x.code === codeSel.value);
    const eligible = itemMeta ? itemMeta.eligible : false;

    if(eligible && !isNaN(val)) {
      total += val;
    }
  });

  const totalEl = document.getElementById('amount');
  if(totalEl) totalEl.value = total.toFixed(2);

  const btn = document.getElementById('btn-purchase');
  if(btn) btn.disabled = (total <= 0);

  // auto-clear error toast when valid
  if(total > 0){
    const c = document.querySelector('.toast-container');
    if(c){ c.querySelectorAll('.toast.error').forEach(n => n.remove()); }
  }
}


function createItemRow(defaultCode="RX_PRESCRIPTION"){
  const row = document.createElement('div');
  row.className = 'item-row';

  const nameIn = document.createElement('input');
  nameIn.name = 'item-name';
  nameIn.placeholder = 'Item name (e.g., Bandages)';
  nameIn.value = eligibleItemsCache.find(x => x.code === defaultCode)?.name || "";

  const codeSel = document.createElement('select');
  codeSel.name = 'item-code';
  for(const it of eligibleItemsCache){
    const opt = document.createElement('option');
    opt.value = it.code;
    opt.textContent = `${it.code} (${it.eligible ? "eligible" : "ineligible"})`;
    if(it.code === defaultCode) opt.selected = true;
    codeSel.appendChild(opt);
  }

  const amtIn = document.createElement('input');
  amtIn.name = 'item-amount';
  amtIn.placeholder = 'Amount (USD)';
  amtIn.inputMode = 'decimal';
  amtIn.addEventListener('input', recalcTotal);

  const removeBtn = document.createElement('button');
  removeBtn.textContent = 'Remove';
  removeBtn.type = 'button';
  removeBtn.onclick = () => { row.remove(); recalcTotal(); };

  row.appendChild(nameIn);
  row.appendChild(codeSel);
  row.appendChild(amtIn);
  row.appendChild(removeBtn);
  return row;
}

function getItemsPayload(){
  const container = document.getElementById('items');
  const rows = container ? container.querySelectorAll('.item-row') : [];
  const items = [];
  rows.forEach(r => {
    const nameInput = r.querySelector('input[name="item-name"]');
    const codeSel = r.querySelector('select[name="item-code"]');
    const amtInput = r.querySelector('input[name="item-amount"]');
    const amount = parseFloat(amtInput?.value || '0');
    items.push({
      name: (nameInput?.value || "Item"),
      code: (codeSel?.value || "UNKNOWN"),
      amount_dollars: isNaN(amount) ? 0 : amount
    });
  });
  return items;
}

async function loadMCCs(){
  try{
    const data = await jfetch('/api/mccs');
    const sel = document.getElementById('mcc');
    if(!sel) return;
    sel.innerHTML = "";
    (data.eligible_mccs || []).forEach(row => {
      const opt = document.createElement('option');
      opt.value = row.mcc;
      opt.textContent = `${row.mcc} — ${row.label}`;
      sel.appendChild(opt);
    });
  }catch(e){ console.error(e); }
}

async function loadItems(){
  try{
    const data = await jfetch('/api/items');
    eligibleItemsCache = data.items || [];
  }catch(e){ console.error(e); }
}

async function loadMyCards(){
  try{
    const data = await jfetch('/api/my-cards');
    const sel = document.getElementById('tx-card-select');
    if(!sel) return;
    sel.innerHTML = '';
    const cards = data.cards || [];
    if(cards.length === 0){
      const opt = document.createElement('option');
      opt.textContent = 'No cards yet — issue one first';
      opt.value = '';
      sel.appendChild(opt);
      sel.disabled = true;
      const btn = document.getElementById('btn-purchase');
      if(btn) btn.disabled = true;
      return;
    }
    for(const c of cards){
      const opt = document.createElement('option');
      const exp = `${String(c.exp_month).padStart(2,'0')}/${String(c.exp_year).slice(-2)}`;
      opt.value = String(c.pan).replace(/\s+/g,'');
      opt.textContent = `${c.pan} — ${c.cardholder_name || 'Cardholder'} — ${exp}`;
      sel.appendChild(opt);
    }
    sel.disabled = false;
    const btn = document.getElementById('btn-purchase');
    if(btn) btn.disabled = false;
  }catch(e){ console.error(e); }
}

async function submitPurchase(){
  try{
    const total = parseFloat(document.getElementById('amount').value) || 0;
    const card_pan = document.getElementById('tx-card-select').value;
    const merchant = document.getElementById('merchant').value.trim();
    const mcc = document.getElementById('mcc').value;
    if(!card_pan){ showToast('error','Missing card','Please select a card'); return; }
    if(!merchant){ showToast('error','Missing merchant','Please enter a merchant'); return; }
    if(!mcc){ showToast('error','Missing MCC','Please choose an MCC'); return; }
    if(total <= 0){ showToast('error','Invalid total','Total must be greater than $0'); return; }

    const items = getItemsPayload();
    const out = await jfetch('/api/transaction', {
      method:'POST',
      body: JSON.stringify({card_pan, merchant, mcc, amount_dollars: total, items})
    });
    if(out.approved){
      showToast('success', 'Purchase approved', `New balance: $${out.new_balance_dollars}`);
    }else{
      showToast('error', 'Declined', out.reason || 'Declined');
    }
  }catch(e){ showToast('error', 'Error', e.message); }
}

document.addEventListener('DOMContentLoaded', async ()=>{
  await loadItems();
  await loadMCCs();
  await loadMyCards();
  const itemsDiv = document.getElementById('items');
  itemsDiv.appendChild(createItemRow());
  recalcTotal();
  document.getElementById('btn-add-item').onclick = ()=>{
    itemsDiv.appendChild(createItemRow());
  };
  document.getElementById('btn-purchase').onclick = submitPurchase;
});
