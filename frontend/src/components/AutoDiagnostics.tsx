import { useEffect, useRef, useState } from "react";
import "./AutoDiagnostics.css";
import LoadingSpinner from "./LoadingSpinner";
import { getApiUrl } from "../config";

type TestStatus = "pending" | "running" | "passed" | "failed" | "unsupported";
type AutoTest = { id: string; name: string; description: string; status: TestStatus; detail?: string };
type ManualCheck = { id: string; label: string; options: Array<{ value: string; label: string }> };

const AUTO_TESTS: Array<Omit<AutoTest, "status">> = [
  { id: "wifi", name: "Wi-Fi", description: "Checking network connectivity" },
  { id: "gps", name: "GPS / Location", description: "Testing location access" },
  { id: "camera_front", name: "Front Camera", description: "Detecting front camera" },
  { id: "camera_back", name: "Back Camera", description: "Detecting rear camera" },
  { id: "microphone", name: "Microphone", description: "Testing microphone access" },
  { id: "speaker", name: "Speaker", description: "Testing audio output" },
  { id: "battery", name: "Battery", description: "Reading battery info" },
  { id: "bluetooth", name: "Bluetooth", description: "Checking Bluetooth availability" },
  { id: "touch", name: "Touchscreen", description: "Touch calibration test" },
];

const MANUAL_CHECKS: ManualCheck[] = [
  { id: "screen_cracks", label: "Screen cracks", options: [{ value: "none", label: "None" }, { value: "minor", label: "Minor" }, { value: "major", label: "Major/Cracked" }] },
  { id: "body_damage", label: "Body damage", options: [{ value: "none", label: "None" }, { value: "minor", label: "Minor" }, { value: "major", label: "Major" }] },
  { id: "dents", label: "Dents", options: [{ value: "none", label: "None" }, { value: "yes", label: "Yes" }] },
  { id: "scratches", label: "Scratches", options: [{ value: "none", label: "None" }, { value: "minor", label: "Minor" }, { value: "heavy", label: "Heavy" }] },
  { id: "display_originality", label: "Display originality", options: [{ value: "original", label: "Original" }, { value: "replaced", label: "Replaced/Aftermarket" }, { value: "unknown", label: "Unknown" }] },
  { id: "loose_screen", label: "Loose screen", options: [{ value: "no", label: "No" }, { value: "yes", label: "Yes" }] },
  { id: "missing_parts", label: "Missing parts", options: [{ value: "none", label: "None" }, { value: "back_cover", label: "Back cover" }, { value: "sim_tray", label: "SIM tray" }, { value: "other", label: "Other" }] },
  { id: "camera_glass", label: "Camera glass damage", options: [{ value: "none", label: "None" }, { value: "cracked", label: "Cracked" }, { value: "scratched", label: "Scratched" }] },
  { id: "battery_health_manual", label: "Battery health", options: [{ value: "good", label: "Good (>85%)" }, { value: "average", label: "Average (70-85%)" }, { value: "poor", label: "Poor (<70%)" }, { value: "unknown", label: "Unknown" }] },
  { id: "warranty", label: "Warranty status", options: [{ value: "active", label: "Active" }, { value: "expired", label: "Expired" }, { value: "none", label: "None" }] },
  { id: "original_box", label: "Original box", options: [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }] },
  { id: "finance_lock", label: "Finance/EMI lock", options: [{ value: "no", label: "No lock" }, { value: "yes", label: "Has lock" }, { value: "unknown", label: "Unknown" }] },
  { id: "sim_working", label: "SIM working", options: [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "dual", label: "Dual SIM working" }] },
];

type Props = { inspectionCode: string; onComplete: (r:any)=>void; onError: (m:string)=>void };

export default function AutoDiagnostics({ inspectionCode, onComplete, onError }: Props) {
  const [tests, setTests] = useState<AutoTest[]>(AUTO_TESTS.map(t=>({...t,status:"pending"})));
  const [manual, setManual] = useState<Record<string,string>>({});
  const [phase, setPhase] = useState<"running"|"manual"|"saving">("running");
  const [touchDots, setTouchDots] = useState<Array<{x:number,y:number,touched:boolean}>>([]);
  const [touchActive, setTouchActive] = useState(false);
  const startedRef = useRef(false);
  useEffect(()=>{ if(startedRef.current)return; startedRef.current=true; runAllTests(); },[]);
  const updateTest=(id:string,status:TestStatus,detail?:string)=>{ setTests(p=>p.map(t=>t.id===id?{...t,status,detail}:t)); };
  const runAllTests=async()=>{
    updateTest("wifi","running"); try{ if(navigator.onLine) updateTest("wifi","passed","Connected"); else updateTest("wifi","failed","Offline"); }catch{updateTest("wifi","unsupported");}
    updateTest("gps","running"); try{ if(navigator.geolocation){ navigator.geolocation.getCurrentPosition(()=>updateTest("gps","passed","Location available"),()=>updateTest("gps","failed","No location access"),{timeout:5000}); }else updateTest("gps","unsupported"); }catch{updateTest("gps","unsupported");}
    updateTest("camera_front","running"); updateTest("camera_back","running"); try{ const devices=await navigator.mediaDevices.enumerateDevices(); const videos=devices.filter(d=>d.kind==="videoinput"); if(videos.length>=2){updateTest("camera_front","passed","Available");updateTest("camera_back","passed","Available");}else if(videos.length===1){updateTest("camera_front","passed","Available");updateTest("camera_back","failed","Not detected");}else{updateTest("camera_front","failed","Not found");updateTest("camera_back","failed","Not found");}}catch{updateTest("camera_front","unsupported");updateTest("camera_back","unsupported");}
    updateTest("microphone","running"); try{ const s=await navigator.mediaDevices.getUserMedia({audio:true}); s.getTracks().forEach(t=>t.stop()); updateTest("microphone","passed","Mic accessible"); }catch{updateTest("microphone","failed","No mic access/blocked");}
    updateTest("speaker","running"); try{ const AC:any=(window as any).AudioContext||(window as any).webkitAudioContext; const ctx=new AC(); const osc=ctx.createOscillator(); const gain=ctx.createGain(); osc.connect(gain); gain.connect(ctx.destination); gain.gain.setValueAtTime(0.01,ctx.currentTime); osc.start(); osc.stop(ctx.currentTime+0.1); updateTest("speaker","passed","Audio output ready"); setTimeout(()=>ctx.close(),500);}catch{updateTest("speaker","failed","Audio test failed");}
    updateTest("battery","running"); try{ const nav:any=navigator; if(nav.getBattery){ const b=await nav.getBattery(); updateTest("battery","passed",`Level ${Math.round(b.level*100)}% ${b.charging?"(Charging)":""}`); }else updateTest("battery","unsupported"); }catch{updateTest("battery","unsupported");}
    updateTest("bluetooth","running"); try{ if((navigator as any).bluetooth) updateTest("bluetooth","passed","Available"); else updateTest("bluetooth","unsupported"); }catch{updateTest("bluetooth","unsupported");}
    updateTest("touch","pending"); setTimeout(()=>setPhase("manual"),1500);
  };
  const startTouchTest=()=>{ setTouchActive(true); setTouchDots(Array.from({length:9},(_,i)=>({x:20+(i%3)*30,y:20+Math.floor(i/3)*30,touched:false}))); updateTest("touch","running","Tap all dots"); };
  const touchDot=(idx:number)=>{ setTouchDots(p=>{ const n=p.map((d,i)=>i===idx?{...d,touched:true}:d); if(n.every(d=>d.touched)){ updateTest("touch","passed","All points touched"); setTimeout(()=>setTouchActive(false),250); } return n; }); };
  const submit=async()=>{
    setPhase("saving");
    const failed=tests.filter(t=>t.status==="failed").map(t=>t.id);
    const passed=tests.filter(t=>t.status==="passed").length;
    const total=tests.filter(t=>t.status!=="unsupported").length;
    const score=total>0?Math.round((passed/total)*100):50;
    const report={auto:Object.fromEntries(tests.map(t=>[t.id,{status:t.status,detail:t.detail}])),manual,failed,passed_count:passed,total_tested:total};
    try{
      const dr=await fetch(getApiUrl(`/api/inspections/${inspectionCode}/diagnostics`),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({working:failed.length>4?"no":failed.length>1?"partial":"yes",diagnostics_score:score,diagnostics_report:report})});
      if(!dr.ok){ const e=await dr.json().catch(()=>null); throw new Error(e?.detail||"Failed"); }
      onComplete(report);
    }catch(err:any){ onError(err.message||"Failed"); setPhase("manual"); }
  };
  if(phase==="saving") return <div className="ad-container"><LoadingSpinner overlay label="Saving diagnostics..." /></div>;
  return (<div className="ad-container"><div className="ad-header"><h1>Device Diagnostics</h1><p>Auto tests + physical checks</p></div>
    {phase==="running" && (<><div className="ad-section"><h2>Automatic Tests</h2><div className="ad-tests">{tests.map(test=>(<div key={test.id} className={`ad-test ad-test--${test.status}`}><div className="ad-test__info"><div className="ad-test__name">{test.name}</div><div className="ad-test__desc">{test.detail||test.description}</div></div><div className="ad-test__status">{test.status==="passed"?"?":test.status==="failed"?"?":test.status==="unsupported"?"??":test.status==="running"?"?":"?"}</div></div>))}</div></div>{tests.find(t=>t.id==="touch")?.status==="pending" && <button className="ad-btn" onClick={startTouchTest}>Start Touchscreen Test</button>}{touchActive && <div className="ad-touch-modal"><div className="ad-touch-grid">{touchDots.map((dot,idx)=>(<button key={idx} className={`ad-touch-dot ${dot.touched?"ad-touch-dot--touched":""}`} style={{left:dot.x+"%",top:dot.y+"%"}} onClick={()=>touchDot(idx)}/>))}</div><p>Tap all dots</p></div>}</>)}
    {phase==="manual" && (<><div className="ad-section"><h2>Physical & Other Checks</h2><div className="ad-manual">{MANUAL_CHECKS.map(check=>(<div key={check.id} className="ad-manual__row"><div className="ad-manual__label">{check.label}</div><div className="ad-manual__options">{check.options.map(opt=>(<button key={opt.value} className={`ad-manual__btn ${manual[check.id]===opt.value?"ad-manual__btn--active":""}`} onClick={()=>setManual(p=>({...p,[check.id]:opt.value}))}>{opt.label}</button>))}</div></div>))}</div></div><button className="ad-btn ad-btn--primary" onClick={submit} disabled={Object.keys(manual).length<8}>Complete Diagnostics & Get Valuation</button></>)}
  </div>);
}

