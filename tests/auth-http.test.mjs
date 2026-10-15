import {test} from 'node:test';import assert from 'node:assert/strict';import {spawn} from 'node:child_process';import {mkdtempSync,rmSync} from 'node:fs';import {tmpdir} from 'node:os';import {join} from 'node:path';import {createAuth} from '../server/auth.mjs';
test('HTTP authentication gates scripts, isolates admin privileges, rejects CSRF and revokes sessions',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'et-http-')),db=join(dir,'auth.sqlite');const auth=createAuth(db);auth.resetAdmin(auth.resetToken(),'owner-test-password-123');auth.changeTeam('team-test-password-123');auth.close();
 const origin='http://127.0.0.1:18743';const child=spawn(process.execPath,['server/server.mjs'],{env:{...process.env,NODE_ENV:'test',PORT:'18743',PUBLIC_ORIGIN:origin,AUTH_DB_PATH:db},stdio:['ignore','ignore','pipe']});
 const req=(path,{cookie,body,foreign=false}={})=>fetch(origin+path,{method:body?'POST':'GET',headers:{...(cookie?{Cookie:cookie}:{}),...(body?{'Content-Type':'application/json',Origin:foreign?'https://untrusted.example':origin}:{})},body:body?JSON.stringify(body):undefined});
 try{
 for(let i=0;i<50;i++){try{await req('/health');break}catch{await new Promise(r=>setTimeout(r,20))}}
 assert.equal((await req('/app-core.js')).status,401);assert.equal((await req('/server/auth.mjs')).status,404);const html=await(await req('/')).text();assert.ok(html.includes('auth-client.js'));assert.ok(!html.includes('<script src="app.js'));
 assert.equal((await req('/api/login',{body:{role:'team',password:'team-test-password-123'},foreign:true})).status,403);
 const teamLogin=await req('/api/login',{body:{role:'team',password:'team-test-password-123'}});assert.equal(teamLogin.status,200);const teamCookie=teamLogin.headers.get('set-cookie').split(';')[0];assert.ok(teamLogin.headers.get('set-cookie').includes('HttpOnly'));assert.equal((await req('/app-core.js',{cookie:teamCookie})).status,200);
 assert.equal((await req('/api/admin/team-password',{cookie:teamCookie,body:{password:'unwanted-test-password'}})).status,403);
 const ownerLogin=await req('/api/login',{body:{role:'admin',password:'owner-test-password-123'}});const ownerCookie=ownerLogin.headers.get('set-cookie').split(';')[0];assert.equal(ownerLogin.status,200);
 assert.equal((await req('/api/admin/team-password',{cookie:ownerCookie,body:{password:'changed-test-password-123'}})).status,200);assert.equal((await req('/api/session',{cookie:teamCookie})).status,401);assert.equal((await req('/app-core.js',{cookie:teamCookie})).status,401);assert.equal((await req('/api/session',{cookie:ownerCookie})).status,200);
 assert.equal((await req('/api/login',{body:{role:'team',password:'team-test-password-123'}})).status,401);assert.equal((await req('/api/login',{body:{role:'team',password:'changed-test-password-123'}})).status,200);
 assert.equal((await req('/api/recovery',{body:{}})).status,503);assert.equal((await req('/api/logout',{cookie:ownerCookie,body:{}})).status,200);assert.equal((await req('/api/session',{cookie:ownerCookie})).status,401);
 }finally{child.kill();await new Promise(r=>child.once('exit',r));rmSync(dir,{recursive:true,force:true})}
});
