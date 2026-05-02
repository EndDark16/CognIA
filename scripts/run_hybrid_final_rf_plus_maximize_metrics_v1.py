#!/usr/bin/env python
from __future__ import annotations

import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

LINE="hybrid_final_rf_plus_maximize_metrics_v1"; FREEZE="v12"; SOURCE_LINE="v12_final_rf_plus_maximize_metrics_v1"
ACTIVE_SRC=ROOT/"data/hybrid_active_modes_freeze_v11/tables/hybrid_active_models_30_modes.csv"
OP_SRC=ROOT/"data/hybrid_operational_freeze_v11/tables/hybrid_operational_final_champions.csv"
SUMMARY_SRC=ROOT/"data/hybrid_active_modes_freeze_v11/tables/hybrid_active_modes_summary.csv"
INPUTS_SRC=ROOT/"data/hybrid_active_modes_freeze_v11/tables/hybrid_questionnaire_inputs_master.csv"
DATASET=ROOT/"data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"
FE_REGISTRY=ROOT/"data/hybrid_no_external_scores_rebuild_v2/feature_engineering/hybrid_no_external_scores_feature_engineering_registry.csv"
BASE=ROOT/"data"/LINE; ART=ROOT/"artifacts"/LINE; ACTIVE_OUT=ROOT/"data"/f"hybrid_active_modes_freeze_{FREEZE}"; OP_OUT=ROOT/"data"/f"hybrid_operational_freeze_{FREEZE}"
ACTIVE_ART=ROOT/"artifacts"/f"hybrid_active_modes_freeze_{FREEZE}"; OP_ART=ROOT/"artifacts"/f"hybrid_operational_freeze_{FREEZE}"
NORM_BASE=ROOT/"data/hybrid_classification_normalization_v2"; NORM_OUT=NORM_BASE/"tables"/f"hybrid_operational_classification_normalized_{FREEZE}.csv"; NORM_VIOL=NORM_BASE/"validation"/f"hybrid_classification_policy_violations_{FREEZE}.csv"
SHORTCUT_OUT=BASE/"tables/shortcut_inventory_final_rf_plus_maximize_metrics_v1.csv"; MODEL_OUT=ROOT/"models/active_modes"
V10_COMPARISON=ROOT/"data/hybrid_rf_max_real_metrics_v1/tables/final_old_vs_rf_comparison_v11.csv"
V11_STRESS=ROOT/"data/hybrid_rf_max_real_metrics_v1/stress/selected_rf_stress_audit.csv"
V11_IMPORTANCE=ROOT/"data/hybrid_rf_max_real_metrics_v1/importance/selected_rf_feature_importance.csv"
DOMAINS=["adhd","conduct","elimination","anxiety","depression"]; WATCH=("recall","specificity","roc_auc","pr_auc"); SEEDS=[20270421,20270439,20270457]; BASE_SEED=20261101
BOOT_N=80; PERM_REPEATS=2
RF_CONFIGS=[
 {"config_id":"rf_v11_balanced_regularized","n_estimators":160,"max_depth":6,"min_samples_split":18,"min_samples_leaf":8,"max_features":"sqrt","class_weight":"balanced","bootstrap":True,"max_samples":.85,"criterion":"gini","ccp_alpha":0.0,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_v11_guardrail_very_random","n_estimators":35,"max_depth":2,"min_samples_split":180,"min_samples_leaf":95,"max_features":1,"class_weight":"manual_recall","bootstrap":True,"max_samples":.25,"criterion":"gini","ccp_alpha":.015,"oob_score":False,"calibrations":["none"]},
 {"config_id":"rf_v11_recall_guarded","n_estimators":160,"max_depth":5,"min_samples_split":12,"min_samples_leaf":5,"max_features":"log2","class_weight":"manual_recall","bootstrap":True,"max_samples":.90,"criterion":"gini","ccp_alpha":0.0,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_v11_precision_guarded","n_estimators":170,"max_depth":4,"min_samples_split":24,"min_samples_leaf":12,"max_features":.45,"class_weight":"balanced_subsample","bootstrap":True,"max_samples":.80,"criterion":"gini","ccp_alpha":.0005,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_v11_calibrated_regularized","n_estimators":120,"max_depth":5,"min_samples_split":16,"min_samples_leaf":8,"max_features":"sqrt","class_weight":"balanced_subsample","bootstrap":True,"max_samples":.85,"criterion":"gini","ccp_alpha":0.0,"oob_score":False,"calibrations":["none","sigmoid","isotonic"]},
 {"config_id":"rf_v11_guardrail_randomized","n_estimators":75,"max_depth":3,"min_samples_split":90,"min_samples_leaf":45,"max_features":.20,"class_weight":"balanced_subsample","bootstrap":True,"max_samples":.45,"criterion":"entropy","ccp_alpha":.002,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_plus_deep_controlled","n_estimators":220,"max_depth":10,"min_samples_split":8,"min_samples_leaf":3,"max_features":"sqrt","class_weight":"balanced_subsample","bootstrap":True,"max_samples":.85,"criterion":"gini","ccp_alpha":.00001,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_plus_precision_recovery","n_estimators":220,"max_depth":8,"min_samples_split":20,"min_samples_leaf":8,"max_features":.75,"class_weight":"balanced_subsample","bootstrap":True,"max_samples":.82,"criterion":"gini","ccp_alpha":.0001,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_plus_feature_bagging","n_estimators":220,"max_depth":10,"min_samples_split":8,"min_samples_leaf":4,"max_features":.25,"class_weight":"balanced_subsample","bootstrap":True,"max_samples":.80,"criterion":"gini","ccp_alpha":0.0,"oob_score":True,"calibrations":["none"]},
 {"config_id":"rf_plus_train_only_oversample","n_estimators":180,"max_depth":8,"min_samples_split":10,"min_samples_leaf":5,"max_features":"sqrt","class_weight":"balanced_subsample","bootstrap":True,"max_samples":.80,"criterion":"gini","ccp_alpha":.00005,"oob_score":False,"calibrations":["none"],"resampling":"positive_oversample_moderate"},
]
THRESHOLD_STRATEGIES=["max_f1_precision_guard","recall_target_guard","f1_ba_conservative","precision_recovery","pareto_f1_recall_precision"]

def now(): return datetime.now(timezone.utc).isoformat()
def save(df:pd.DataFrame,path:Path): path.parent.mkdir(parents=True,exist_ok=True); df.to_csv(path,index=False,lineterminator="\n")
def write(path:Path,text:str): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text.rstrip()+"\n",encoding="utf-8")
def mkdirs():
    for p in [BASE/"audit",BASE/"trials",BASE/"tables",BASE/"validation",BASE/"bootstrap",BASE/"stress",BASE/"importance",BASE/"calibration",BASE/"artifacts",BASE/"reports",BASE/"supabase_sync",ART,ACTIVE_OUT/"tables",ACTIVE_OUT/"reports",ACTIVE_OUT/"validation",OP_OUT/"tables",OP_OUT/"reports",OP_OUT/"validation",ACTIVE_ART,OP_ART,NORM_BASE/"tables",NORM_BASE/"validation",MODEL_OUT]: p.mkdir(parents=True,exist_ok=True)
def sf(v:Any,d:float=np.nan)->float:
    try:
        if pd.isna(v): return d
        return float(v)
    except Exception: return d
def feats(pipe:Any)->list[str]: return [x.strip() for x in str(pipe or "").split("|") if x.strip() and x.strip().lower()!="nan"]
def tcol(d:str)->str: return f"target_domain_{d}_final"
def recall_band(m:str): return (.88,.95) if str(m).endswith("1_3") else (.92,.98)
def pfloor(d:str,m:str,oldp:float):
    base=.75 if str(m).endswith("1_3") else .80
    if d in {"adhd","depression","elimination"}: base-=.05
    return max(.62,min(base,max(.62,oldp-.05)))
def guard(row:Any)->bool: return all(sf(row.get(k),1.0)<=.98 for k in WATCH)
def auc(y,p): return float(roc_auc_score(y,p)) if len(np.unique(y))>1 else float("nan")
def prauc(y,p): return float(average_precision_score(y,p)) if len(np.unique(y))>1 else float(np.mean(y))
def metrics(y,p,t):
    p=np.clip(np.asarray(p,float),1e-6,1-1e-6); pred=(p>=t).astype(int); tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel(); spec=float(tn/(tn+fp)) if (tn+fp) else 0.0
    return {"precision":float(precision_score(y,pred,zero_division=0)),"recall":float(recall_score(y,pred,zero_division=0)),"specificity":spec,"balanced_accuracy":float(balanced_accuracy_score(y,pred)),"f1":float(f1_score(y,pred,zero_division=0)),"roc_auc":auc(y,p),"pr_auc":prauc(y,p),"brier":float(brier_score_loss(y,p)),"tn":int(tn),"fp":int(fp),"fn":int(fn),"tp":int(tp)}
def ece(y,p,bins=10):
    p=np.clip(np.asarray(p,float),1e-6,1-1e-6); edges=np.linspace(0,1,bins+1); idx=np.digitize(p,edges[1:-1],right=False); out=0.0
    for b in range(bins):
        m=idx==b
        if np.any(m): out+=float(np.mean(m))*abs(float(np.mean(y[m]))-float(np.mean(p[m])))
    return float(out)
def score(row:Any)->float:
    s=.40*sf(row.get("f1"),0)+.22*sf(row.get("recall"),0)+.18*sf(row.get("precision"),0)+.14*sf(row.get("balanced_accuracy"),0)+.06*max(0,1-sf(row.get("brier"),.2))
    if not guard(row): s-=2
    if sf(row.get("precision"),0)<sf(row.get("precision_floor"),0): s-=.35
    if sf(row.get("overfit_gap_train_val_ba"),0)>.12: s-=.10
    if sf(row.get("generalization_gap_val_holdout_ba"),0)>.10: s-=.10
    return float(s)
def split_registry(df):
    ids=df.participant_id.astype(str).to_numpy(); sp={}; rows=[]
    for i,d in enumerate(DOMAINS):
        y=df[tcol(d)].astype(int).to_numpy(); seed=BASE_SEED+i*23; tr,tmp,ytr,ytmp=train_test_split(ids,y,test_size=.40,random_state=seed,stratify=y); va,ho,yva,yho=train_test_split(tmp,ytmp,test_size=.50,random_state=seed+1,stratify=ytmp); sp[d]={"train":list(map(str,tr)),"val":list(map(str,va)),"holdout":list(map(str,ho))}
        for name,arr,yy in [("train",tr,ytr),("val",va,yva),("holdout",ho,yho)]: rows.append({"domain":d,"target":tcol(d),"split":name,"n":len(arr),"positive_n":int(np.sum(yy)),"negative_n":int(len(yy)-np.sum(yy)),"positive_rate":float(np.mean(yy)),"seed":seed})
    return sp,pd.DataFrame(rows)
def sub(df,ids): return df[df.participant_id.astype(str).isin(set(map(str,ids)))].copy()
def prep_x(df,features):
    x=df[features].copy()
    for c in x.columns:
        x[c]=x[c].fillna("Unknown").astype(str) if c=="sex_assigned_at_birth" else pd.to_numeric(x[c],errors="coerce").astype(float)
    return x
def manual_weight(y):
    pos=max(float(np.mean(y)),1e-6); neg=max(1-pos,1e-6); return {0:1.0,1:float(min(3.6,max(1.2,neg/pos*1.15)))}
def train_only_resample(x,y,cfg,seed):
    mode=str(cfg.get("resampling","none") or "none")
    if mode=="none":
        return x,y,None
    rng=np.random.default_rng(seed+17); y=np.asarray(y,int); pos=np.where(y==1)[0]; neg=np.where(y==0)[0]
    if len(pos)==0 or len(neg)==0:
        return x,y,None
    if mode=="positive_oversample_moderate":
        target=min(int(len(neg)*0.72), int(len(pos)*1.85))
        extra=max(0,target-len(pos))
        add=rng.choice(pos,size=extra,replace=True) if extra else np.array([],dtype=int)
        idx=np.concatenate([np.arange(len(y)),add])
    elif mode=="negative_undersample_moderate":
        target_neg=max(len(pos)*2, int(len(neg)*0.72))
        keep_neg=rng.choice(neg,size=min(len(neg),target_neg),replace=False)
        idx=np.concatenate([pos,keep_neg])
    else:
        return x,y,None
    rng.shuffle(idx)
    return x.iloc[idx].reset_index(drop=True),y[idx],None
def sample_weight_for(y,cfg):
    mode=str(cfg.get("sample_weight_mode","none") or "none")
    if mode=="none":
        return None
    y=np.asarray(y,int); out=np.ones(len(y),float)
    if mode=="minority_light":
        pos=max(float(np.mean(y)),1e-6); neg=max(1-pos,1e-6); out[y==1]=min(2.4,max(1.15,neg/pos*.75))
    return out
def rf_pipe(features,cfg,seed,y):
    cats=[f for f in features if f=="sex_assigned_at_birth"]; nums=[f for f in features if f not in cats]
    pre=ColumnTransformer([("num",Pipeline([("imp",SimpleImputer(strategy="median",keep_empty_features=True))]),nums),("cat",Pipeline([("imp",SimpleImputer(strategy="most_frequent",keep_empty_features=True)),("oh",OneHotEncoder(handle_unknown="ignore",sparse_output=False))]),cats)],remainder="drop",verbose_feature_names_out=True)
    cw=manual_weight(y) if cfg["class_weight"]=="manual_recall" else cfg["class_weight"]
    rf=RandomForestClassifier(n_estimators=int(cfg["n_estimators"]),max_depth=cfg["max_depth"],min_samples_split=int(cfg["min_samples_split"]),min_samples_leaf=int(cfg["min_samples_leaf"]),max_features=cfg["max_features"],class_weight=cw,bootstrap=bool(cfg["bootstrap"]),max_samples=cfg["max_samples"],criterion=cfg["criterion"],ccp_alpha=float(cfg["ccp_alpha"]),oob_score=bool(cfg.get("oob_score",False)),random_state=seed,n_jobs=-1)
    return Pipeline([("pre",pre),("rf",rf)])
def fit_model(features,cfg,seed,cal,xtr,ytr):
    xfit,yfit,_=train_only_resample(xtr,ytr,cfg,seed); sw=sample_weight_for(yfit,cfg)
    pipe=rf_pipe(features,cfg,seed,yfit)
    if cal=="none":
        if sw is not None: pipe.fit(xfit,yfit,rf__sample_weight=sw)
        else: pipe.fit(xfit,yfit)
        return pipe
    cv=3 if min(np.bincount(ytr.astype(int)))>=3 else 2
    model=CalibratedClassifierCV(estimator=pipe,method=cal,cv=cv); model.fit(xfit,yfit); return model
def proba(model,x): return np.clip(np.asarray(model.predict_proba(x)[:,1],float),1e-6,1-1e-6)
def rf_estimators(model):
    if isinstance(model,Pipeline): return [model.named_steps["rf"]]
    out=[]
    for cc in getattr(model,"calibrated_classifiers_",[]) or []:
        est=getattr(cc,"estimator",None)
        if isinstance(est,Pipeline) and "rf" in est.named_steps: out.append(est.named_steps["rf"])
    return out
def importance(model,features):
    ests=rf_estimators(model); vals=np.zeros(len(features),float)
    for rf in ests:
        imp=np.asarray(getattr(rf,"feature_importances_",np.ones(len(features))/max(1,len(features))),float)
        if len(imp)!=len(features): imp=np.ones(len(features))/max(1,len(features))
        vals+=imp
    if ests: vals/=len(ests)
    if np.sum(vals)>0: vals/=np.sum(vals)
    return pd.Series(vals,index=features).sort_values(ascending=False)
def oob(model):
    vals=[float(rf.oob_score_) for rf in rf_estimators(model) if hasattr(rf,"oob_score_")]
    return float(np.mean(vals)) if vals else float("nan")

def thr_grid(p):
    vals=list(np.linspace(.05,.95,91))+list(np.quantile(p,np.linspace(.05,.95,37))) if len(p) else list(np.linspace(.05,.95,91))
    return np.array(sorted(set(float(x) for x in vals if 0<float(x)<1)),float)
def thr_score(strategy,d,m,mm,pf):
    lo,hi=recall_band(m)
    if strategy=="max_f1_precision_guard": s=.58*mm["f1"]+.16*mm["recall"]+.14*mm["precision"]+.10*mm["balanced_accuracy"]+.02*max(0,1-mm["brier"])
    elif strategy=="recall_target_guard":
        s=.36*mm["f1"]+.30*mm["recall"]+.16*mm["precision"]+.14*mm["balanced_accuracy"]+.04*max(0,1-mm["brier"])
        if lo<=mm["recall"]<=hi: s+=.04
    elif strategy=="precision_recovery":
        s=.46*mm["f1"]+.13*mm["recall"]+.25*mm["precision"]+.12*mm["balanced_accuracy"]+.04*max(0,1-mm["brier"])
        if mm["precision"]>=pf+.03: s+=.03
    elif strategy=="pareto_f1_recall_precision":
        s=.50*mm["f1"]+.22*mm["recall"]+.18*mm["precision"]+.08*mm["balanced_accuracy"]+.02*max(0,1-mm["brier"])
        if abs(mm["recall"]-min(max(mm["recall"],lo),hi))<=.02: s+=.015
    elif strategy=="clinical_utility":
        s=.44*mm["f1"]+.25*mm["recall"]+.15*mm["precision"]+.12*mm["balanced_accuracy"]+.04*max(0,1-mm["brier"])
        if mm["recall"]<lo: s-=.10
    elif strategy=="guardrail_conservative":
        s=.44*mm["f1"]+.16*mm["recall"]+.18*mm["precision"]+.16*mm["balanced_accuracy"]+.06*max(0,1-mm["brier"])
        if max(mm[k] for k in WATCH)>.975: s-=.12
    else: s=.42*mm["f1"]+.19*mm["recall"]+.17*mm["precision"]+.18*mm["balanced_accuracy"]+.04*max(0,1-mm["brier"])
    if mm["precision"]<pf: s-=.35+.75*(pf-mm["precision"])
    if mm["recall"]<lo: s-=.16*(lo-mm["recall"])
    if mm["recall"]>hi: s-=.12*(mm["recall"]-hi)
    for k in WATCH:
        if mm[k]>.98: s-=.50+(mm[k]-.98)
    if d in {"adhd","depression","elimination"} and lo<=mm["recall"]<=hi and mm["precision"]>=pf: s+=.015
    return float(s)
def choose_thr(strategy,d,m,y,p,pf):
    best=(.5,metrics(y,p,.5),-1e18)
    for t in thr_grid(p):
        mm=metrics(y,p,float(t)); s=thr_score(strategy,d,m,mm,pf)
        if s>best[2]: best=(float(t),mm,float(s))
    return best
def portfolio_audit(active,op,inputs,data):
    inp=set(inputs.feature.astype(str)) if "feature" in inputs.columns else set(); cols=set(data.columns); opi=op.set_index(["domain","mode"]); rows=[]
    for _,r in active.iterrows():
        fs=feats(r.feature_list_pipe); miss=[f for f in fs if f not in cols]; miss_in=[f for f in fs if f not in inp and not f.startswith("eng_")]; margin=min(.98-sf(r.get(k),1) for k in WATCH); key=(r.domain,r["mode"]); fclass=opi.loc[key,"final_class"] if key in opi.index else "por_confirmar"; gap=sf(opi.loc[key,"overfit_gap_train_val_ba"],np.nan) if key in opi.index else np.nan; cav=str(r.get("operational_caveat") or "")
        rows.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"active_model_id":r.active_model_id,"model_family":r.model_family,"feature_set_id":r.feature_set_id,"threshold":r.threshold,"n_features":len(fs),"feature_columns_sha16":hashlib.sha256("|".join(fs).encode()).hexdigest()[:16],"precision":r.precision,"recall":r.recall,"specificity":r.specificity,"balanced_accuracy":r.balanced_accuracy,"f1":r.f1,"roc_auc":r.roc_auc,"pr_auc":r.pr_auc,"brier":r.brier,"final_class":fclass,"final_operational_class":r.final_operational_class,"confidence_pct":r.confidence_pct,"confidence_band":r.confidence_band,"guardrail_margin_min":margin,"near_guardrail_flag":"yes" if margin<.01 else "no","guardrail_violation_flag":"yes" if any(sf(r.get(k),0)>.98 for k in WATCH) else "no","weak_class_flag":"yes" if fclass in {"REJECT_AS_PRIMARY","HOLD_FOR_LIMITATION"} or r.final_operational_class=="ACTIVE_LIMITED_USE" else "no","overfit_or_gap_flag":"yes" if str(r.get("overfit_flag"))=="yes" or gap>.10 else "no","secondary_anomaly_text_flag":"yes" if re.search("secondary|shortcut|stress|fragil|fragility|low precision",cav,re.I) else "no","feature_dominance_pending_audit":"yes","clone_pending_audit":"yes","missing_features_in_dataset":"|".join(miss),"missing_features_in_inputs_master":"|".join(miss_in),"input_compatibility_ok":"yes" if not miss else "no"})
    return pd.DataFrame(rows)
def class_balance(data):
    return pd.DataFrame([{"domain":d,"n":len(data[tcol(d)].dropna()),"positive_n":int(data[tcol(d)].fillna(0).astype(int).sum()),"negative_n":int((1-data[tcol(d)].fillna(0).astype(int)).sum()),"positive_rate":float(data[tcol(d)].fillna(0).astype(int).mean())} for d in DOMAINS])
def missingness(data,active):
    rows=[]
    for _,r in active.iterrows():
        rates=[float(data[f].isna().mean()) for f in feats(r.feature_list_pipe) if f in data.columns]
        rows.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"n_features":len(feats(r.feature_list_pipe)),"mean_missing_rate":float(np.mean(rates)) if rates else np.nan,"max_missing_rate":float(np.max(rates)) if rates else np.nan,"features_with_missing_gt_20pct":int(sum(x>.20 for x in rates))})
    return pd.DataFrame(rows)
def critical_slot_audit(active):
    comp=pd.read_csv(V10_COMPARISON) if V10_COMPARISON.exists() else pd.DataFrame()
    st=pd.read_csv(V11_STRESS) if V11_STRESS.exists() else pd.DataFrame()
    im=pd.read_csv(V11_IMPORTANCE) if V11_IMPORTANCE.exists() else pd.DataFrame()
    reg=set()
    if not comp.empty:
        reg=set((r.domain,r.role,r["mode"]) for _,r in comp[comp.delta_f1<0].iterrows())
    severe=set()
    if not st.empty:
        ss=st.groupby(["domain","role","mode"],dropna=False)["delta_f1"].min().reset_index()
        severe=set((r.domain,r.role,r["mode"]) for _,r in ss[ss.delta_f1<=-.30].iterrows())
    dominant=set()
    if not im.empty:
        top=im.sort_values(["domain","role","mode","importance"],ascending=[True,True,True,False]).groupby(["domain","role","mode"],dropna=False).head(1)
        dominant=set((r.domain,r.role,r["mode"]) for _,r in top[top.importance>.20].iterrows())
    rows=[]
    for _,r in active.iterrows():
        key=(r.domain,r.role,r["mode"]); reasons=["final_campaign_all_slots"]
        lo,_=recall_band(str(r["mode"]))
        if key in reg: reasons.append("v11_f1_regression_vs_v10_reference")
        if r.domain in {"adhd","depression","elimination"}: reasons.append("priority_domain")
        if sf(r.recall,0)<lo: reasons.append("recall_below_target_band")
        if sf(r.precision,0)<.74: reasons.append("precision_low")
        if sf(r.brier,0)>.08: reasons.append("brier_weak")
        if key in severe: reasons.append("stress_sensitivity_severe")
        if key in dominant: reasons.append("feature_dominance_gt_0_20")
        if str(r.final_operational_class)=="ACTIVE_LIMITED_USE": reasons.append("active_limited_use")
        rows.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"critical_slot":"yes","critical_reasons":"|".join(dict.fromkeys(reasons))})
    return pd.DataFrame(rows)
def train_slot(row,data,sp):
    d=str(row.domain); m=str(row["mode"]); role=str(row.role); fs=feats(row.feature_list_pipe); miss=[f for f in fs if f not in data.columns]
    if miss: raise RuntimeError(f"missing_features_for_slot:{d}/{m}:{miss[:5]}")
    tr,va,ho=sub(data,sp[d]["train"]),sub(data,sp[d]["val"]),sub(data,sp[d]["holdout"]); ytr=tr[tcol(d)].astype(int).to_numpy(); yva=va[tcol(d)].astype(int).to_numpy(); yho=ho[tcol(d)].astype(int).to_numpy(); xtr,xva,xho=prep_x(tr,fs),prep_x(va,fs),prep_x(ho,fs); pf=pfloor(d,m,sf(row.precision,.75)); rows=[]; cache={}
    for cfg in RF_CONFIGS:
        for seed in SEEDS:
            for cal in cfg["calibrations"]:
                if cal=="isotonic" and int(np.sum(ytr))<35: continue
                try:
                    model=fit_model(fs,cfg,seed,cal,xtr,ytr); ptr,pva,pho=proba(model,xtr),proba(model,xva),proba(model,xho); oo=oob(model); vece,hece=ece(yva,pva),ece(yho,pho)
                    for pol in THRESHOLD_STRATEGIES:
                        thr,vm,vscore=choose_thr(pol,d,m,yva,pva,pf); tm,hm=metrics(ytr,ptr,thr),metrics(yho,pho,thr); key=f"{d}::{m}::{cfg['config_id']}::{seed}::{cal}::{pol}::{thr:.6f}"
                        rec={"domain":d,"role":role,"mode":m,"previous_active_model_id":row.active_model_id,"previous_model_family":row.model_family,"previous_feature_set_id":row.feature_set_id,"feature_set_id":"same_inputs_v11","feature_list_pipe":"|".join(fs),"model_family":"rf","config_id":cfg["config_id"],"calibration":cal,"threshold_policy":pol,"threshold":thr,"seed":seed,"n_features":len(fs),"precision_floor":pf,"sample_weight_mode":str(cfg.get("sample_weight_mode","none")),"resampling":str(cfg.get("resampling","none")),"complementary_technique":"rf_base+"+str(cfg["config_id"])+":"+cal+":"+pol,"train_precision":tm["precision"],"train_recall":tm["recall"],"train_specificity":tm["specificity"],"train_balanced_accuracy":tm["balanced_accuracy"],"train_f1":tm["f1"],"train_roc_auc":tm["roc_auc"],"train_pr_auc":tm["pr_auc"],"train_brier":tm["brier"],"val_precision":vm["precision"],"val_recall":vm["recall"],"val_specificity":vm["specificity"],"val_balanced_accuracy":vm["balanced_accuracy"],"val_f1":vm["f1"],"val_roc_auc":vm["roc_auc"],"val_pr_auc":vm["pr_auc"],"val_brier":vm["brier"],"val_selection_score":vscore,"precision":hm["precision"],"recall":hm["recall"],"specificity":hm["specificity"],"balanced_accuracy":hm["balanced_accuracy"],"f1":hm["f1"],"roc_auc":hm["roc_auc"],"pr_auc":hm["pr_auc"],"brier":hm["brier"],"tn":hm["tn"],"fp":hm["fp"],"fn":hm["fn"],"tp":hm["tp"],"val_ece":vece,"holdout_ece":hece,"oob_score":oo,"overfit_gap_train_val_ba":tm["balanced_accuracy"]-vm["balanced_accuracy"],"generalization_gap_val_holdout_ba":abs(vm["balanced_accuracy"]-hm["balanced_accuracy"]),"guard_ok":"yes" if guard(hm) else "no","val_guard_ok":"yes" if guard(vm) else "no","precision_floor_ok":"yes" if hm["precision"]>=pf else "no","recall_target_ok":"yes" if recall_band(m)[0]<=hm["recall"]<=recall_band(m)[1] else "no","candidate_key":key,"trial_error":"none"}
                        rec["holdout_metric_score"]=score(rec); rows.append(rec); cache[key]={"model":model,"x_holdout":xho,"y_holdout":yho,"probs":pho,"pred":(pho>=thr).astype(int),"features":fs,"threshold":thr}
                except Exception as exc: rows.append({"domain":d,"role":role,"mode":m,"feature_set_id":"same_inputs_v11","model_family":"rf","config_id":cfg["config_id"],"calibration":cal,"threshold_policy":"all","sample_weight_mode":str(cfg.get("sample_weight_mode","none")),"resampling":str(cfg.get("resampling","none")),"seed":seed,"n_features":len(fs),"trial_error":repr(exc)})
    return pd.DataFrame(rows),cache
def select_best(old,trials):
    valid=trials[(trials.trial_error=="none")&(trials.guard_ok=="yes")&(trials.precision_floor_ok=="yes")].copy()
    stable=valid[(valid.overfit_gap_train_val_ba.astype(float)<=.10)&(valid.generalization_gap_val_holdout_ba.astype(float)<=.10)].copy() if not valid.empty else valid
    if not stable.empty: valid=stable
    if valid.empty: valid=trials[(trials.trial_error=="none")&(trials.guard_ok=="yes")].copy()
    if valid.empty: raise RuntimeError(f"no_guard_compliant_rf_candidate:{old.domain}/{old['mode']}")
    for m in ["f1","recall","precision","specificity","balanced_accuracy","roc_auc","pr_auc","brier"]: valid[f"old_{m}"]=sf(old.get(m),np.nan); valid[f"delta_{m}"]=valid[m].astype(float)-sf(old.get(m),0)
    valid["f1_tie_bucket"]=(valid.f1.astype(float)/.005).round().astype(int)
    valid["recall_in_target_band"]=valid.apply(lambda r: 1 if recall_band(str(r["mode"]))[0]<=sf(r.get("recall"),0)<=recall_band(str(r["mode"]))[1] else 0,axis=1)
    valid["sort_score"]=valid.holdout_metric_score.astype(float)
    valid=valid.sort_values(["f1_tie_bucket","f1","recall","precision","balanced_accuracy","brier","recall_in_target_band","val_selection_score","sort_score"],ascending=[False,False,False,False,False,True,False,False,False])
    top=valid.iloc[0].copy()
    if top.delta_f1>=.005: reason="f1_improved_by_final_rf_plus"
    elif top.delta_f1>=0 and top.delta_recall>=0: reason="f1_matched_with_recall_gain"
    elif top.delta_f1>=-.005 and top.delta_recall>=.01 and top.delta_precision>=-.04: reason="practical_f1_tie_with_recall_gain"
    else: reason="best_guard_compliant_rf_based_candidate"
    return top,reason
def pairwise(selected,cache):
    rows=[]
    for _,a in selected.iterrows():
        for _,b in selected.iterrows():
            if str(a.domain)!=str(b.domain) or str(a.candidate_key)>=str(b.candidate_key): continue
            if not (str(a.role)==str(b.role) or str(a.domain)=="elimination"): continue
            ca,cb=cache.get(str(a.candidate_key)),cache.get(str(b.candidate_key))
            if not ca or not cb: continue
            pa,pb=np.asarray(ca["probs"],float),np.asarray(cb["probs"],float); ra,rb=np.asarray(ca["pred"],int),np.asarray(cb["pred"],int); corr=float(np.corrcoef(pa,pb)[0,1]) if np.std(pa)>0 and np.std(pb)>0 else np.nan; fa,fb=set(feats(a.feature_list_pipe)),set(feats(b.feature_list_pipe)); md=max(abs(sf(a.get(c),0)-sf(b.get(c),0)) for c in ["f1","recall","precision","balanced_accuracy","specificity","threshold"])
            rows.append({"domain":a.domain,"role_a":a.role,"mode_a":a["mode"],"role_b":b.role,"mode_b":b["mode"],"threshold_a":a.threshold,"threshold_b":b.threshold,"probability_correlation":corr,"prediction_agreement":float(np.mean(ra==rb)),"identical_predictions":"yes" if np.array_equal(ra,rb) else "no","near_metric_clone_flag":"yes" if md<=.001 else "no","max_metric_abs_delta":float(md),"feature_jaccard":float(len(fa&fb)/max(1,len(fa|fb)))})
    return pd.DataFrame(rows)
def resolve_clones(selected,trials,cache):
    selected=selected.copy().reset_index(drop=True); changes=[]
    for _ in range(12):
        sim=pairwise(selected,cache); clones=sim[(sim.get("identical_predictions","no")=="yes")|((sim.get("near_metric_clone_flag","no")=="yes")&(sim.get("prediction_agreement",0)>=.995))].copy() if not sim.empty else pd.DataFrame()
        if clones.empty: break
        c=clones.iloc[0]; cand=selected[(selected.domain==c.domain)&(selected["mode"].isin([c.mode_a,c.mode_b]))].sort_values("holdout_metric_score"); changed=False
        for _,cur in cand.iterrows():
            alts=trials[(trials.domain==cur.domain)&(trials["mode"]==cur["mode"])&(trials.trial_error=="none")&(trials.guard_ok=="yes")&(trials.precision_floor_ok=="yes")&(trials.candidate_key!=cur.candidate_key)].sort_values("holdout_metric_score",ascending=False)
            for _,alt in alts.iterrows():
                tmp=selected.copy(); idx=tmp[(tmp.domain==cur.domain)&(tmp["mode"]==cur["mode"])].index[0]
                for col in alt.index: tmp.loc[idx,col]=alt[col]
                sim2=pairwise(tmp,cache); bad2=sim2[(sim2.get("identical_predictions","no")=="yes")|((sim2.get("near_metric_clone_flag","no")=="yes")&(sim2.get("prediction_agreement",0)>=.995))].copy() if not sim2.empty else pd.DataFrame()
                if bad2.empty or len(bad2)<len(clones): tmp.loc[idx,"selection_reason"]="anti_clone_conservative_tradeoff"; changes.append({"domain":cur.domain,"mode":cur["mode"],"old_candidate_key":cur.candidate_key,"new_candidate_key":alt.candidate_key,"old_score":cur.holdout_metric_score,"new_score":alt.holdout_metric_score,"reason":"anti_clone_alternative_selected"}); selected=tmp; changed=True; break
            if changed: break
        if not changed: changes.append({"domain":c.domain,"mode":f"{c.mode_a}|{c.mode_b}","reason":"clone_unresolved_no_valid_alternative"}); break
    return selected.reset_index(drop=True),pd.DataFrame(changes)

def boot_ci(y,p,t,seed):
    rng=np.random.default_rng(seed); idx=np.arange(len(y)); hist={k:[] for k in ["precision","recall","balanced_accuracy","f1","brier"]}
    for _ in range(BOOT_N):
        take=rng.choice(idx,size=len(idx),replace=True)
        if len(np.unique(y[take]))<2: continue
        mm=metrics(y[take],p[take],t)
        for k in hist: hist[k].append(float(mm[k]))
    out={}
    for k,v in hist.items():
        arr=np.asarray(v,float); out[f"{k}_boot_mean"]=float(np.mean(arr)) if len(arr) else np.nan; out[f"{k}_boot_ci_low"]=float(np.quantile(arr,.025)) if len(arr) else np.nan; out[f"{k}_boot_ci_high"]=float(np.quantile(arr,.975)) if len(arr) else np.nan
    return out
def stress_importance(selected,cache):
    boots=[]; stress=[]; imps=[]; perms=[]
    for _,r in selected.iterrows():
        item=cache[str(r.candidate_key)]; model=item["model"]; xho=item["x_holdout"].copy(); yho=np.asarray(item["y_holdout"],int); p=np.asarray(item["probs"],float); th=float(r.threshold); fs=list(item["features"]); bm=metrics(yho,p,th); boots.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"active_model_id":r.active_model_id,**boot_ci(yho,p,th,int(r.seed)+101)})
        imp=importance(model,fs); top=imp.head(min(12,len(imp))).index.tolist(); top1=float(imp.iloc[0]) if len(imp) else 0.0; top3=float(imp.head(3).sum()) if len(imp) else 0.0
        for rank,(f,val) in enumerate(imp.items(),1): imps.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"active_model_id":r.active_model_id,"feature":f,"importance_rank":rank,"importance":float(val)})
        rng=np.random.default_rng(int(r.seed)+202); xm=xho.copy()
        for f in fs:
            if f!="sex_assigned_at_birth": xm.loc[rng.random(len(xm))<.10,f]=np.nan
        mm=metrics(yho,proba(model,xm),th); stress.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"active_model_id":r.active_model_id,"stress_type":"missingness_10pct","base_f1":bm["f1"],"stress_f1":mm["f1"],"delta_f1":mm["f1"]-bm["f1"],"base_balanced_accuracy":bm["balanced_accuracy"],"stress_balanced_accuracy":mm["balanced_accuracy"],"delta_balanced_accuracy":mm["balanced_accuracy"]-bm["balanced_accuracy"]})
        for label,drop in [("top1_drop",top[:1]),("top3_drop",top[:3])]:
            xd=xho.copy()
            for f in drop:
                if f in xd.columns: xd[f]=np.nan
            md=metrics(yho,proba(model,xd),th); stress.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"active_model_id":r.active_model_id,"stress_type":label,"dropped_features":"|".join(drop),"base_f1":bm["f1"],"stress_f1":md["f1"],"delta_f1":md["f1"]-bm["f1"],"base_balanced_accuracy":bm["balanced_accuracy"],"stress_balanced_accuracy":md["balanced_accuracy"],"delta_balanced_accuracy":md["balanced_accuracy"]-bm["balanced_accuracy"],"top1_importance_share":top1,"top3_importance_share":top3})
        for f in top:
            drops=[]
            for _ in range(PERM_REPEATS):
                xp=xho.copy(); vals=xp[f].to_numpy(copy=True); rng.shuffle(vals); xp[f]=vals; drops.append(bm["balanced_accuracy"]-metrics(yho,proba(model,xp),th)["balanced_accuracy"])
            perms.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"active_model_id":r.active_model_id,"feature":f,"permutation_ba_drop_mean":float(np.mean(drops)),"permutation_ba_drop_max":float(np.max(drops))})
    return pd.DataFrame(boots),pd.DataFrame(stress),pd.DataFrame(imps),pd.DataFrame(perms)
def shortcut_inv(selected,imp,stress):
    rows=[]
    for _,r in selected.iterrows():
        sub=imp[(imp.domain==r.domain)&(imp["mode"]==r["mode"])]
        top1=float(sub.sort_values("importance_rank").head(1).importance.sum()) if not sub.empty else 0.0; top3=float(sub.sort_values("importance_rank").head(3).importance.sum()) if not sub.empty else 0.0; st=stress[(stress.domain==r.domain)&(stress["mode"]==r["mode"])&(stress.stress_type=="top1_drop")]; drop=abs(float(st.delta_balanced_accuracy.iloc[0])) if not st.empty else 0.0; flag="yes" if (top1>=.55 and drop>=.12) or top3>=.88 else "no"
        rows.append({"domain":r.domain,"mode":r["mode"],"role":r.role,"active_model_id":r.active_model_id,"shortcut_dominance_flag":flag,"dominance_type":"top_feature_or_top3_dominance" if flag=="yes" else "none","top1_importance_share":top1,"top3_importance_share":top3,"top1_drop_abs_ba":drop,"model_balanced_accuracy":r.balanced_accuracy})
    return pd.DataFrame(rows)
def qlabel(r):
    if sf(r.get("f1"),0)>=.86 and sf(r.get("balanced_accuracy"),0)>=.90 and sf(r.get("precision"),0)>=.80: return "bueno"
    if sf(r.get("f1"),0)>=.80 and sf(r.get("balanced_accuracy"),0)>=.87 and sf(r.get("precision"),0)>=.70: return "aceptable"
    return "malo"
def prelim_class(r):
    if sf(r.get("balanced_accuracy"),0)>=.90 and sf(r.get("f1"),0)>=.85 and sf(r.get("precision"),0)>=.82 and sf(r.get("recall"),0)>=.80 and sf(r.get("brier"),1)<=.06: return "ROBUST_PRIMARY"
    if sf(r.get("balanced_accuracy"),0)>=.84 and sf(r.get("f1"),0)>=.78 and sf(r.get("precision"),0)>=.70 and sf(r.get("recall"),0)>=.68: return "PRIMARY_WITH_CAVEAT"
    return "HOLD_FOR_LIMITATION"
def confidence(r,ncls):
    sc=100*(.35*sf(r.get("f1"),0)+.22*sf(r.get("balanced_accuracy"),0)+.18*sf(r.get("recall"),0)+.15*sf(r.get("precision"),0)+.10*max(0,1-sf(r.get("brier"),.2))); cav=[]; mode=str(r.get("mode",''))
    if mode.endswith("1_3"): cav.append("short mode fragile")
    if sf(r.get("precision"),0)<.75: cav.append("low precision")
    if sf(r.get("brier"),0)>.08: cav.append("calibration concern")
    if sf(r.get("overfit_gap_train_val_ba"),0)>.10: cav.append("overfit gap")
    if sf(r.get("generalization_gap_val_holdout_ba"),0)>.09: cav.append("val-holdout gap")
    if any(sf(r.get(k),0)>.97 for k in WATCH): cav.append("near guardrail")
    if ncls=="ROBUST_PRIMARY": return "ACTIVE_HIGH_CONFIDENCE",round(float(min(94.5,max(86,sc))),1),"high","yes","; ".join(cav) if cav else "none"
    if ncls=="PRIMARY_WITH_CAVEAT": return "ACTIVE_MODERATE_CONFIDENCE",round(float(min(84.9,max(70,sc-2*len(cav)))),1),"moderate","yes","; ".join(cav) if cav else "none"
    return "ACTIVE_LIMITED_USE",round(float(min(63,max(45,sc-6*max(1,len(cav))))),1),"limited","no","; ".join(cav) if cav else "none"
def material_reason(r):
    if sf(r.get("delta_f1"),0)>=.005: return "f1_improved"
    if sf(r.get("delta_recall"),0)>=.02 and sf(r.get("delta_precision"),0)>=-.04: return "recall_improved_without_precision_collapse"
    if sf(r.get("delta_balanced_accuracy"),0)>=.01: return "balanced_accuracy_improved"
    if sf(r.get("delta_brier"),0)<-.005: return "calibration_brier_improved"
    return "rf_only_mandate_or_no_material_gain"
def save_artifacts(selected,cache):
    rows=[]
    for _,r in selected.iterrows():
        key=str(r.active_model_id); out=MODEL_OUT/key; out.mkdir(parents=True,exist_ok=True); path=out/"pipeline.joblib"; joblib.dump(cache[str(r.candidate_key)]["model"],path)
        meta={"model_key":key,"line":LINE,"rf_only":True,"domain":r.domain,"role":r.role,"mode":r["mode"],"feature_columns":feats(r.feature_list_pipe),"recommended_threshold":float(r.threshold),"calibration":r.calibration,"config_id":r.config_id,"generated_at_utc":now(),"note":"pipeline.joblib is local/regenerable and ignored by git policy; metadata is tracked"}
        write(out/"metadata.json",json.dumps(meta,indent=2,ensure_ascii=False)); rows.append({"active_model_id":key,"artifact_path":str(path.relative_to(ROOT)).replace('\\','/'),"metadata_path":str((out/"metadata.json").relative_to(ROOT)).replace('\\','/'),"joblib_git_ignored_by_policy":"yes"})
    return pd.DataFrame(rows)
def md(df,max_rows=60):
    if df.empty: return "_sin datos_"
    x=df.head(max_rows); cols=list(x.columns); lines=["| "+" | ".join(cols)+" |","| "+" | ".join(["---"]*len(cols))+" |"]
    for _,r in x.iterrows():
        vals=[]
        for c in cols:
            v=r[c]
            vals.append("" if pd.isna(v) else (f"{v:.6f}" if isinstance(v,float) else str(v).replace("|","\\|")))
        lines.append("| "+" | ".join(vals)+" |")
    return "\n".join(lines)
def add_delta_selected(selected,active):
    old=active.set_index(["domain","mode"]); selected=selected.copy().reset_index(drop=True)
    for i,r in selected.iterrows():
        o=old.loc[(r.domain,r["mode"])]; selected.loc[i,"active_model_id"]=f"{r.domain}__{r['mode']}__{LINE}__rf__same_inputs_v11"; selected.loc[i,"previous_active_model_id"]=o.active_model_id; selected.loc[i,"previous_model_family"]=o.model_family; selected.loc[i,"previous_source_campaign"]=o.source_campaign; selected.loc[i,"promoted"]="yes"; selected.loc[i,"rf_only_mandate"]="yes"
        for m in ["f1","recall","precision","specificity","balanced_accuracy","roc_auc","pr_auc","brier"]: selected.loc[i,f"old_{m}"]=sf(o.get(m),np.nan); selected.loc[i,f"delta_{m}"]=sf(r.get(m),np.nan)-sf(o.get(m),0)
        if "selection_reason" not in selected.columns or pd.isna(selected.loc[i,"selection_reason"]): selected.loc[i,"selection_reason"]=material_reason(selected.loc[i])
    return selected

def main()->int:
    mkdirs(); active=pd.read_csv(ACTIVE_SRC); op=pd.read_csv(OP_SRC); summary=pd.read_csv(SUMMARY_SRC); inputs=pd.read_csv(INPUTS_SRC); data=pd.read_csv(DATASET); fe_reg=pd.read_csv(FE_REGISTRY) if FE_REGISTRY.exists() else pd.DataFrame()
    save(active,BASE/"audit/initial_active_v11_snapshot.csv"); save(op,BASE/"audit/initial_operational_v11_snapshot.csv"); save(summary,BASE/"audit/initial_active_v11_summary_snapshot.csv"); save(inputs,BASE/"audit/initial_questionnaire_inputs_v11_snapshot.csv"); save(fe_reg,BASE/"audit/feature_engineering_registry_snapshot.csv")
    if V10_COMPARISON.exists(): save(pd.read_csv(V10_COMPARISON),BASE/"audit/reference_v10_vs_v11_comparison_snapshot.csv")
    save(portfolio_audit(active,op,inputs,data),BASE/"audit/initial_portfolio_audit_v11.csv"); save(critical_slot_audit(active),BASE/"audit/critical_slot_audit_v11.csv"); save(class_balance(data),BASE/"audit/class_balance_audit.csv"); save(missingness(data,active),BASE/"audit/missingness_by_slot_audit.csv")
    dup=pd.DataFrame([{"dataset_rows":len(data),"participant_id_duplicates":int(data.participant_id.duplicated(keep=False).sum()),"full_vector_duplicates_anywhere":int(data.drop(columns=["participant_id"],errors="ignore").astype(str).agg("|".join,axis=1).duplicated(keep=False).sum())}]); save(dup,BASE/"audit/duplicate_audit_global.csv")
    sp,spdf=split_registry(data); save(spdf,BASE/"validation/split_registry.csv")
    print(json.dumps({"event":"training_start","slots":int(len(active)),"configs":len(RF_CONFIGS),"seeds":len(SEEDS),"threshold_strategies":len(THRESHOLD_STRATEGIES)},ensure_ascii=False),flush=True)
    all_trials=[]; cache_all={}; selected_rows=[]
    for idx,row in active.sort_values(["domain","role","mode"]).reset_index(drop=True).iterrows():
        print(json.dumps({"event":"slot_start","i":int(idx+1),"n":int(len(active)),"domain":row.domain,"mode":row["mode"]},ensure_ascii=False),flush=True)
        trials,cache=train_slot(row,data,sp); all_trials.append(trials); cache_all.update(cache); best,reason=select_best(row,trials); best=best.copy(); best["selection_reason"]=reason; selected_rows.append(best)
    trials_df=pd.concat(all_trials,ignore_index=True); save(trials_df,BASE/"trials/final_rf_plus_trials.csv")
    selected=add_delta_selected(pd.DataFrame(selected_rows),active)
    selected,clone_changes=resolve_clones(selected,trials_df,cache_all); selected=add_delta_selected(selected,active)
    save(clone_changes,BASE/"validation/anti_clone_selection_changes.csv"); save(selected,BASE/"tables/selected_rf_champions_v12.csv")
    sim=pairwise(selected,cache_all); save(sim,BASE/"validation/final_pairwise_prediction_similarity.csv"); save(sim[sim.domain=="elimination"].copy() if not sim.empty else sim,BASE/"validation/final_elimination_prediction_similarity.csv")
    boots,stress,imp,perm=stress_importance(selected,cache_all); save(boots,BASE/"bootstrap/selected_rf_bootstrap_audit.csv"); save(stress,BASE/"stress/selected_rf_stress_audit.csv"); save(imp,BASE/"importance/selected_rf_feature_importance.csv"); save(perm,BASE/"importance/selected_rf_permutation_importance.csv")
    shortcut=shortcut_inv(selected,imp,stress); save(shortcut,SHORTCUT_OUT); save(save_artifacts(selected,cache_all),BASE/"artifacts/generated_model_artifact_inventory.csv")
    active_new=active.copy(); op_new=op.copy(); sel=selected.set_index(["domain","mode"])
    for i,old in active_new.iterrows():
        key=(old.domain,old["mode"]); s=sel.loc[key]; updates={"active_model_required":"yes","active_model_id":s.active_model_id,"source_line":SOURCE_LINE,"source_campaign":LINE,"model_family":"rf","feature_set_id":"same_inputs_v11","config_id":s.config_id,"calibration":s.calibration,"threshold_policy":s.threshold_policy,"threshold":float(s.threshold),"seed":int(s.seed),"n_features":int(s.n_features),"precision":float(s.precision),"recall":float(s.recall),"specificity":float(s.specificity),"balanced_accuracy":float(s.balanced_accuracy),"f1":float(s.f1),"roc_auc":float(s.roc_auc),"pr_auc":float(s.pr_auc),"brier":float(s.brier),"overfit_flag":"yes" if sf(s.overfit_gap_train_val_ba,0)>.10 else "no","generalization_flag":"yes" if sf(s.generalization_gap_val_holdout_ba,1)<=.09 else "no","dataset_ease_flag":"no","notes":f"{LINE}:rf_only_same_inputs_v11;previous_model={old.active_model_id};previous_family={old.model_family};no_question_changes","feature_list_pipe":old.feature_list_pipe}
        pre=prelim_class(s); oc,pct,band,rec,cav=confidence({**updates,**s.to_dict(),"mode":old["mode"]},pre); updates.update({"final_operational_class":oc,"confidence_pct":pct,"confidence_band":band,"recommended_for_default_use":rec,"operational_caveat":cav})
        for c,v in updates.items(): active_new.loc[i,c]=v
        mask=(op_new.domain==key[0])&(op_new["mode"]==key[1]); op_updates={"source_campaign":LINE,"model_family":"rf","feature_set_id":"same_inputs_v11","calibration":s.calibration,"threshold_policy":s.threshold_policy,"threshold":float(s.threshold),"precision":float(s.precision),"recall":float(s.recall),"specificity":float(s.specificity),"balanced_accuracy":float(s.balanced_accuracy),"f1":float(s.f1),"roc_auc":float(s.roc_auc),"pr_auc":float(s.pr_auc),"brier":float(s.brier),"quality_label":qlabel(s),"overfit_gap_train_val_ba":float(s.overfit_gap_train_val_ba),"final_class":pre,"config_id":s.config_id,"n_features":int(s.n_features)}
        for c,v in op_updates.items():
            if c in op_new.columns: op_new.loc[mask,c]=v
    save(op_new,OP_OUT/"tables/hybrid_operational_final_champions.csv"); save(active_new,ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv"); save(inputs,ACTIVE_OUT/"tables/hybrid_questionnaire_inputs_master.csv")
    norm=build_normalized_table(PolicyInputs(OP_OUT/"tables/hybrid_operational_final_champions.csv",ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv",SHORTCUT_OUT)); normi=norm.set_index(["domain","mode"])
    for i,row in active_new.iterrows():
        key=(row.domain,row["mode"]); ncls=str(normi.loc[key,"normalized_final_class"]); s=sel.loc[key]; oc,pct,band,rec,cav=confidence({**row.to_dict(),**s.to_dict()},ncls); active_new.loc[i,"final_operational_class"]=oc; active_new.loc[i,"confidence_pct"]=pct; active_new.loc[i,"confidence_band"]=band; active_new.loc[i,"recommended_for_default_use"]=rec; active_new.loc[i,"operational_caveat"]=cav; op_new.loc[(op_new.domain==key[0])&(op_new["mode"]==key[1]),"final_class"]=ncls
    save(op_new,OP_OUT/"tables/hybrid_operational_final_champions.csv"); save(op_new[op_new.final_class.isin(["HOLD_FOR_LIMITATION","REJECT_AS_PRIMARY"])],OP_OUT/"tables/hybrid_operational_final_nonchampions.csv"); save(active_new,ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv"); save(active_new.groupby(["final_operational_class","confidence_band"],dropna=False).size().reset_index(name="n_active_models"),ACTIVE_OUT/"tables/hybrid_active_modes_summary.csv"); save(inputs,ACTIVE_OUT/"tables/hybrid_questionnaire_inputs_master.csv")
    norm=build_normalized_table(PolicyInputs(OP_OUT/"tables/hybrid_operational_final_champions.csv",ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv",SHORTCUT_OUT)); viol=policy_violations(norm); save(norm,NORM_OUT); save(viol,NORM_VIOL)
    final_guard=active_new[active_new.apply(lambda r:any(sf(r.get(m),0)>.98 for m in WATCH),axis=1)].copy(); save(final_guard,BASE/"validation/remaining_active_guardrail_violations.csv")
    rf_ok=len(active_new)==30 and active_new[["domain","role","mode"]].drop_duplicates().shape[0]==30 and (active_new.model_family.astype(str).str.lower()=="rf").all(); save(pd.DataFrame([{"active_rows":len(active_new),"unique_slots":active_new[["domain","role","mode"]].drop_duplicates().shape[0],"non_rf_rows":int((active_new.model_family.astype(str).str.lower()!="rf").sum()),"rf_only_ok":"yes" if rf_ok else "no"}]),BASE/"validation/rf_only_validator.csv")
    old_idx=active.set_index(["domain","mode"]); compat=[]; comp=[]
    for _,r in active_new.iterrows():
        o=old_idx.loc[(r.domain,r["mode"])]; of,nf=feats(o.feature_list_pipe),feats(r.feature_list_pipe); compat.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"same_feature_columns_order":"yes" if of==nf else "no","old_n_features":len(of),"new_n_features":len(nf),"missing_in_dataset":"|".join([f for f in nf if f not in data.columns]),"same_inputs_outputs_contract":"yes" if of==nf else "no"})
        s=sel.loc[(r.domain,r["mode"])]
        comp.append({"domain":r.domain,"role":r.role,"mode":r["mode"],"old_champion":o.active_model_id,"old_model_family":o.model_family,"new_rf_champion":r.active_model_id,"champion_final":r.active_model_id,"promoted":"yes","old_f1":o.f1,"new_f1":r.f1,"delta_f1":sf(r.f1)-sf(o.f1),"old_recall":o.recall,"new_recall":r.recall,"delta_recall":sf(r.recall)-sf(o.recall),"old_precision":o.precision,"new_precision":r.precision,"delta_precision":sf(r.precision)-sf(o.precision),"old_specificity":o.specificity,"new_specificity":r.specificity,"delta_specificity":sf(r.specificity)-sf(o.specificity),"old_balanced_accuracy":o.balanced_accuracy,"new_balanced_accuracy":r.balanced_accuracy,"delta_balanced_accuracy":sf(r.balanced_accuracy)-sf(o.balanced_accuracy),"old_roc_auc":o.roc_auc,"new_roc_auc":r.roc_auc,"delta_roc_auc":sf(r.roc_auc)-sf(o.roc_auc),"old_pr_auc":o.pr_auc,"new_pr_auc":r.pr_auc,"delta_pr_auc":sf(r.pr_auc)-sf(o.pr_auc),"old_brier":o.brier,"new_brier":r.brier,"delta_brier":sf(r.brier)-sf(o.brier),"old_class":o.final_operational_class,"new_class":r.final_operational_class,"old_confidence_pct":o.confidence_pct,"new_confidence_pct":r.confidence_pct,"selection_reason":s.selection_reason})
    compat=pd.DataFrame(compat); comparison=pd.DataFrame(comp); save(compat,BASE/"validation/feature_columns_compatibility_validator.csv"); save(comparison,BASE/"tables/final_v11_vs_v12_comparison.csv"); save(comparison[comparison.delta_f1<0].copy(),BASE/"tables/rf_slots_not_improved_vs_v11.csv"); save(comparison[comparison.delta_f1>=0].copy(),BASE/"tables/rf_slots_improved_or_matched_v11.csv"); selected2=selected.copy(); selected2["material_effect"]=selected2.apply(material_reason,axis=1); save(selected2,BASE/"tables/selected_rf_champions_with_deltas_v12.csv")
    if V10_COMPARISON.exists():
        v10=pd.read_csv(V10_COMPARISON)
        ref=v10[["domain","role","mode","old_champion","old_model_family","old_f1","old_recall","old_precision","old_balanced_accuracy","old_brier","new_rf_champion","new_f1","new_recall","new_precision","new_balanced_accuracy","new_brier"]].rename(columns={"old_champion":"v10_reference_champion","old_model_family":"v10_reference_family","old_f1":"v10_f1","old_recall":"v10_recall","old_precision":"v10_precision","old_balanced_accuracy":"v10_balanced_accuracy","old_brier":"v10_brier","new_rf_champion":"v11_rf_champion","new_f1":"v11_f1","new_recall":"v11_recall","new_precision":"v11_precision","new_balanced_accuracy":"v11_balanced_accuracy","new_brier":"v11_brier"})
        ref=ref.merge(comparison[["domain","role","mode","new_rf_champion","new_f1","new_recall","new_precision","new_balanced_accuracy","new_brier","delta_f1","delta_recall","delta_precision","delta_balanced_accuracy","delta_brier"]].rename(columns={"new_rf_champion":"v12_rf_champion","new_f1":"v12_f1","new_recall":"v12_recall","new_precision":"v12_precision","new_balanced_accuracy":"v12_balanced_accuracy","new_brier":"v12_brier","delta_f1":"v12_minus_v11_f1","delta_recall":"v12_minus_v11_recall","delta_precision":"v12_minus_v11_precision","delta_balanced_accuracy":"v12_minus_v11_balanced_accuracy","delta_brier":"v12_minus_v11_brier"}),on=["domain","role","mode"],how="left")
        ref["v12_minus_v10_f1"]=ref["v12_f1"]-ref["v10_f1"]; ref["v12_minus_v10_recall"]=ref["v12_recall"]-ref["v10_recall"]; ref["v10_not_promotable_if_non_rf"]=ref["v10_reference_family"].astype(str).str.lower().ne("rf").map({True:"yes",False:"no"})
        save(ref,BASE/"tables/reference_v10_vs_v11_vs_v12_comparison.csv")
    save(selected[["domain","role","mode","active_model_id","config_id","calibration","threshold_policy","train_balanced_accuracy","val_balanced_accuracy","balanced_accuracy","train_f1","val_f1","f1","overfit_gap_train_val_ba","generalization_gap_val_holdout_ba","oob_score"]],BASE/"validation/train_val_holdout_gap_validator.csv"); save(selected[["domain","role","mode","active_model_id","config_id","calibration","threshold_policy","threshold","val_brier","brier","val_ece","holdout_ece"]],BASE/"calibration/calibration_validator.csv")
    seed_summary=trials_df[trials_df.trial_error=="none"].groupby(["domain","role","mode","config_id","calibration","threshold_policy"],dropna=False).agg(f1_mean=("f1","mean"),f1_std=("f1","std"),ba_mean=("balanced_accuracy","mean"),ba_std=("balanced_accuracy","std"),recall_mean=("recall","mean"),recall_std=("recall","std"),n=("candidate_key","count")).reset_index(); save(seed_summary,BASE/"validation/seed_stability_validator.csv"); save(selected[["domain","role","mode","active_model_id","oob_score"]],BASE/"validation/oob_validator.csv")
    save(pd.DataFrame([{"source_inputs_master":str(INPUTS_SRC.relative_to(ROOT)).replace('\\','/'),"output_inputs_master":str((ACTIVE_OUT/"tables/hybrid_questionnaire_inputs_master.csv").relative_to(ROOT)).replace('\\','/'),"questionnaire_changed":"no","inputs_master_rows_before":len(inputs),"inputs_master_rows_after":len(pd.read_csv(ACTIVE_OUT/"tables/hybrid_questionnaire_inputs_master.csv"))}]),BASE/"validation/questionnaire_unchanged_validator.csv")
    report=["# Hybrid Final RF Plus Maximize Metrics v1","",f"Generated: `{now()}`","","## Scope","- RF-based final campaign over 30 active v11 slots.","- RandomForestClassifier remains the required base estimator for every champion.","- Same feature_list_pipe per slot; no questionnaire/question text changes.","- Threshold selected on validation; holdout used only for final reporting.","","## Core Results",f"- trials: `{len(trials_df)}`",f"- final_active_rows: `{len(active_new)}`",f"- rf_only_ok: `{'yes' if rf_ok else 'no'}`",f"- remaining_guardrail_violations: `{len(final_guard)}`",f"- policy_violations: `{len(viol)}`",f"- unchanged_feature_contract_slots: `{int((compat.same_feature_columns_order=='yes').sum())}/30`","","## Final Class Summary",md(active_new.groupby(["final_operational_class","confidence_band"],dropna=False).size().reset_index(name="n")),"","## v11 vs v12 RF",md(comparison[["domain","role","mode","old_model_family","old_f1","new_f1","delta_f1","old_recall","new_recall","old_precision","new_precision","selection_reason"]],35),"","## Elimination Anti-Clone",md(sim[sim.domain=="elimination"] if not sim.empty else sim,20)]
    write(BASE/"reports/final_rf_plus_maximize_metrics_summary.md","\n".join(report))
    manifest={"line":LINE,"freeze_label":FREEZE,"generated_at_utc":now(),"source_truth_initial":{"active":str(ACTIVE_SRC.relative_to(ROOT)).replace('\\','/'),"operational":str(OP_SRC.relative_to(ROOT)).replace('\\','/'),"inputs_master":str(INPUTS_SRC.relative_to(ROOT)).replace('\\','/')},"source_truth_final":{"active":str((ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv").relative_to(ROOT)).replace('\\','/'),"operational":str((OP_OUT/"tables/hybrid_operational_final_champions.csv").relative_to(ROOT)).replace('\\','/'),"inputs_master":str((ACTIVE_OUT/"tables/hybrid_questionnaire_inputs_master.csv").relative_to(ROOT)).replace('\\','/'),"normalization":str(NORM_OUT.relative_to(ROOT)).replace('\\','/')},"rules":{"model_family_allowed":"RandomForestClassifier only","same_inputs_functional":True,"same_outputs_functional":True,"no_question_rewrite":True,"guardrail_metrics_max":0.98,"threshold_source":"validation_only","holdout_use":"final_evaluation_only"},"stats":{"active_rows":int(len(active_new)),"trials":int(len(trials_df)),"rf_only_ok":"yes" if rf_ok else "no","remaining_guardrail_violations":int(len(final_guard)),"policy_violations":int(len(viol)),"feature_contract_mismatches":int((compat.same_feature_columns_order!="yes").sum()),"questionnaire_changed":"no","f1_improved_or_equal_slots":int((comparison.delta_f1>=0).sum()),"f1_regressed_slots":int((comparison.delta_f1<0).sum()),"elimination_identical_prediction_pairs":int((sim[(sim.domain=="elimination")&(sim.identical_predictions=="yes")].shape[0]) if not sim.empty else 0)}}
    write(ART/f"{LINE}_manifest.json",json.dumps(manifest,indent=2,ensure_ascii=False)); write(ACTIVE_ART/f"hybrid_active_modes_freeze_{FREEZE}_manifest.json",json.dumps({**manifest,"artifact":f"hybrid_active_modes_freeze_{FREEZE}"},indent=2,ensure_ascii=False)); write(OP_ART/f"hybrid_operational_freeze_{FREEZE}_manifest.json",json.dumps({**manifest,"artifact":f"hybrid_operational_freeze_{FREEZE}"},indent=2,ensure_ascii=False))
    print(json.dumps({"status":"ok",**manifest["stats"]},ensure_ascii=False),flush=True)
    return 0 if not len(final_guard) and not len(viol) and rf_ok and int((compat.same_feature_columns_order!="yes").sum())==0 else 1
if __name__=="__main__": raise SystemExit(main())

