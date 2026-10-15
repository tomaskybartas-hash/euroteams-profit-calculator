import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createAuth} from '../server/auth.mjs';
test('Owner bootstrap, reset expiration/single use, shared-password revocation and persistent sessions',()=>{
 const dir=mkdtempSync(join(tmpdir(),'euroteams-auth-'));let clock=1000000;let auth=createAuth(join(dir,'auth.sqlite'),{now:()=>clock});
 try{
 assert.equal(auth.login('admin','invalid'),null);const reset=auth.resetToken();assert.equal(auth.resetAdmin(reset,'owner-password-123'),true);assert.equal(auth.resetAdmin(reset,'intruder-password-123'),false);
 let owner=auth.login('admin','owner-password-123');assert.equal(auth.session(owner),'admin');auth.changeTeam('team-password-123');let team=auth.login('team','team-password-123');assert.equal(auth.session(team),'team');
 auth.changeTeam('new-team-password-123');assert.equal(auth.session(team),null);assert.equal(auth.login('team','team-password-123'),null);assert.equal(auth.session(owner),'admin');team=auth.login('team','new-team-password-123');assert.equal(auth.session(team),'team');
 auth.close();auth=createAuth(join(dir,'auth.sqlite'),{now:()=>clock});assert.equal(auth.session(team),'team');auth.revokeTeam();assert.equal(auth.session(team),null);
 assert.equal(auth.changeAdmin(owner,'wrong','another-owner-password'),false);assert.equal(auth.changeAdmin(owner,'owner-password-123','another-owner-password'),true);assert.equal(auth.session(owner),null);owner=auth.login('admin','another-owner-password');assert.equal(auth.session(owner),'admin');
 const expired=auth.resetToken();clock+=900001;assert.equal(auth.resetAdmin(expired,'reset-owner-password'),false);const fresh=auth.resetToken();assert.equal(auth.resetAdmin(fresh,'reset-owner-password'),true);assert.equal(auth.session(owner),null);assert.equal(auth.resetAdmin(fresh,'reuse-owner-password'),false);
 assert.throws(()=>auth.changeTeam('short'),/PASSWORD_LENGTH/);assert.equal(auth.limited('test',1,1000),false);assert.equal(auth.limited('test',1,1000),true);clock+=1001;assert.equal(auth.limited('test',1,1000),false);owner=auth.login('admin','reset-owner-password');clock+=86400001;assert.equal(auth.session(owner),null);
 }finally{auth.close();rmSync(dir,{recursive:true,force:true})}
});
