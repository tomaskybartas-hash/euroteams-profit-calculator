import {DatabaseSync} from 'node:sqlite';
import {randomBytes,createHash,scryptSync,timingSafeEqual} from 'node:crypto';
export const digest=v=>createHash('sha256').update(v).digest('hex');
export const hashPassword=value=>{const salt=randomBytes(16).toString('hex');return salt+':'+scryptSync(value,salt,64).toString('hex')};
const verify=(value,hash)=>{if(!hash)return false;const [salt,key]=hash.split(':');return timingSafeEqual(scryptSync(value,salt,64),Buffer.from(key,'hex'))};
export function createAuth(file,{now=Date.now}={}){
 const db=new DatabaseSync(file);db.exec(`PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,role TEXT NOT NULL,expires INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS resets(hash TEXT PRIMARY KEY,expires INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);`);
 const get=k=>db.prepare('SELECT value FROM settings WHERE key=?').get(k)?.value;
 const set=(k,v)=>db.prepare('INSERT OR REPLACE INTO settings VALUES(?,?)').run(k,v);
 function transaction(fn){db.exec('BEGIN IMMEDIATE');try{const r=fn();db.exec('COMMIT');return r}catch(e){db.exec('ROLLBACK');throw e}}
 function password(value){if(typeof value!=='string'||value.length<12||value.length>256)throw new Error('PASSWORD_LENGTH')}
 return {
  close:()=>db.close(),
  limited(key,max,period){db.prepare('DELETE FROM limits WHERE expires<=?').run(now());const row=db.prepare('SELECT * FROM limits WHERE key=?').get(key);if(!row||row.expires<=now()){db.prepare('INSERT OR REPLACE INTO limits VALUES(?,1,?)').run(key,now()+period);return false}if(row.count>=max)return true;db.prepare('UPDATE limits SET count=count+1 WHERE key=?').run(key);return false},
  login(role,value){if(!['admin','team'].includes(role)||typeof value!=='string'||value.length>256)return null;const hash=get(role);if(!hash){scryptSync(value,'dummy-verification',64);return null}if(!verify(value,hash))return null;const token=randomBytes(32).toString('hex');db.prepare('DELETE FROM sessions WHERE expires<=?').run(now());db.prepare('INSERT INTO sessions VALUES(?,?,?)').run(digest(token),role,now()+86400000);return token},
  session(token){if(!token)return null;return db.prepare('SELECT role FROM sessions WHERE hash=? AND expires>?').get(digest(token),now())?.role||null},
  logout(token){if(token)db.prepare('DELETE FROM sessions WHERE hash=?').run(digest(token))},
  changeTeam(value){password(value);const hash=hashPassword(value);transaction(()=>{set('team',hash);db.prepare("DELETE FROM sessions WHERE role='team'").run()})},
  revokeTeam(){db.prepare("DELETE FROM sessions WHERE role='team'").run()},
  resetToken(){const token=randomBytes(32).toString('hex');db.prepare('DELETE FROM resets WHERE expires<=?').run(now());db.prepare('INSERT INTO resets VALUES(?,?)').run(digest(token),now()+900000);return token},
  cancelReset(token){db.prepare('DELETE FROM resets WHERE hash=?').run(digest(token))},
  resetAdmin(token,value){password(value);const hash=hashPassword(value);return transaction(()=>{const row=db.prepare('SELECT * FROM resets WHERE hash=? AND expires>?').get(digest(token),now());if(!row)return false;set('admin',hash);db.prepare('DELETE FROM resets').run();db.prepare("DELETE FROM sessions WHERE role='admin'").run();return true})},
  changeAdmin(token,current,value){password(value);if(this.session(token)!=='admin'||!verify(current,get('admin')))return false;const hash=hashPassword(value);transaction(()=>{set('admin',hash);db.prepare("DELETE FROM sessions WHERE role='admin'").run();db.prepare('DELETE FROM resets').run()});return true}
 };
}
