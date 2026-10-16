(() => {
  'use strict';
  // Bound user inputs before multiplication so invalid magnitudes cannot overflow.
  const MAX_INPUT=1e9;
  window.EuroteamsInput=Object.freeze({max:MAX_INPUT,normalize(value,min=0){
    const number=Number(value);
    return Number.isFinite(number)?Math.min(MAX_INPUT,Math.max(min,number)):min;
  }});
  const pending=new Map();
  const store={
    getItem(key){if(pending.has(key))return pending.get(key);try{return localStorage.getItem(key)}catch{return null}},
    setItem(key,value){const text=String(value);try{localStorage.setItem(key,text);pending.delete(key)}catch{pending.set(key,text)}},
    removeItem(key){try{localStorage.removeItem(key);pending.delete(key)}catch{pending.set(key,null)}},
    hasPending(){return pending.size>0}
  };
  window.EuroteamsStorage=Object.freeze(store);
  if(typeof window.structuredClone!=='function')window.structuredClone=value=>JSON.parse(JSON.stringify(value));
})();
