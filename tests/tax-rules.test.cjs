const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const window={EuroteamsDailyRates:{NL:['Nyderlandai','Netherlands',64]}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../tax-rules-2026.js'),'utf8'),{window});
const T=window.EuroteamsTax2026;let tests=0;
function near(actual,expected,label){assert.ok(Math.abs(actual-expected)<.00001,`${label}: ${actual} != ${expected}`);tests++}
const cfg={employerRate:1.77,applyNpd:false,pension2:false,floorBase:1153};
near(T.fromNet(2300,cfg).gross,3801.652892561983,'Audit net/gross reference');
near(T.fromNet(2300,{...cfg,pension2:true}).gross,4000,'Pension reference');
near(T.payroll(1500,{...cfg,applyNpd:true}).npd,576.97,'2026 NPD at 1500 gross');
near(T.payroll(1500,{...cfg,applyNpd:true}).net,1022.894,'2026 net with NPD');
near(T.payroll(1500,{...cfg,applyNpd:true,taxResident:false}).npd,0,'Non-resident monthly NPD disabled');
near(T.payroll(1000,cfg).floorCost,32.2983,'Employer-funded floor, GF actual-pay base');
near(T.payroll(1000,cfg).payrollCost,1049.9983,'Employment cost includes floor');
near(T.payroll(1000,{...cfg,floorBase:0}).payrollCost,1017.7,'Statutory floor exception input');
near(T.progressive(83237.4),16647.48,'36 VDU threshold');
near(T.progressive(138729),30520.38,'60 VDU threshold');
near(T.progressive(180000),43727.1,'Progressive tax above 60 VDU');
let p=T.payroll(8000,{...cfg,taxMode:'annualAverage'});
near(p.gpm,1653.1775,'Annual-average GPM on 96000');near(p.net,4786.8225,'Annual-average net on 96000');
p=T.payroll(15000,{...cfg,taxMode:'annualAverage'});
near(p.vsd,1447.4059,'Annual-average capped employee VSD');near(p.psd,1047,'PSD remains uncapped');near(p.employerTaxes,215.630875,'Employer VSD capped; GF/ILDF uncapped');near(p.net,8861.6691,'Annual-average net after progressive tax and caps');
p=T.payroll(3000,{...cfg,priorSocialIncome:137729});near(p.vsdBase,1000,'Only remaining annual VSD base is used');near(p.net,2065.4,'Actual month with remaining VSD base');near(p.employerTaxes,24.1,'Employer cap in actual-month model');
const pc={...cfg,a1:true,country:'NL',days:30,perDiemRate:64};
let b=T.payroll(1800,pc),post=T.posting(b,pc,80);
near(post.exemptPerDiem,900,'Monthly contract cannot borrow hourly exemption threshold');
near(T.posting(b,{...pc,wageBasis:'hourly'},80).exemptPerDiem,1920,'Hourly contract uses hourly threshold');
near(T.posting(b,{...pc,contractWage:2000},80).exemptPerDiem,1920,'Stipulated monthly wage used for part-month scenario');
b=T.payroll(4000,pc);post=T.posting(b,{...pc,shortDays:2},200);
near(post.effectiveDays,28.4,'Two short boundary days count as 20% each');near(post.totalPerDiem,1817.6,'Short days daily allowance');
post=T.posting(b,{...pc,perDiemRate:80},200);near(post.exemptPerDiem,1920,'Tax-free country maximum');near(post.taxablePerDiem,480,'Excess over country maximum taxable');
post=T.posting(b,{...pc,country:'OTHER',customCountryLimit:50,perDiemRate:60},200);near(post.exemptPerDiem,1500,'Custom verified country limit');
post=T.posting(T.payroll(500,pc),pc,200);near(post.payrollPostingCost,2458.409,'Taxable allowance recalculates floor once');
for(const annual of [false,true])for(const pension2 of [false,true])for(const applyNpd of [false,true])for(const gross of [0,100,747,1153,1902.45,2677.49,8000,11560.75,15000,200000]){
 const c={...cfg,pension2,applyNpd,taxMode:annual?'annualAverage':'monthly'};const result=T.payroll(gross,c);near(T.fromNet(result.net,c).gross,gross,'Round trip across tax thresholds');
 assert.ok(Number.isFinite(result.payrollCost)&&result.payrollCost>=gross);tests++;
}
console.log(`${tests} tax assertions passed`);
