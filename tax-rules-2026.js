/* Lithuanian employment planning rules, reviewed 2026-10-15.
   Annual-average mode assumes 12 identical months, not an actual monthly payslip.
   Sources and exclusions are documented in TAX_DEVICE_AUDIT.md. */
(() => {
  'use strict';
  const nonnegative=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const RULES=Object.freeze({mma:1153,maxNpd:747,npdSlope:.49,vsd:.1252,psd:.0698,pension:.03,socialCap:138729,gpmThreshold1:83237.4,gpmThreshold2:138729,monthlyPostingThreshold:1902.45,hourlyPostingThreshold:11.6325});
  const progressive=income=>{const x=nonnegative(income);return Math.min(x,RULES.gpmThreshold1)*.20+Math.min(Math.max(0,x-RULES.gpmThreshold1),RULES.gpmThreshold2-RULES.gpmThreshold1)*.25+Math.max(0,x-RULES.gpmThreshold2)*.32};
  function npd(gross,enabled){return enabled?Math.min(nonnegative(gross),Math.max(0,RULES.maxNpd-RULES.npdSlope*Math.max(0,nonnegative(gross)-RULES.mma))):0}
  function payroll(gross,cfg={}){
    gross=nonnegative(gross);const annual=cfg.taxMode==='annualAverage',resident=cfg.taxResident!==false,other=nonnegative(cfg.otherAnnualIncome),rate=nonnegative(cfg.employerRate??1.77)/100;
    const vsdBase=annual?Math.min(gross,RULES.socialCap/12):Math.min(gross,Math.max(0,RULES.socialCap-nonnegative(cfg.priorSocialIncome)));
    const vsd=vsdBase*RULES.vsd,psd=gross*RULES.psd,sodra=vsd+psd,pension=cfg.pension2?vsdBase*RULES.pension:0;
    const N=resident?npd(annual?gross+other/12:gross,cfg.applyNpd):0;
    const gpmBase=Math.max(0,gross-N),gpm=annual?Math.max(0,(progressive(gross*12+other)-progressive(other))/12-N*.20):gpmBase*.20;
    // GF and ILDF (0.16% each) are outside VSD; cap only the VSD component.
    const fundsRate=Math.min(rate,.0032),employerTaxes=vsdBase*Math.max(0,rate-fundsRate)+gross*fundsRate;
    const floorBase=nonnegative(cfg.floorBase??1153),floorGap=Math.max(0,floorBase-gross);
    // GF follows actual pay; employer VSD/ILDF and employee VSD/PSD top-up is employer-funded.
    const floorCost=floorGap*(RULES.vsd+RULES.psd+Math.max(0,rate-.0016));
    return {gross,vsd,psd,sodra,pension,npd:N,gpmBase,gpm,net:gross-sodra-pension-gpm,employerTaxes,floorCost,vsdBase,payrollCost:gross+employerTaxes+floorCost,annual};
  }
  function fromNet(target,cfg={}){
    target=nonnegative(target);let lo=0,hi=Math.max(3000,target*4+1000);
    for(let i=0;i<30&&payroll(hi,cfg).net<target;i++)hi*=2;
    for(let i=0;i<110;i++){const mid=(lo+hi)/2;if(payroll(mid,cfg).net<target)lo=mid;else hi=mid}
    return payroll(target?(lo+hi)/2:0,cfg);
  }
  function posting(base,cfg,hours){
    if(!cfg.a1)return {totalPerDiem:0,exemptPerDiem:0,taxablePerDiem:0,taxablePerDiemNet:0,taxableEmployerTaxes:0,floorAdjustment:0,totalSodra:base.sodra,totalPension:base.pension,totalGpm:base.gpm,paidToEmployee:base.net,payrollPostingCost:base.payrollCost,fullyExempt:true,hourlyGross:hours?base.gross/hours:0,effectiveDays:0};
    const days=Math.min(31,Math.trunc(nonnegative(cfg.days))),shortDays=Math.min(days,2,Math.trunc(nonnegative(cfg.shortDays))),effectiveDays=days-.8*shortDays;
    const totalPerDiem=nonnegative(cfg.perDiemRate)*effectiveDays;
    const hourlyGross=hours?base.gross/hours:0,hourly=cfg.wageBasis==='hourly';
    const contractWage=nonnegative(cfg.contractWage)||(hourly?hourlyGross:base.gross);
    const fullyExempt=contractWage+1e-9>=(hourly?RULES.hourlyPostingThreshold:RULES.monthlyPostingThreshold);
    const maximum=cfg.country==='OTHER'?nonnegative(cfg.customCountryLimit):nonnegative(window.EuroteamsDailyRates?.[cfg.country||'NL']?.[2]);
    const salaryReference=hourly?contractWage*nonnegative(hours):contractWage;
    const exemptPerDiem=Math.min(totalPerDiem,maximum*effectiveDays,fullyExempt?totalPerDiem:salaryReference*.5);
    const taxablePerDiem=Math.max(0,totalPerDiem-exemptPerDiem),combined=payroll(base.gross+taxablePerDiem,cfg);
    return {totalPerDiem,exemptPerDiem,taxablePerDiem,taxablePerDiemNet:Math.max(0,combined.net-base.net),taxableEmployerTaxes:combined.employerTaxes-base.employerTaxes,floorAdjustment:combined.floorCost-base.floorCost,totalSodra:combined.sodra,totalPension:combined.pension,totalGpm:combined.gpm,paidToEmployee:combined.net+exemptPerDiem,payrollPostingCost:combined.payrollCost+exemptPerDiem,fullyExempt,hourlyGross,effectiveDays,contractWage,maximum};
  }
  window.EuroteamsTax2026=Object.freeze({RULES,progressive,npd,payroll,fromNet,posting});
})();
