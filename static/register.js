async function doRegister(){
  try{
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();
    const out = await jfetch('/api/register', {method:'POST', body: JSON.stringify({name, email, password})});
    showToast('success', 'Account created', `${out.name} <${out.email}> — Account ID ${out.account_id}`);
    setTimeout(()=> location.href = '/', 600);
  }catch(e){ showToast('error', 'Error', e.message); }
}
document.addEventListener('DOMContentLoaded', ()=>{
  document.getElementById('btn-register').onclick = doRegister;
});
