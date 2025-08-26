async function doLogin(){
  try{
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const out = await jfetch('/api/login', {method:'POST', body: JSON.stringify({email, password})});
    showToast('success', 'Logged in', `${out.name} <${out.email}>`);
    setTimeout(()=> location.href = '/', 600);
  }catch(e){ showToast('error', 'Login failed', e.message); }
}
document.addEventListener('DOMContentLoaded', ()=>{
  document.getElementById('btn-login').onclick = doLogin;
});
