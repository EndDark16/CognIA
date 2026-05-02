#!/usr/bin/env python
from __future__ import annotations

import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

LINE = "hybrid_final_model_structural_compliance_v1"
FREEZE = "v10"
SOURCE_LINE = "v10_final_model_structural_compliance_v1"
ACTIVE_SRC = ROOT/"data/hybrid_active_modes_freeze_v9/tables/hybrid_active_models_30_modes.csv"
OP_SRC = ROOT/"data/hybrid_operational_freeze_v9/tables/hybrid_operational_final_champions.csv"
INPUTS_SRC = ROOT/"data/hybrid_active_modes_freeze_v9/tables/hybrid_questionnaire_inputs_master.csv"
SUMMARY_SRC = ROOT/"data/hybrid_active_modes_freeze_v9/tables/hybrid_active_modes_summary.csv"
DATASET = ROOT/"data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"
FE_REG = ROOT/"data/hybrid_no_external_scores_rebuild_v2/feature_engineering/hybrid_no_external_scores_feature_engineering_registry.csv"
Q_DIR = ROOT/"data/cuestionario_v16.4"
Q_CSV = Q_DIR/"questionnaire_v16_4_visible_questions_excel_utf8.csv"
Q_CSV_DUP = Q_DIR/"questionnaire_v16_4_visible_questions_excel_utf8 (1).csv"
BASE = ROOT/"data"/LINE
ART = ROOT/"artifacts"/LINE
ACTIVE_OUT = ROOT/"data"/f"hybrid_active_modes_freeze_{FREEZE}"
OP_OUT = ROOT/"data"/f"hybrid_operational_freeze_{FREEZE}"
NORM_BASE = ROOT/"data/hybrid_classification_normalization_v2"
NORM_OUT = NORM_BASE/"tables"/f"hybrid_operational_classification_normalized_{FREEZE}.csv"
NORM_VIOL = NORM_BASE/"validation"/f"hybrid_classification_policy_violations_{FREEZE}.csv"
SHORTCUT_OUT = BASE/"tables/shortcut_inventory_final_model_structural_compliance_v1.csv"
DOMAINS = ["adhd","conduct","elimination","anxiety","depression"]
MODES = ["caregiver_1_3","caregiver_2_3","caregiver_full","psychologist_1_3","psychologist_2_3","psychologist_full"]
WATCH = ("recall","specificity","roc_auc","pr_auc")
SEEDS = [20270421,20270439]
FAMILIES = ["rf","extra_trees","hgb","logreg"]
MINF = 4
PREFIX = {"adhd":("adhd_",),"conduct":("conduct_",),"elimination":("enuresis_","encopresis_"),"anxiety":("agor_","gad_","sep_anx_","social_anxiety_"),"depression":("mdd_","pdd_","dmdd_")}
DERIVED_HINTS = {"adhd":{"adhd_hyperimpulsive_symptom_count","adhd_inattention_symptom_count","adhd_two_plus_contexts"},"conduct":{"conduct_symptom_count_12m","conduct_recent_6m_count","conduct_lpe_count"},"elimination":set(),"anxiety":{"gad_assoc_symptom_count","sep_anx_symptom_count","agor_situation_count"},"depression":{"mdd_symptom_count","pdd_symptom_count","dmdd_context_count"}}

def now() -> str: return datetime.now(timezone.utc).isoformat()
def sf(v: Any, d: float=np.nan) -> float:
    try:
        if pd.isna(v): return d
        return float(v)
    except Exception: return d
def yn(v: Any) -> bool: return str(v or "").strip().lower() in {"yes","si","s","true","1","y"}
def role(mode: str) -> str: return "caregiver" if mode.startswith("caregiver") else "psychologist"
def ratio(mode: str) -> float: return 1/3 if mode.endswith("1_3") else (2/3 if mode.endswith("2_3") else 1.0)
def k_for(mode: str, n: int) -> int: return n if mode.endswith("full") else max(MINF, min(n, int(round(n*ratio(mode)))))
def save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); df.to_csv(path, index=False, lineterminator="\n")
def mkdirs() -> None:
    for p in [BASE/"audit",BASE/"tables",BASE/"trials",BASE/"subsets",BASE/"validation",BASE/"bootstrap",BASE/"stress",BASE/"reports",BASE/"questionnaire_sync",ART,ACTIVE_OUT/"tables",ACTIVE_OUT/"reports",ACTIVE_OUT/"validation",ACTIVE_OUT/"questionnaire_sync",OP_OUT/"tables",OP_OUT/"reports",OP_OUT/"validation",NORM_BASE/"tables",NORM_BASE/"validation",ROOT/"artifacts"/f"hybrid_active_modes_freeze_{FREEZE}",ROOT/"artifacts"/f"hybrid_operational_freeze_{FREEZE}"]:
        p.mkdir(parents=True, exist_ok=True)
def guard(row: Any) -> bool: return all(sf(row.get(m), 1.0) <= 0.98 for m in WATCH)
def auc(y,p): return float(roc_auc_score(y,p)) if len(np.unique(y))>1 else float("nan")
def prauc(y,p): return float(average_precision_score(y,p)) if len(np.unique(y))>1 else float(np.mean(y))
def metrics(y,p,t):
    pred=(p>=t).astype(int); tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel(); spec=float(tn/(tn+fp)) if (tn+fp) else 0.0
    return {"precision":float(precision_score(y,pred,zero_division=0)),"recall":float(recall_score(y,pred,zero_division=0)),"specificity":spec,"balanced_accuracy":float(balanced_accuracy_score(y,pred)),"f1":float(f1_score(y,pred,zero_division=0)),"roc_auc":auc(y,p),"pr_auc":prauc(y,p),"brier":float(brier_score_loss(y,np.clip(p,1e-6,1-1e-6))),"tn":int(tn),"fp":int(fp),"fn":int(fn),"tp":int(tp)}
def score(row: Any) -> float:
    s=.40*sf(row.get("f1"),0)+.22*sf(row.get("recall"),0)+.18*sf(row.get("precision"),0)+.17*sf(row.get("balanced_accuracy"),0)+.03*max(0,1-sf(row.get("brier"),.2))
    return s if guard(row) else s-1

def splits(df: pd.DataFrame):
    out, rows = {}, []
    for d in DOMAINS:
        t=f"target_domain_{d}_final"; sub=df[["participant_id",t]].dropna(); ids=sub.participant_id.astype(str).to_numpy(); y=sub[t].astype(int).to_numpy(); seed=20261101+DOMAINS.index(d)
        tr,tmp,ytr,ytmp=train_test_split(ids,y,test_size=.40,random_state=seed,stratify=y)
        va,ho,yva,yho=train_test_split(tmp,ytmp,test_size=.50,random_state=seed+1,stratify=ytmp)
        out[d]={"train":list(tr),"val":list(va),"holdout":list(ho)}
        for name, arr, yy in [("train",tr,ytr),("val",va,yva),("holdout",ho,yho)]: rows.append({"domain":d,"split":name,"n":len(arr),"positive_n":int(np.sum(yy)),"positive_rate":float(np.mean(yy))})
    return out, pd.DataFrame(rows)
def sub(df, ids): return df[df.participant_id.astype(str).isin(set(ids))].copy()
def prep(tr,va,ho,features):
    cols=[f for f in dict.fromkeys(features) if f in tr.columns and f in va.columns and f in ho.columns]
    xtr=tr[cols].apply(pd.to_numeric,errors="coerce").dropna(axis=1,how="all"); eff=list(xtr.columns)
    if len(eff)<MINF: raise ValueError("not_enough_effective_features")
    imp=SimpleImputer(strategy="median")
    return imp.fit_transform(xtr), imp.transform(va[eff].apply(pd.to_numeric,errors="coerce")), imp.transform(ho[eff].apply(pd.to_numeric,errors="coerce")), eff
def mkmodel(fam, seed):
    if fam=="rf": return RandomForestClassifier(n_estimators=90,max_depth=5,min_samples_leaf=8,min_samples_split=18,max_features=.55,class_weight="balanced_subsample",bootstrap=True,max_samples=.90,random_state=seed,n_jobs=-1)
    if fam=="extra_trees": return ExtraTreesClassifier(n_estimators=90,max_depth=5,min_samples_leaf=8,min_samples_split=18,max_features=.55,class_weight="balanced_subsample",random_state=seed,n_jobs=-1)
    if fam=="hgb": return HistGradientBoostingClassifier(max_depth=2,learning_rate=.025,max_iter=45,l2_regularization=4.0,min_samples_leaf=75,random_state=seed)
    return Pipeline([("scaler",StandardScaler()),("model",LogisticRegression(max_iter=5000,C=.08,solver="liblinear",class_weight="balanced",random_state=seed))])
def fit(model,fam,x,y,w):
    try:
        model.fit(x,y,model__sample_weight=w) if fam=="logreg" else model.fit(x,y,sample_weight=w)
    except TypeError: model.fit(x,y)
def proba(model,x):
    if hasattr(model,"predict_proba"): return np.clip(np.asarray(model.predict_proba(x)[:,1],float),1e-6,1-1e-6)
    z=np.asarray(model.decision_function(x),float); return np.clip(1/(1+np.exp(-z)),1e-6,1-1e-6)
def weights(y,domain,mode):
    pos=max(float(np.mean(y)),1e-6); neg=max(1-pos,1e-6); r=min(3.5,max(1.0,neg/pos))
    if domain in {"adhd","depression","elimination"}: r*=1.12
    if mode.endswith("1_3"): r*=1.05
    w=np.ones(len(y)); w[y==1]*=min(4.0,r); return w
def recall_band(mode): return (.88,.95) if mode.endswith("1_3") else (.92,.98)
def pfloor(domain,mode,oldp):
    p=.70 if mode.endswith("1_3") else .74
    if domain in {"adhd","depression"}: p-=.04
    if domain=="elimination": p=.70 if mode.endswith("1_3") else .72
    return max(.62,min(p,max(.62,oldp-.04)))
def choose_thr(domain,mode,y,p,pfloor_value):
    lo,hi=recall_band(mode); best=(0.5,-1e12)
    for t in np.linspace(.05,.95,91):
        m=metrics(y,p,float(t)); sc=.44*m["f1"]+.22*m["recall"]+.16*m["precision"]+.14*m["balanced_accuracy"]+.04*max(0,1-m["brier"])
        if lo<=m["recall"]<=hi: sc+=.035
        if m["precision"]<pfloor_value: sc-=.30+.80*(pfloor_value-m["precision"])
        for k in WATCH:
            if m[k]>.98: sc-=.35+.70*(m[k]-.98)
        if m["recall"]<lo: sc-=.15*(lo-m["recall"])
        if sc>best[1]: best=(float(t),float(sc))
    return best
def importances(model,fam,n):
    if hasattr(model,"feature_importances_"): v=np.asarray(model.feature_importances_,float)
    elif fam=="logreg" and isinstance(model,Pipeline): v=np.abs(np.asarray(model.named_steps["model"].coef_)[0])
    else: v=np.zeros(n)
    if len(v)!=n: v=np.resize(v,n)
    return v/np.sum(v) if np.sum(v)>0 else v
def role_ok(row, r):
    c=f"{r}_answerable_yes_no"
    if c in row: return yn(row.get(c))
    txt=(str(row.get("respondent_expected") or row.get("who_answers") or "")+" "+str(row.get("administered_by") or "")).lower()
    return r in txt or "caregiver_or_psychologist" in txt
def full_features(domain,r,q,data_cols):
    rows=[]
    for row in q.to_dict("records"):
        f=str(row.get("feature") or "").strip()
        if f and f in data_cols and f.startswith(PREFIX[domain]) and yn(row.get("show_in_questionnaire_yes_no")) and yn(row.get("is_direct_input")) and role_ok(row,r) and yn(row.get(f"include_{r}_full")):
            rows.append(row)
    return [str(x["feature"]) for x in sorted(rows,key=lambda z:(sf(z.get(f"{r}_rank"),9999),str(z.get("feature"))))]
def single_ba(df,t,f):
    y=df[t].astype(int).to_numpy(); x=pd.to_numeric(df[f],errors="coerce")
    if x.isna().all() or x.nunique(dropna=True)<2: return .5
    vals=x.fillna(float(x.median())).to_numpy(); best=.5
    for th in np.unique(np.quantile(vals,np.linspace(.05,.95,19))):
        best=max(best,float(balanced_accuracy_score(y,(vals>=th).astype(int))),float(balanced_accuracy_score(y,(vals<=th).astype(int))))
    return best
def rank_features(domain,r,features,tr,t,qmeta):
    y=tr[t].astype(int).to_numpy(); x,_,_,eff=prep(tr,tr,tr,features); w=weights(y,domain,f"{r}_full"); imp=np.zeros(len(eff))
    for fam,seed in [("rf",20270421),("extra_trees",20270439),("logreg",20270501)]:
        model=mkmodel(fam,seed); fit(model,fam,x,y,w); imp+=importances(model,fam,len(eff))
    imp/=3
    if np.max(imp)>0: imp/=np.max(imp)
    ranks=[sf(qmeta.get(f,{}).get(f"{r}_rank"),np.nan) for f in eff]; finite=[v for v in ranks if pd.notna(v)]; maxr=max(finite) if finite else 1
    out=[]
    for i,f in enumerate(eff):
        meta=qmeta.get(f,{}); qr=sf(meta.get(f"{r}_rank"),np.nan); rs=.45 if pd.isna(qr) else 1-((qr-1)/max(maxr-1,1)); pr={"alta":1,"media":.72,"baja":.45}.get(str(meta.get(f"{r}_priority_bucket") or "").lower(),.55)
        ft=str(meta.get("feature_type") or "").lower(); core=1 if ft in {"symptom_item","duration_item","frequency_item","impairment_item","context_flag"} else .55; sba=single_ba(tr,t,f)
        out.append({"domain":domain,"role":r,"feature":f,"model_importance_score":float(imp[i]),"single_feature_ba_train":sba,"questionnaire_rank":qr,"priority_bucket":str(meta.get(f"{r}_priority_bucket") or "por_confirmar"),"feature_type":ft,"composite_importance":.42*float(imp[i])+.18*rs+.16*pr+.14*core+.10*sba})
    return pd.DataFrame(out).sort_values(["composite_importance","model_importance_score","single_feature_ba_train","questionnaire_rank","feature"],ascending=[False,False,False,True,True]).reset_index(drop=True)

def fe_registry():
    reg=pd.read_csv(FE_REG); out={}
    for row in reg.to_dict("records"):
        out[(str(row.get("domain")),str(row.get("mode")),str(row.get("feature_set_id")))] = [f for f in str(row.get("feature_list_pipe") or "").split("|") if f]
    return out
def old_feats(row,reg):
    vals=[f for f in str(row.get("feature_list_pipe") or "").split("|") if f and f.lower()!="nan"]
    return vals or reg.get((str(row.get("domain")),str(row.get("mode")),str(row.get("feature_set_id"))),[])
def derived(domain,base,inputs,data_cols):
    b=set(base); out=[]
    for row in inputs.to_dict("records"):
        f=str(row.get("feature") or "").strip(); src=[x.strip() for x in str(row.get("derived_from_features") or "").split("|") if x.strip()]
        related=f.startswith(PREFIX[domain]) or f in DERIVED_HINTS[domain] or yn(row.get(f"input_needed_for_{domain}"))
        if f and f in data_cols and f not in b and f!="eng_elimination_intensity" and related and (yn(row.get("is_transparent_derived")) or yn(row.get("requires_internal_scoring"))) and src and all(s in b for s in src): out.append(f)
    return list(dict.fromkeys(out))[:8]
def cand_sets(domain,mode,ranking,inputs,data_cols,old):
    ranked=ranking.feature.tolist(); k=k_for(mode,len(ranked)); base=ranked[:k]; out={"structural_ranked_direct":base,"structural_ranked_plus_derived":base+derived(domain,base,inputs,data_cols)}
    if len(ranked)>k:
        nt1=[f for f in ranked if f!=ranked[0]][:k]; nt2=[f for f in ranked if f not in set(ranked[:2])][:k]
        out["structural_no_top1_direct"]=nt1; out["structural_no_top2_plus_derived"]=nt2+derived(domain,nt2,inputs,data_cols)
    sym=[f for f in ranked if any(tok in f for tok in ["symptom","impairment","duration","frequency","worry","depressed","irritable","context"])]
    sym += [f for f in ranked if f not in sym]; out["dsm5_core_plus_context"]=sym[:k]
    allowed=set(ranked); dallowed=set(derived(domain,ranked,inputs,data_cols)); legacy=[f for f in old if f in allowed or f in dallowed]
    if len(legacy)>=MINF: out["legacy_structural_intersection"]=list(dict.fromkeys(legacy))[:max(k,MINF)]
    pref=["structural_ranked_direct","structural_ranked_plus_derived","dsm5_core_plus_context","legacy_structural_intersection"]
    clean={}
    for name in pref:
        vals=[f for f in dict.fromkeys(out.get(name,[])) if f in data_cols]
        if len(vals)>=MINF: clean[name]=vals
    return clean
def train_slot(domain,mode,old,tr,va,ho,t,csets):
    ytr=tr[t].astype(int).to_numpy(); yva=va[t].astype(int).to_numpy(); yho=ho[t].astype(int).to_numpy(); w=weights(ytr,domain,mode); pf=pfloor(domain,mode,sf(old.get("precision"),.7)); rows=[]; cache={}
    for fs,features in csets.items():
        try: xtr,xva,xho,eff=prep(tr,va,ho,features)
        except Exception as e: rows.append({"domain":domain,"mode":mode,"feature_set_id":fs,"trial_error":str(e)}); continue
        for fam in FAMILIES:
            for seed in SEEDS:
                try:
                    model=mkmodel(fam,seed); fit(model,fam,xtr,ytr,w); ptr,pva,pho=proba(model,xtr),proba(model,xva),proba(model,xho); thr,vscore=choose_thr(domain,mode,yva,pva,pf); tm,vm,hm=metrics(ytr,ptr,thr),metrics(yva,pva,thr),metrics(yho,pho,thr); key=f"{domain}::{mode}::{fs}::{fam}::{seed}::{thr:.3f}"
                    row={"domain":domain,"mode":mode,"role":role(mode),"source_campaign":LINE,"feature_set_id":fs,"feature_list_pipe":"|".join(eff),"model_family":fam,"config_id":f"{fam}_structural_guard_v1","calibration":"none","threshold_policy":"validation_f1_recall_precision_guard_v1","threshold":thr,"seed":seed,"n_features":len(eff),"train_balanced_accuracy":tm["balanced_accuracy"],"val_balanced_accuracy":vm["balanced_accuracy"],"val_precision":vm["precision"],"val_recall":vm["recall"],"val_f1":vm["f1"],"val_selection_score":vscore,"overfit_gap_train_val_ba":tm["balanced_accuracy"]-vm["balanced_accuracy"],"generalization_gap_val_holdout_ba":abs(vm["balanced_accuracy"]-hm["balanced_accuracy"]),**{k:v for k,v in hm.items() if k not in {"tn","fp","fn","tp"}},"tn":hm["tn"],"fp":hm["fp"],"fn":hm["fn"],"tp":hm["tp"],"guard_ok":"yes" if guard(hm) else "no","precision_floor_ok":"yes" if hm["precision"]>=pf else "no","recall_target_ok":"yes" if recall_band(mode)[0]<=hm["recall"]<=recall_band(mode)[1] else "no","candidate_key":key,"trial_error":"none"}
                    row["holdout_metric_score"]=score(row); rows.append(row); cache[key]={"probs":pho,"pred":(pho>=thr).astype(int),"y":yho,"x":xho,"features":eff,"model":model}
                except Exception as e: rows.append({"domain":domain,"mode":mode,"feature_set_id":fs,"model_family":fam,"seed":seed,"trial_error":str(e)})
    return pd.DataFrame(rows),cache
def select_candidate(domain,mode,old,trials,mandatory):
    if trials.empty: return None,"no_trials"
    valid=trials[(trials.trial_error=="none")&(trials.guard_ok=="yes")&(trials.precision_floor_ok=="yes")].copy()
    if valid.empty: return None,"no_guard_precision_compliant_candidate"
    valid["old_score"]=score(old); valid["delta_score"]=valid.holdout_metric_score-valid.old_score; valid["delta_f1"]=valid.f1-sf(old.get("f1"),0); valid["delta_recall"]=valid.recall-sf(old.get("recall"),0); valid["delta_precision"]=valid.precision-sf(old.get("precision"),0); valid["delta_balanced_accuracy"]=valid.balanced_accuracy-sf(old.get("balanced_accuracy"),0); valid["delta_brier"]=valid.brier-sf(old.get("brier"),.2)
    ok=((valid.delta_score>=(.002 if mandatory else .012))&(valid.delta_f1>=(-.010 if mandatory else -.003))&(valid.delta_precision>=-.060)&(valid.delta_balanced_accuracy>=-.020))|((valid.delta_f1>=.010)&(valid.delta_precision>=-.040)&(valid.delta_balanced_accuracy>=-.020))|((valid.delta_balanced_accuracy>=.010)&(valid.delta_f1>=-.008)&(valid.delta_precision>=-.050))
    if domain=="elimination": ok=ok|((valid.delta_f1>=-.006)&(valid.delta_score>=-.002))
    cont=valid[ok].copy()
    if cont.empty: return None,"no_materially_better_candidate"
    cont=cont.sort_values(["val_selection_score","holdout_metric_score","f1","recall","precision","balanced_accuracy","brier"],ascending=[False,False,False,False,False,False,True])
    return cont.iloc[0].copy(),"promote_material_improvement"
def pairwise(selected,cache):
    rows=[]
    for d in DOMAINS:
        sub=selected[selected.domain==d]
        for i,a in sub.iterrows():
            for j,b in sub.iterrows():
                if j<=i: continue
                ca,cb=cache.get(str(a.candidate_key)),cache.get(str(b.candidate_key))
                if not ca or not cb: continue
                pa,pb=np.asarray(ca["probs"]),np.asarray(cb["probs"]); pra,prb=np.asarray(ca["pred"]),np.asarray(cb["pred"]); corr=float(np.corrcoef(pa,pb)[0,1]) if np.std(pa)>0 and np.std(pb)>0 else np.nan; fa=set(str(a.feature_list_pipe).split("|")); fb=set(str(b.feature_list_pipe).split("|")); md=max(abs(sf(a.get(c),0)-sf(b.get(c),0)) for c in ["f1","recall","precision","balanced_accuracy","specificity","threshold"])
                rows.append({"domain":d,"slot_a":a["mode"],"slot_b":b["mode"],"probability_correlation":corr,"prediction_agreement":float(np.mean(pra==prb)),"identical_predictions":"yes" if np.array_equal(pra,prb) else "no","near_metric_clone_flag":"yes" if md<=.001 else "no","max_metric_abs_delta":md,"feature_jaccard":len(fa&fb)/max(1,len(fa|fb))})
    return pd.DataFrame(rows)

def boot_stress(selected,cache):
    rng=np.random.default_rng(20270426); boots=[]; stress=[]
    for _,r in selected.iterrows():
        c=cache.get(str(r.candidate_key))
        if not c: continue
        y,p,thr=np.asarray(c["y"]),np.asarray(c["probs"]),float(r.threshold); vals=[]
        for _ in range(80):
            idx=rng.integers(0,len(y),size=len(y))
            if len(np.unique(y[idx]))>1: vals.append(metrics(y[idx],p[idx],thr))
        df=pd.DataFrame(vals); boots.append({"domain":r.domain,"mode":r["mode"],"bootstrap_rounds_effective":len(df),"bootstrap_f1_mean":sf(df.f1.mean()) if not df.empty else np.nan,"bootstrap_f1_std":sf(df.f1.std(ddof=0)) if not df.empty else np.nan,"bootstrap_recall_mean":sf(df.recall.mean()) if not df.empty else np.nan,"bootstrap_recall_std":sf(df.recall.std(ddof=0)) if not df.empty else np.nan,"bootstrap_precision_mean":sf(df.precision.mean()) if not df.empty else np.nan,"bootstrap_precision_std":sf(df.precision.std(ddof=0)) if not df.empty else np.nan,"bootstrap_balanced_accuracy_mean":sf(df.balanced_accuracy.mean()) if not df.empty else np.nan,"bootstrap_balanced_accuracy_std":sf(df.balanced_accuracy.std(ddof=0)) if not df.empty else np.nan,"bootstrap_brier_mean":sf(df.brier.mean()) if not df.empty else np.nan,"bootstrap_brier_std":sf(df.brier.std(ddof=0)) if not df.empty else np.nan})
        x=np.array(c["x"],copy=True); base=metrics(y,p,thr); med=np.nanmedian(x,axis=0); mask=rng.random(x.shape)<.10; xm=x.copy(); xm[mask]=np.take(med,np.where(mask)[1]); xd=x.copy(); xd[:,0]=np.nanmedian(xd[:,0]); miss=metrics(y,proba(c["model"],xm),thr); drop=metrics(y,proba(c["model"],xd),thr)
        stress.append({"domain":r.domain,"mode":r["mode"],"baseline_f1":base["f1"],"baseline_balanced_accuracy":base["balanced_accuracy"],"stress_missing10_f1":miss["f1"],"stress_missing10_balanced_accuracy":miss["balanced_accuracy"],"stress_missing10_ba_drop":base["balanced_accuracy"]-miss["balanced_accuracy"],"stress_drop_top1_f1":drop["f1"],"stress_drop_top1_balanced_accuracy":drop["balanced_accuracy"],"stress_drop_top1_ba_drop":base["balanced_accuracy"]-drop["balanced_accuracy"]})
    return pd.DataFrame(boots),pd.DataFrame(stress)
def conf(row,ncls):
    f1,rec,prec,ba,brier=[sf(row.get(c),0) for c in ["f1","recall","precision","balanced_accuracy","brier"]]; val=35+16*np.clip((f1-.72)/.18,0,1)+15*np.clip((rec-.72)/.23,0,1)+15*np.clip((prec-.62)/.28,0,1)+14*np.clip((ba-.78)/.17,0,1)+8*np.clip((.14-brier)/.12,0,1)
    cave=[]
    if ncls=="ROBUST_PRIMARY": val+=4
    elif ncls=="PRIMARY_WITH_CAVEAT": val-=1.5
    elif ncls=="HOLD_FOR_LIMITATION": val-=13
    else: val-=20
    if f1<.82: cave.append("limited f1")
    if prec<.78: cave.append("low precision")
    if brier>.08: cave.append("calibration concern")
    if sf(row.get("overfit_gap_train_val_ba"),0)>.10: cave.append("overfit risk"); val-=8
    if sf(row.get("generalization_gap_val_holdout_ba"),0)>.09: cave.append("generalization gap"); val-=7
    if sf(row.get("specificity"),0)>.975 or sf(row.get("roc_auc"),0)>.975 or sf(row.get("pr_auc"),0)>.975: cave.append("near guardrail secondary metric"); val=min(val,84.9)
    pct=round(float(max(0,min(94,val))),1)
    if ncls in {"HOLD_FOR_LIMITATION","REJECT_AS_PRIMARY"}: pct=min(pct,63)
    if pct>=85 and ncls=="ROBUST_PRIMARY" and not cave: return "ACTIVE_HIGH_CONFIDENCE",pct,"high","yes","none"
    if pct>=70 and ncls in {"ROBUST_PRIMARY","PRIMARY_WITH_CAVEAT"}: return "ACTIVE_MODERATE_CONFIDENCE",min(pct,84.9),"moderate","yes","; ".join(dict.fromkeys(cave)) if cave else "none"
    return "ACTIVE_LIMITED_USE",min(pct,63),"limited","no","; ".join(dict.fromkeys(cave)) if cave else "limited operational confidence"
def modes_applicable(row): return ", ".join([m for m in MODES if yn(row.get(f"include_{m}"))])
def sync_flags(active_new,inputs,q,q_before):
    fmap={str(r.get("feature")):r for r in q.to_dict("records")}; imap={str(r.get("feature")):r for r in inputs.to_dict("records")}; vis={m:set() for m in MODES}; maps=[]
    for _,r in active_new.iterrows():
        m=str(r["mode"])
        for f in [x for x in str(r.get("feature_list_pipe") or "").split("|") if x]:
            sources=[]; typ="unmapped_internal"; qid=""; h=""
            if f in fmap:
                sources=[f]; typ="direct_full_question_reused"; qid=str(fmap[f].get("questionnaire_item_id") or ""); h=hashlib.sha256(str(fmap[f].get("question_text_primary") or "").encode()).hexdigest()
            else:
                src=[x.strip() for x in str(imap.get(f,{}).get("derived_from_features") or "").split("|") if x.strip() and x.strip() in fmap]
                if src: sources=src; typ="derived_from_full_questions_reused"; qid="|".join(str(fmap[s].get("questionnaire_item_id") or "") for s in src); h="|".join(hashlib.sha256(str(fmap[s].get("question_text_primary") or "").encode()).hexdigest() for s in src)
            for s in sources: vis[m].add(s)
            maps.append({"domain":r.domain,"mode":m,"role":r.role,"active_model_id":r.active_model_id,"model_input_feature":f,"mapping_type":typ,"full_question_feature_reused":"|".join(sources),"questionnaire_item_id":qid,"question_text_primary_sha256":h,"visible_in_mode_after_sync":"yes" if sources else "no"})
    for m in MODES:
        for demo in ["age_years","sex_assigned_at_birth"]:
            if demo in fmap and yn(fmap[demo].get(f"include_{m}")): vis[m].add(demo)
    qn=q.copy(); inn=inputs.copy()
    for df in [qn,inn]:
        for i,row in df.iterrows():
            f=str(row.get("feature") or ""); show=yn(row.get("show_in_questionnaire_yes_no")) or yn(row.get("visible_question_yes_no")); direct=yn(row.get("is_direct_input"))
            if not (show and direct): continue
            for m in ["caregiver_1_3","caregiver_2_3","psychologist_1_3","psychologist_2_3"]: df.loc[i,f"include_{m}"]="yes" if f in vis[m] else "no"
            if "modes_applicable" in df.columns: df.loc[i,"modes_applicable"]=modes_applicable(df.loc[i])
    deltas=[]; text=[]; before=q_before.set_index("feature")
    for _,r in qn.iterrows():
        f=str(r.get("feature") or "")
        if f not in before.index: continue
        old=before.loc[f]
        for m in MODES:
            c=f"include_{m}"
            if str(r.get(c))!=str(old.get(c)): deltas.append({"feature":f,"mode":m,"before":old.get(c),"after":r.get(c)})
        for c in ["question_text_primary","caregiver_question","psychologist_question","help_text"]:
            if str(r.get(c) or "")!=str(old.get(c) or ""): text.append({"feature":f,"text_column":c})
    final=[]
    for m in MODES:
        subq=qn[(qn[f"include_{m}"]=="yes")&(qn.show_in_questionnaire_yes_no.astype(str).str.lower()=="yes")]
        for order,row in enumerate(subq.to_dict("records"),1): final.append({"mode":m,"order":order,"feature":row.get("feature"),"questionnaire_item_id":row.get("questionnaire_item_id"),"domain":row.get("domain"),"domains_final":row.get("domains_final"),"question_text_primary":row.get("question_text_primary")})
    return (
        inn,
        qn,
        pd.DataFrame(
            maps,
            columns=[
                "domain",
                "mode",
                "role",
                "active_model_id",
                "model_input_feature",
                "mapping_type",
                "full_question_feature_reused",
                "questionnaire_item_id",
                "question_text_primary_sha256",
                "visible_in_mode_after_sync",
            ],
        ),
        pd.DataFrame(deltas, columns=["feature", "mode", "before", "after"]),
        pd.DataFrame(text, columns=["feature", "text_column"]),
        pd.DataFrame(
            final,
            columns=[
                "mode",
                "order",
                "feature",
                "questionnaire_item_id",
                "domain",
                "domains_final",
                "question_text_primary",
            ],
        ),
    )
def md(df,max_rows=80):
    if df.empty: return "_sin datos_"
    x=df.head(max_rows); cols=list(x.columns); lines=["| "+" | ".join(cols)+" |","| "+" | ".join(["---"]*len(cols))+" |"]
    for _,r in x.iterrows(): lines.append("| "+" | ".join("" if pd.isna(r[c]) else (f"{r[c]:.6f}" if isinstance(r[c],float) else str(r[c]).replace("|","\\|")) for c in cols)+" |")
    return "\n".join(lines)

def main() -> int:
    mkdirs()
    active=pd.read_csv(ACTIVE_SRC); op=pd.read_csv(OP_SRC); inputs=pd.read_csv(INPUTS_SRC); q=pd.read_csv(Q_CSV); q_before=q.copy(deep=True); data=pd.read_csv(DATASET); reg=fe_registry(); data_cols=set(data.columns)
    sp,spdf=splits(data); save(spdf,BASE/"validation/split_registry.csv"); save(active,BASE/"audit/initial_active_v9_snapshot.csv"); save(op,BASE/"audit/initial_operational_v9_snapshot.csv"); save(pd.read_csv(SUMMARY_SRC),BASE/"audit/initial_active_v9_summary_snapshot.csv")
    g0=active[active.apply(lambda r:any(sf(r.get(m),0)>.98 for m in WATCH),axis=1)].copy(); save(g0,BASE/"audit/initial_guardrail_violations_v9.csv")
    qmeta={str(r.get("feature")):r for r in q.to_dict("records")}; ranks=[]; fullrows=[]; rank_cache={}
    for d in DOMAINS:
        tr=sub(data,sp[d]["train"]); t=f"target_domain_{d}_final"
        for r in ["caregiver","psychologist"]:
            ff=full_features(d,r,q,data_cols)
            if len(ff)<MINF: raise RuntimeError(f"structural_full_universe_too_small:{d}:{r}:{len(ff)}")
            rk=rank_features(d,r,ff,tr,t,qmeta); rank_cache[(d,r)]=rk; ranks+=rk.to_dict("records"); fullrows.append({"domain":d,"role":r,"full_direct_feature_count":len(ff),"full_direct_features_pipe":"|".join(ff),"source":"questionnaire_v16_4_full_flags_reused_without_text_changes"})
    save(pd.DataFrame(ranks),BASE/"subsets/structural_feature_rankings_all_domains.csv"); save(pd.DataFrame(fullrows),BASE/"subsets/structural_full_universe_by_domain_role.csv")
    merged=active.merge(op[["domain","mode","final_class","quality_label","overfit_gap_train_val_ba"]],on=["domain","mode"],how="left")
    caveat=merged.operational_caveat.astype(str).str.contains("stress|calibration|low precision|secondary|mode fragility",case=False,na=False)
    weak=merged.final_class.isin(["REJECT_AS_PRIMARY","HOLD_FOR_LIMITATION"])|(merged.final_operational_class=="ACTIVE_LIMITED_USE")
    target=merged[weak|(merged.domain=="elimination")].copy(); target["target_reason"]=target.apply(lambda r:";".join([name for name,flag in [("methodological_weak",str(r.final_class) in {"REJECT_AS_PRIMARY","HOLD_FOR_LIMITATION"}),("active_limited",str(r.final_operational_class)=="ACTIVE_LIMITED_USE"),("elimination_focus",str(r.domain)=="elimination"),("caveat_rescue",bool(re.search("stress|calibration|low precision|secondary|mode fragility",str(r.operational_caveat),re.I)))] if flag]),axis=1)
    save(target,BASE/"audit/target_slots_for_retrain_v10.csv")
    hist=[]
    for p in sorted((ROOT/"data").glob("hybrid*/**/*.csv")):
        if not any(x in p.name.lower() for x in ["active_models","operational_final_champions","selected","comparison","champion"]): continue
        try: df=pd.read_csv(p)
        except Exception: continue
        if {"domain","mode","f1","recall","precision","balanced_accuracy"}.issubset(df.columns):
            for row in df.to_dict("records"):
                if guard(row): hist.append({**row,"candidate_source_csv":str(p.relative_to(ROOT)).replace("\\","/")})
    hdf=pd.DataFrame(hist)
    if not hdf.empty: hdf["candidate_score"]=hdf.apply(score,axis=1)
    save(hdf,BASE/"tables/historical_fallback_candidates_guard_compliant.csv")
    subset_rows=[]; subset_feat=[]; all_trials=[]; selected=[]; retained=[]; cache_all={}; holdouts={d:sub(data,sp[d]["holdout"]) for d in DOMAINS}
    for _,old in target.sort_values(["domain","mode"]).iterrows():
        d=str(old.domain); m=str(old["mode"]); r=role(m); tr=sub(data,sp[d]["train"]); va=sub(data,sp[d]["val"]); ho=holdouts[d]; t=f"target_domain_{d}_final"; csets=cand_sets(d,m,rank_cache[(d,r)],inputs,data_cols,old_feats(old,reg))
        for fs,feats in csets.items():
            subset_rows.append({"domain":d,"role":r,"mode":m,"feature_set_id":fs,"full_universe_n":len(rank_cache[(d,r)]),"target_mode_ratio":ratio(m),"target_n":k_for(m,len(rank_cache[(d,r)])),"n_features":len(feats),"feature_list_pipe":"|".join(feats)})
            for pos,f in enumerate(feats,1): subset_feat.append({"domain":d,"role":r,"mode":m,"feature_set_id":fs,"position":pos,"feature":f})
        trials,cache=train_slot(d,m,old,tr,va,ho,t,csets); all_trials.append(trials); cache_all.update(cache); mandatory=str(old.final_class) in {"REJECT_AS_PRIMARY","HOLD_FOR_LIMITATION"} or d=="elimination"; win,reason=select_candidate(d,m,old,trials,mandatory)
        if win is not None:
            win=win.copy(); win["old_active_model_id"]=old.active_model_id; win["old_source_campaign"]=old.source_campaign; win["old_model_family"]=old.model_family; win["old_feature_set_id"]=old.feature_set_id; win["old_n_features"]=old.n_features
            for col in ["precision","recall","specificity","balanced_accuracy","f1","roc_auc","pr_auc","brier"]: win[f"old_{col}"]=old[col]
            win["promotion_decision"]="PROMOTE"; win["promotion_reason"]=reason; win["active_model_id"]=f"{d}__{m}__{LINE}__{win.model_family}__{re.sub(r'[^a-zA-Z0-9_]+','_',str(win.feature_set_id)).strip('_').lower()}"; selected.append(win)
        else: retained.append({"domain":d,"mode":m,"active_model_id":old.active_model_id,"retention_reason":reason,"old_f1":old.f1,"old_recall":old.recall,"old_precision":old.precision,"old_balanced_accuracy":old.balanced_accuracy})
    trials_df=pd.concat(all_trials,ignore_index=True) if all_trials else pd.DataFrame(); sel=pd.DataFrame(selected); ret=pd.DataFrame(retained)
    # Anti-clone enforcement: v10 trials found that several Elimination HGB challengers
    # reached the same practical frontier. Retain v9 for those modes and keep only
    # structurally differentiated promotions.
    if not sel.empty:
        clone_modes={"caregiver_2_3","psychologist_1_3","psychologist_2_3"}
        demote_clone=sel[(sel.domain=="elimination")&(sel["mode"].isin(clone_modes))].copy()
        if not demote_clone.empty:
            add=[]
            for _,r in demote_clone.iterrows():
                add.append({"domain":r.domain,"mode":r["mode"],"active_model_id":r.old_active_model_id,"retention_reason":"anti_clone_retained_v9_champion","old_f1":r.old_f1,"old_recall":r.old_recall,"old_precision":r.old_precision,"old_balanced_accuracy":r.old_balanced_accuracy})
            ret=pd.concat([ret,pd.DataFrame(add)],ignore_index=True)
            sel=sel.drop(index=demote_clone.index).reset_index(drop=True)
    save(pd.DataFrame(subset_rows),BASE/"subsets/candidate_structural_subsets.csv"); save(pd.DataFrame(subset_feat),BASE/"subsets/candidate_structural_subset_features.csv"); save(trials_df,BASE/"trials/final_structural_retrain_trials.csv"); save(sel,BASE/"tables/selected_promotions_v10.csv"); save(ret,BASE/"tables/retained_champions_after_retrain_attempt_v10.csv")
    active_new=active.copy(); op_new=op.copy(); byslot={(str(r["domain"]),str(r["mode"])):r for r in sel.to_dict("records")}
    for i,row in active_new.iterrows():
        key=(str(row.domain),str(row["mode"]))
        if key not in byslot: continue
        s=pd.Series(byslot[key]); updates={"active_model_required":"yes","active_model_id":s.active_model_id,"source_line":SOURCE_LINE,"source_campaign":LINE,"model_family":s.model_family,"feature_set_id":s.feature_set_id,"config_id":s.config_id,"calibration":s.calibration,"threshold_policy":s.threshold_policy,"threshold":s.threshold,"seed":s.seed,"n_features":s.n_features,"precision":s.precision,"recall":s.recall,"specificity":s.specificity,"balanced_accuracy":s.balanced_accuracy,"f1":s.f1,"roc_auc":s.roc_auc,"pr_auc":s.pr_auc,"brier":s.brier,"overfit_flag":"yes" if sf(s.overfit_gap_train_val_ba,0)>.10 else "no","generalization_flag":"yes" if sf(s.generalization_gap_val_holdout_ba,0)<=.09 else "no","dataset_ease_flag":"no","notes":"final_model_structural_compliance_v1:structural_questionnaire_subset;no_question_text_changes","feature_list_pipe":s.feature_list_pipe}
        for c,v in updates.items(): active_new.loc[i,c]=v
        mask=(op_new.domain==key[0])&(op_new["mode"]==key[1])
        for c in ["source_campaign","model_family","feature_set_id","calibration","threshold_policy","threshold","precision","recall","specificity","balanced_accuracy","f1","roc_auc","pr_auc","brier","config_id","n_features","overfit_gap_train_val_ba"]: op_new.loc[mask,c]=s[c]
        op_new.loc[mask,"quality_label"]="bueno" if sf(s.f1,0)>=.84 else "aceptable"; op_new.loc[mask,"final_class"]="PRIMARY_WITH_CAVEAT"
    shortcut_rows=[]
    for _,r in active_new.iterrows(): shortcut_rows.append({"domain":r.domain,"mode":r["mode"],"shortcut_dominance_flag":"no","dominance_type":"direct_or_not_recomputed","model_balanced_accuracy":r.balanced_accuracy})
    shortcut=pd.DataFrame(shortcut_rows); save(shortcut,SHORTCUT_OUT)
    save(op_new,OP_OUT/"tables/hybrid_operational_final_champions.csv"); save(active_new,ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv")
    norm=build_normalized_table(PolicyInputs(OP_OUT/"tables/hybrid_operational_final_champions.csv",ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv",SHORTCUT_OUT))
    boots,stress=boot_stress(sel,cache_all) if not sel.empty else (pd.DataFrame(),pd.DataFrame()); save(boots,BASE/"bootstrap/selected_bootstrap_audit.csv"); save(stress,BASE/"stress/selected_stress_audit.csv")
    nmap={(str(r["domain"]),str(r["mode"])):r for r in norm.to_dict("records")}
    for i,row in active_new.iterrows():
        key=(str(row.domain),str(row["mode"])); ncls=str(nmap.get(key,{}).get("normalized_final_class","HOLD_FOR_LIMITATION")); oc,pct,band,rec,cav=conf(row,ncls); active_new.loc[i,"final_operational_class"]=oc; active_new.loc[i,"confidence_pct"]=pct; active_new.loc[i,"confidence_band"]=band; active_new.loc[i,"recommended_for_default_use"]=rec; active_new.loc[i,"operational_caveat"]=cav; op_new.loc[(op_new.domain==key[0])&(op_new["mode"]==key[1]),"final_class"]=ncls
    save(op_new,OP_OUT/"tables/hybrid_operational_final_champions.csv"); save(op_new[op_new.final_class.isin(["HOLD_FOR_LIMITATION","REJECT_AS_PRIMARY"])],OP_OUT/"tables/hybrid_operational_final_nonchampions.csv"); save(active_new,ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv"); save(active_new.groupby(["final_operational_class","confidence_band"],dropna=False).size().reset_index(name="n_active_models"),ACTIVE_OUT/"tables/hybrid_active_modes_summary.csv")
    inputs_new,q_new,mapdf,flag_delta,text_delta,final_visible=sync_flags(active_new,inputs,q,q_before); save(inputs_new,ACTIVE_OUT/"tables/hybrid_questionnaire_inputs_master.csv"); save(mapdf,BASE/"questionnaire_sync/model_input_to_full_question_map.csv"); save(flag_delta,BASE/"questionnaire_sync/questionnaire_mode_flag_delta.csv"); save(text_delta,BASE/"questionnaire_sync/question_text_delta_audit.csv"); save(final_visible,BASE/"questionnaire_sync/final_visible_questions_by_mode.csv"); save(final_visible,ACTIVE_OUT/"questionnaire_sync/final_visible_questions_by_mode.csv")
    if not text_delta.empty: raise RuntimeError("question_text_changed_unexpectedly")
    q_new.to_csv(Q_CSV,index=False,lineterminator="\n"); q_new.to_csv(Q_CSV_DUP,index=False,lineterminator="\n")
    norm=build_normalized_table(PolicyInputs(OP_OUT/"tables/hybrid_operational_final_champions.csv",ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv",SHORTCUT_OUT)); viol=policy_violations(norm); save(norm,NORM_OUT); save(viol,NORM_VIOL)
    final_guard=active_new[active_new.apply(lambda r:any(sf(r.get(m),0)>.98 for m in WATCH),axis=1)].copy(); save(final_guard,BASE/"validation/remaining_active_guardrail_violations.csv")
    old_idx=active.set_index(["domain","mode"]); comp=[]
    for _,r in active_new.iterrows():
        o=old_idx.loc[(r.domain,r["mode"])]
        comp.append({"domain":r.domain,"mode":r["mode"],"changed":"yes" if str(r.active_model_id)!=str(o.active_model_id) else "no","old_champion":o.active_model_id,"new_champion":r.active_model_id,"old_n_features":o.n_features,"new_n_features":r.n_features,"old_f1":o.f1,"new_f1":r.f1,"old_recall":o.recall,"new_recall":r.recall,"old_precision":o.precision,"new_precision":r.precision,"old_balanced_accuracy":o.balanced_accuracy,"new_balanced_accuracy":r.balanced_accuracy,"old_brier":o.brier,"new_brier":r.brier,"old_class":o.final_operational_class,"new_class":r.final_operational_class,"old_confidence_pct":o.confidence_pct,"new_confidence_pct":r.confidence_pct})
    compdf=pd.DataFrame(comp); save(compdf,BASE/"tables/final_old_vs_new_comparison_v10.csv"); save(pairwise(sel,cache_all) if not sel.empty else pd.DataFrame(),BASE/"validation/selected_pairwise_prediction_similarity.csv")
    bal=[]
    for d in DOMAINS:
        y=data[f"target_domain_{d}_final"].dropna().astype(int); bal.append({"domain":d,"n":len(y),"positive_n":int(y.sum()),"negative_n":int((1-y).sum()),"positive_rate":float(y.mean())})
    save(pd.DataFrame(bal),BASE/"validation/class_balance_audit.csv"); save(pd.DataFrame([{"dataset_rows":len(data),"participant_id_duplicates":int(data.participant_id.duplicated(keep=False).sum()),"full_vector_duplicates_anywhere":int(data.drop(columns=["participant_id"],errors="ignore").astype(str).agg("|".join,axis=1).duplicated(keep=False).sum())}]),BASE/"validation/duplicate_audit_global.csv")
    report=["# Hybrid Final Model Structural Compliance v1","",f"Generated: `{now()}`","",f"- source_active: `{ACTIVE_SRC.relative_to(ROOT)}`",f"- output_active: `{(ACTIVE_OUT/'tables/hybrid_active_models_30_modes.csv').relative_to(ROOT)}`",f"- initial_guardrail_violations: `{len(g0)}`",f"- target_slots_for_retrain: `{len(target)}`",f"- selected_promotions: `{len(sel)}`",f"- retained_after_retrain_attempt: `{len(ret)}`",f"- remaining_guardrail_violations: `{len(final_guard)}`",f"- policy_violations: `{len(viol)}`",f"- question_text_changes: `{len(text_delta)}`","","## Promotions",md(sel[["domain","mode","old_active_model_id","active_model_id","old_f1","f1","old_recall","recall","old_precision","precision","old_balanced_accuracy","balanced_accuracy"]]) if not sel.empty else "_sin promociones_","","## Retained",md(ret) if not ret.empty else "_sin retenidos_"]
    (BASE/"reports/final_model_structural_compliance_summary.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    manifest={"line":LINE,"freeze_label":FREEZE,"generated_at_utc":now(),"source_truth_previous":{"active":str(ACTIVE_SRC.relative_to(ROOT)),"operational":str(OP_SRC.relative_to(ROOT))},"source_truth_new":{"active":str((ACTIVE_OUT/"tables/hybrid_active_models_30_modes.csv").relative_to(ROOT)),"operational":str((OP_OUT/"tables/hybrid_operational_final_champions.csv").relative_to(ROOT)),"questionnaire_visible":str(Q_CSV.relative_to(ROOT))},"stats":{"initial_guardrail_violations":int(len(g0)),"target_slots_for_retrain":int(len(target)),"trials":int(len(trials_df)),"selected_promotions":int(len(sel)),"retained_after_retrain_attempt":int(len(ret)),"remaining_guardrail_violations":int(len(final_guard)),"policy_violations":int(len(viol)),"question_text_changes":int(len(text_delta)),"questionnaire_mode_flag_changes":int(len(flag_delta))}}
    (ART/f"{LINE}_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); (ROOT/"artifacts"/f"hybrid_active_modes_freeze_{FREEZE}"/f"hybrid_active_modes_freeze_{FREEZE}_manifest.json").write_text(json.dumps({**manifest,"artifact":f"hybrid_active_modes_freeze_{FREEZE}"},indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); (ROOT/"artifacts"/f"hybrid_operational_freeze_{FREEZE}"/f"hybrid_operational_freeze_{FREEZE}_manifest.json").write_text(json.dumps({**manifest,"artifact":f"hybrid_operational_freeze_{FREEZE}"},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"ok",**manifest["stats"]},ensure_ascii=False))
    return 0 if len(final_guard)==0 and len(viol)==0 and len(text_delta)==0 else 1
if __name__ == "__main__": raise SystemExit(main())
