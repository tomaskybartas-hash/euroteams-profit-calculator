import http from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createAuth} from './auth.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const origin=process.env.PUBLIC_ORIGIN;
if(!origin||new URL(origin).origin!==origin||(!origin.startsWith('https://')&&process.env.NODE_ENV!=='test'))throw Error('Set PUBLIC_ORIGIN to the canonical HTTPS origin');
const dbPath=process.env.AUTH_DB_PATH;if(!dbPath)throw Error('Set AUTH_DB_PATH on persistent storage');
await mkdir(dirname(dbPath),{recursive:true,mode:0o700});
const auth=createAuth(dbPath),owner='tomas_kybartas@yahoo.com';
const assets=new Map(['app.js','app-core.js','full-language.js','payroll-controls.js','tax-rules-2026.js','canonical-results.js','safe-storage.js','styles.css','final-audit.css','logo.svg','auth-client.js'].map(f=>['/'+f,f]));
const publicAssets=new Set(['/styles.css','/logo.svg','/auth-client.js']);
const mime=f=>f.endsWith('.css')?'text/css':f.endsWith('.svg')?'image/svg+xml':f.endsWith('.js')?'text/javascript':'text/html';
const cookie=(token,clear=false)=>`et_session=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${clear?0:86400}${process.env.NODE_ENV==='test'?'':'; Secure'}`;
function send(res,status,data){res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data))}
async function body(req){let text='';for await(const part of req){text+=part;if(Buffer.byteLength(text)>4096)throw Error('BODY')}return JSON.parse(text||'{}')}
const server=http.createServer(async(req,res)=>{
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('X-Frame-Options','DENY');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
 try{
 const url=new URL(req.url,origin),path=url.pathname;const token=(req.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith('et_session='))?.slice(11);const role=auth.session(token);
 if(path==='/health'){send(res,200,{ok:true});return}
 if(path.startsWith('/api/')){
  if(req.method==='GET'&&path==='/api/session'){send(res,role?200:401,{role});return}
  if(req.method!=='POST'){send(res,405,{error:'METHOD'});return}
  if(req.headers.origin!==origin||!req.headers['content-type']?.startsWith('application/json')){send(res,403,{error:'ORIGIN'});return}
  // Use the final address appended by the trusted Render edge; global limits also bound distributed attempts.
  const ip=(req.headers['x-forwarded-for']||req.socket.remoteAddress||'unknown').split(',').at(-1).trim();
  if(auth.limited('request:'+ip,120,60000)){send(res,429,{error:'RATE_LIMIT'});return}
  const data=await body(req);
  if(path==='/api/login'){
   if(auth.limited('login:'+ip,10,900000)||auth.limited('login:global',100,900000)){send(res,429,{error:'RATE_LIMIT'});return}
   const session=auth.login(data.role,data.password);if(!session){send(res,401,{error:'LOGIN'});return}res.setHeader('Set-Cookie',cookie(session));send(res,200,{role:data.role});return;
  }
  if(path==='/api/recovery'){
   if(!process.env.RESEND_API_KEY||!process.env.MAIL_FROM){send(res,503,{error:'MAIL_NOT_CONFIGURED'});return}
   if(auth.limited('mail:global',3,3600000)){send(res,429,{error:'RATE_LIMIT'});return}
   const reset=auth.resetToken();const link=origin+'/#reset='+reset;
   try{const result=await fetch('https://api.resend.com/emails',{method:'POST',headers:{Authorization:'Bearer '+process.env.RESEND_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({from:process.env.MAIL_FROM,to:[owner],subject:'Euroteams – administratoriaus slaptažodžio atkūrimas',text:'Atidarykite vienkartinę nuorodą (galioja 15 min.):\n'+link+'\nJei atkūrimo neprašėte, šį laišką ignoruokite.'}),signal:AbortSignal.timeout(15000)});if(!result.ok)throw Error('MAIL');send(res,200,{ok:true})}catch{auth.cancelReset(reset);send(res,503,{error:'MAIL_FAILED'})}return;
  }
  if(path==='/api/reset'){if(auth.limited('reset:'+ip,10,900000)){send(res,429,{error:'RATE_LIMIT'});return}const ok=typeof data.token==='string'&&auth.resetAdmin(data.token,data.password);send(res,ok?200:400,ok?{ok:true}:{error:'RESET'});return}
  if(path==='/api/logout'){auth.logout(token);res.setHeader('Set-Cookie',cookie('',true));send(res,200,{ok:true});return}
  if(role!=='admin'){send(res,403,{error:'ADMIN'});return}
  if(path==='/api/admin/team-password'){auth.changeTeam(data.password);send(res,200,{ok:true});return}
  if(path==='/api/admin/revoke'){auth.revokeTeam();send(res,200,{ok:true});return}
  if(path==='/api/admin/password'){if(auth.limited('admin-password:'+ip,5,900000)){send(res,429,{error:'RATE_LIMIT'});return}const ok=typeof data.current==='string'&&auth.changeAdmin(token,data.current,data.password);if(ok)res.setHeader('Set-Cookie',cookie('',true));send(res,ok?200:400,ok?{ok:true}:{error:'LOGIN'});return}
  send(res,404,{error:'NOT_FOUND'});return;
 }
 if(req.method!=='GET'&&req.method!=='HEAD'){send(res,405,{error:'METHOD'});return}
 if(path==='/'){
  let html=await readFile(resolve(root,'index.html'),'utf8');html=html.replace(/<script src="app.js[^>]*><\/script>/,'<script src="auth-client.js"></script>');res.setHeader('Content-Type','text/html');res.end(html);return;
 }
 const file=assets.get(path);if(!file){send(res,404,{error:'NOT_FOUND'});return}if(!publicAssets.has(path)&&!role){send(res,401,{error:'LOGIN_REQUIRED'});return}
 res.setHeader('Content-Type',mime(file));res.end(await readFile(resolve(root,file)));
 }catch(error){send(res,error.message==='PASSWORD_LENGTH'?400:500,{error:error.message==='PASSWORD_LENGTH'?'PASSWORD_LENGTH':'REQUEST_FAILED'})}
});
server.listen(Number(process.env.PORT||10000),'0.0.0.0');
