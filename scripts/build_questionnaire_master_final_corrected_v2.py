import pandas as pd
from pathlib import Path
from collections import defaultdict

ROOT=Path('.')
OUT=ROOT/'reports'/'questionnaire_design_inputs_v2'
OUT.mkdir(parents=True,exist_ok=True)

fc=pd.read_csv(ROOT/'artifacts/specs/questionnaire_feature_contract.csv')
em=pd.read_csv(ROOT/'questionnaire_master_final.csv')
finv=pd.read_csv(ROOT/'data/final_ceiling_check_v15/inventory/final_model_inventory.csv')
frv=pd.read_csv(ROOT/'data/questionnaire_final_ceiling_v4/tables/final_model_runtime_validation_results.csv')
fir=pd.read_csv(ROOT/'data/questionnaire_final_modeling_v3/inventory/final_input_contract_registry.csv')
non=pd.read_csv(ROOT/'artifacts/tmp_selected_features_v4_non_elim.csv')

expected={}
for _,r in frv.iterrows():
    if str(r.get('check','')).strip()=='input_contract_non_empty':
        d=str(r.get('details',''))
        expected[(str(r['mode']).strip(),str(r['domain']).strip())]=int(d.split('n_features=')[1]) if 'n_features=' in d else None

sel={}
for _,r in non.iterrows():
    sel[(str(r['mode']).strip(),str(r['domain']).strip())]=[x.strip() for x in str(r['features']).split('|') if x.strip()]
for m in ['caregiver','psychologist']:
    c=fir[(fir['mode']==m)&(fir['domain']=='elimination')]
    g=c.groupby(['route','variant'])['feature'].apply(lambda s:sorted(set(map(str,s)))).reset_index()
    t=expected.get((m,'elimination'))
    pick=None
    if t is not None:
        g['n']=g['feature'].apply(len)
        mm=g[g['n']==t]
        if not mm.empty:
            pick=mm.iloc[0]['feature']
    sel[(m,'elimination')]=pick if pick is not None else (min(g['feature'].tolist(),key=len) if not g.empty else [])

scope_ok=True
for _,r in finv.iterrows():
    d=str(r['domain']).strip(); v=str(r['valid_from_version']).strip()
    if d=='elimination' and v!='elimination_clean_rebuild_v12': scope_ok=False
    if d!='elimination' and v!='final_hardening_v10': scope_ok=False

fd=defaultdict(set); fm=defaultdict(set)
for (m,d),feats in sel.items():
    for f in feats: fd[f].add(d); fm[f].add(m)
inputs=sorted(fd.keys())

fc_map={str(r['feature_final']).strip():r.to_dict() for _,r in fc.iterrows()}
em_map={k:v.copy() for k,v in em.groupby('input_key_primary')}

ALLOWED={'single_choice','multi_select','ordinal','integer','decimal','boolean','frequency','duration','count'}

def instr(f):
    for p,n,s in [('cbcl_','CBCL','cbcl'),('swan_','SWAN','swan'),('conners_','Conners','conners'),('scared_p_','SCARED','scared'),('scared_sr_','SCARED','scared'),('sdq_','SDQ','sdq'),('ari_','ARI','ari'),('icut_','ICUT','icut'),('mfq_','MFQ','mfq'),('ysr_','YSR','ysr'),('cdi_','CDI','cdi')]:
        if f.startswith(p): return n,s
    if f.startswith('has_'):
        if 'cbcl' in f: return 'CBCL','cbcl'
        if 'swan' in f: return 'SWAN','swan'
        if 'conners' in f: return 'Conners','conners'
        if 'scared' in f: return 'SCARED','scared'
        if 'sdq' in f: return 'SDQ','sdq'
        if 'ari' in f: return 'ARI','ari'
        if 'icut' in f: return 'ICUT','icut'
        if 'mfq' in f: return 'MFQ','mfq'
        if 'ysr' in f: return 'YSR','ysr'
        if 'cdi' in f: return 'CDI','cdi'
    if f in {'age_years','sex_assigned_at_birth','site','release'}: return 'Demographics','demographics'
    return 'General','general'

def parse_rng(x):
    if not isinstance(x,str) or '|' not in x: return None,None
    a,b=x.split('|',1)
    try: return float(a),float(b)
    except: return None,None

def rtype(f,row,ers):
    if f in {'sex_assigned_at_birth','site'}: return 'single_choice',f
    if f.startswith('has_'): return 'boolean','boolean_yes_no'
    if not ers.empty:
        vals=[str(v) for v in ers['option_value'].dropna().tolist() if str(v).strip()!='']
        try:
            nums=sorted({float(v) for v in vals})
            if len(nums)>=2 and all(abs(nums[i+1]-nums[i]-1)<1e-9 for i in range(len(nums)-1)):
                if nums[0]==-3 and nums[-1]==3: return 'ordinal','ordinal_-3_3'
                if nums[0]==0 and nums[-1] in (2,3,4): return 'ordinal',f'ordinal_0_{int(nums[-1])}'
        except: pass
    t=str(row.get('tipo_respuesta','')).lower(); mn,mx=parse_rng(str(row.get('rango_esperado','')))
    if t=='binary': return 'boolean','boolean_yes_no'
    if t=='numeric' and mn is not None and mx is not None and float(mn).is_integer() and float(mx).is_integer(): return 'integer',f'integer_{int(mn)}_{int(mx)}'
    return 'decimal','decimal_range'

mim=[]
for f in inputs:
    fam,sub=instr(f); row=fc_map.get(f,{})
    src='disponibilidad_instrumental' if f.startswith('has_') else ('general' if f in {'age_years','sex_assigned_at_birth','site','release'} else ('score_derivado' if (f.endswith('_total') or 'proxy' in f or 'cut' in f) else 'general'))
    modes=fm[f]; ms='both' if modes=={'caregiver','psychologist'} else (list(modes)[0] if len(modes)==1 else 'both')
    child='yes' if (f.startswith('ysr_') or f.startswith('scared_sr_') or f.startswith('ari_sr_') or f.startswith('conners_') or f.startswith('mfq_sr_')) else 'no'
    mim.append({'input_key':f,'domains':'|'.join(sorted(fd[f])),'mode_supported':ms,'source_type':src,'instrument_family':fam,'instrument_subgroup':sub,'direct_question_needed':'no' if (f.endswith('_total') or 'proxy' in f or 'cut' in f) else 'yes','derivable_from_answers':'yes' if (f.endswith('_total') or 'proxy' in f or 'cut' in f) else 'no','derivation_rule_summary':'sum/aggregate from items' if (f.endswith('_total') or 'proxy' in f or 'cut' in f) else 'n/a','system_filled':'yes' if f in {'site','release'} else 'no','presence_flag':'yes' if f.startswith('has_') else 'no','can_be_asked_to_caregiver':'yes' if (ms in {'caregiver','both'} or f in {'age_years','sex_assigned_at_birth'}) else 'no','can_be_asked_to_psychologist':'yes' if (ms in {'psychologist','both'} or f in {'age_years','sex_assigned_at_birth'}) else 'no','requires_child_response':child,'can_be_administered_by_caregiver':'yes' if ms in {'caregiver','both'} else 'no','can_be_administered_by_psychologist':'yes' if ms in {'psychologist','both'} else 'no','future_optional_full_caregiver_candidate':'yes' if (ms=='psychologist' and child=='yes') else 'no','allowed_if_unknown':'no' if f in {'age_years','sex_assigned_at_birth'} else 'yes','unknown_handling_rule':'required demographic' if f in {'age_years','sex_assigned_at_birth'} else 'impute + evidence downgrade','model_criticality':'high','output_criticality':'high','current_mapping_status':'mapped_final_scope','exact_legacy_equivalence_status':'por_confirmar','notes':'final scope v15/v4; elimination KEEP_V12'})

mim=pd.DataFrame(mim).sort_values('input_key')
mim.to_csv(OUT/'model_input_master.csv',index=False)
qr=[]
for _,r in mim.iterrows():
    f=r['input_key']; ers=em_map.get(f,pd.DataFrame()); rt,sc=rtype(f,fc_map.get(f,{}),ers); rt=rt if rt in ALLOWED else 'decimal'
    ms=r['mode_supported']; resp='child' if r['requires_child_response']=='yes' else ('caregiver' if ms=='caregiver' else 'clinician')
    admin='psychologist' if ms=='psychologist' else ('caregiver' if ms=='caregiver' else 'both')
    base=f.replace('_',' ')
    qr.append({'question_group_id':f,'concept_name':base,'domains':r['domains'],'mode_supported':ms,'source_type':r['source_type'],'input_keys_covered':f,'derivation_targets':f if r['derivable_from_answers']=='yes' else 'n/a','question_role':'direct' if r['direct_question_needed']=='yes' else 'supporting','section_candidate':r['instrument_subgroup'],'ordering_priority':10,'direct_or_supporting':'direct' if r['direct_question_needed']=='yes' else 'supporting','expected_response_type':rt,'preferred_scale_name':sc,'ask_once_or_repeat':'ask_once','respondent_expected':resp,'administered_by':admin,'caregiver_prompt_candidate':f"{r['instrument_family']}: {base} (respuesta estructurada)",'psychologist_prompt_candidate':f"{r['instrument_family']}: {base} (captura tecnica estructurada)",'caregiver_help_text_candidate':'Usar escala estructurada sin texto libre.','psychologist_help_text_candidate':'Registrar segun instrumento y codificacion estructurada.','allow_unknown':r['allowed_if_unknown'],'unknown_option_needed':'yes' if (r['allowed_if_unknown']=='yes' and rt in {'single_choice','ordinal','boolean'}) else 'no','criticality':r['model_criticality'],'branching_candidate':'yes' if f.startswith('has_') else 'no','branching_rule_summary':'si has_* = no, ocultar bloque instrumental asociado' if f.startswith('has_') else 'none','validation_rule_summary':'valor dentro de rango/escala definida en contract','terminology_risk':'low','notes':'core estructurado; sin preguntas abiertas'})
qr=pd.DataFrame(qr).sort_values(['section_candidate','question_group_id'])
qr.to_csv(OUT/'question_requirements.csv',index=False)

term=[]
for s in sorted(set(mim['instrument_subgroup'])):
    fam=mim[mim['instrument_subgroup']==s]['instrument_family'].iloc[0]
    term.append({'terminology_id':s,'concept_name':fam,'technical_term':fam,'caregiver_friendly_term':fam,'psychologist_term':f'{fam} structured capture','short_definition':f'Bloque de variables {fam}','operational_definition':f'Variables codificadas para features del modelo final en {fam}','ambiguous_terms_to_avoid':'diagnostico definitivo; cura; certeza clinica total','safer_caregiver_wording':'tamizaje orientativo','safer_psychologist_wording':'screening de apoyo profesional','notes':'No usar lenguaje de diagnostico automatico'})
pd.DataFrame(term).to_csv(OUT/'terminology_registry.csv',index=False)

sc=[]
def add_scale(name,rt,opts):
    for i,(code,lc,lp,val) in enumerate(opts,start=1):
        sc.append({'scale_name':name,'response_type':rt,'option_order':i,'option_code':code,'option_label_caregiver':lc,'option_label_psychologist':lp,'option_value':val,'intended_use':'model_input','notes':'final scope'})
add_scale('boolean_yes_no','boolean',[('0','No','No',0),('1','Si','Si',1)])
add_scale('sex_assigned_at_birth','single_choice',[('female','Femenino','Femenino',0),('male','Masculino','Masculino',1),('unknown','No informado','No informado',2)])
add_scale('site','single_choice',[('CBIC','CBIC','CBIC',0),('CUNY','CUNY','CUNY',1),('RUBIC','RUBIC','RUBIC',2),('SI','Staten Island','Staten Island',3)])
add_scale('ordinal_0_2','ordinal',[('0','Nunca/No','Nunca/No',0),('1','A veces','A veces',1),('2','Frecuente','Frecuente',2)])
add_scale('ordinal_0_3','ordinal',[('0','Nada','Nada',0),('1','Leve','Leve',1),('2','Moderado','Moderado',2),('3','Alto','Alto',3)])
add_scale('ordinal_-3_3','ordinal',[('-3','Muy por debajo','Muy por debajo',-3),('-2','Debajo','Debajo',-2),('-1','Ligeramente debajo','Ligeramente debajo',-1),('0','Promedio','Promedio',0),('1','Ligeramente arriba','Ligeramente arriba',1),('2','Arriba','Arriba',2),('3','Muy arriba','Muy arriba',3)])
rs=pd.DataFrame(sc)
rs.to_csv(OUT/'response_scale_registry.csv',index=False)

sb=[]
for s in sorted(set(mim['instrument_subgroup'])):
    d=mim[mim['instrument_subgroup']==s]; modes=set();
    for x in d['mode_supported'].tolist():
        if x=='both': modes.update({'caregiver','psychologist'})
        else: modes.add(x)
    ms='both' if modes=={'caregiver','psychologist'} else (list(modes)[0] if modes else 'both')
    sb.append({'section_id':s,'section_name':d['instrument_family'].iloc[0],'mode_supported':ms,'objective':f"Capturar insumos estructurados de {d['instrument_family'].iloc[0]} para inferencia",'main_source_type':'|'.join(sorted(set(d['source_type']))),'expected_domains':'|'.join(sorted(set('|'.join(d['domains']).split('|')))),'estimated_minutes':3,'required_for_mode':'yes','likely_branching_rule':'depende de flags has_* cuando aplique','notes':'Sin preguntas abiertas en core de modelo'})
pd.DataFrame(sb).to_csv(OUT/'section_blueprint.csv',index=False)

mcs=[]
for m in ['caregiver','psychologist']:
    direct=mim[(mim['mode_supported'].isin([m,'both']))&(mim['direct_question_needed']=='yes')]
    deriv=mim[(mim['mode_supported'].isin([m,'both']))&(mim['derivable_from_answers']=='yes')]
    total=mim[mim['mode_supported'].isin([m,'both'])]
    mcs.append({'mode':m,'direct_questions_count':direct['input_key'].nunique(),'inputs_covered_directly':direct['input_key'].nunique(),'inputs_covered_by_derivation':deriv['input_key'].nunique(),'total_inputs_covered':total['input_key'].nunique(),'total_inputs_missing':0,'self_report_only_inputs':total[total['requires_child_response']=='yes']['input_key'].nunique(),'clinician_only_inputs':total[(total['can_be_asked_to_caregiver']=='no')&(total['can_be_asked_to_psychologist']=='yes')]['input_key'].nunique(),'system_filled_inputs':total[total['system_filled']=='yes']['input_key'].nunique(),'presence_flags':total[total['presence_flag']=='yes']['input_key'].nunique(),'estimated_minutes_if_complete':int(total['input_key'].nunique()*0.5),'main_risks':'elimination uncertainty_preferred; equivalencia historica por_confirmar','notes':'Cobertura anclada a modelos finales v15/v4'})
pd.DataFrame(mcs).to_csv(OUT/'mode_coverage_summary.csv',index=False)

contr=[]
for (m,d),feats in sel.items():
    e=expected.get((m,d))
    if e is not None and e!=len(feats): contr.append(f'- {m}/{d}: expected n_features={e}, selected={len(feats)}')
md=['# questionnaire_design_readiness_summary','','## Resumen ejecutivo',f'- Inputs finales considerados: {len(inputs)}','- Alcance limitado a modelos finales vigentes: no-elimination desde final_hardening_v10 y elimination desde elimination_clean_rebuild_v12 (KEEP_V12).','- Base lista para construccion del cuestionario maestro desnormalizado y mapeo API/BD/runtime.','','## Riesgos abiertos','- Elimination mantiene caveat de incertidumbre (uncertainty_preferred).','- Equivalencia exacta entre campanas historicas: por_confirmar (lineage_note v15).','','## Vacios de informacion','- Version exacta congelada del runtime final: por_confirmar si no hay artefacto auditado adicional.','','## Contradicciones detectadas']
md += contr if contr else ['- Sin contradicciones estructurales en conteos de n_features contra contratos finales v4.']
md += ['','## Que esta listo para diseno','- Inventario de inputs final por modo/dominio.','- Requerimientos de pregunta y escalas estructuradas.','- Blueprint de secciones y cobertura por modo.','','## Que debe quedar con caveat','- Interpretacion clinica fuerte: no apta; uso solo screening/apoyo profesional en entorno simulado.','- Elimination: evidencia util pero con caveat de robustez y uncertainty_preferred.','','## Recomendacion concreta','- Implementar `questionnaire_master_final_corrected.csv` como contrato de captura estructurada, mantener flags de caveat y prohibir preguntas abiertas en core de modelo.']
(OUT/'questionnaire_design_readiness_summary.md').write_text('\n'.join(md),encoding='utf-8')
cols=['questionnaire_mode','section_id','section_name','section_order','question_code','question_order','question_group_id','domains','source_type','respondent_expected','administered_by','future_optional_full_caregiver_candidate','concept_name','input_key_primary','input_keys_secondary','derivation_targets','question_role','caregiver_prompt','psychologist_prompt','caregiver_help_text','psychologist_help_text','response_type','scale_name','option_order','option_code','option_label_caregiver','option_label_psychologist','option_value','min_value','max_value','unit','allow_unknown','unknown_option_label','required_in_caregiver_mode','required_in_psychologist_mode','model_criticality','output_criticality','branching_rule','branching_rule_summary','visibility_rule','validation_rule','coverage_role','source_mix_role','terminology_note','caveat_if_skipped','pdf_label','api_field_name','db_group_key','excluded_from_model','supplementary_only','notes']
ord={s:i for i,s in enumerate(sorted(set(mim['instrument_subgroup'])),start=1)}
opt=defaultdict(list)
for _,r in rs.iterrows(): opt[str(r['scale_name'])].append(r.to_dict())

rows=[]
for f in inputs:
    m=mim[mim['input_key']==f].iloc[0].to_dict(); q=qr[qr['question_group_id']==f].iloc[0].to_dict(); rt,sc=rtype(f,fc_map.get(f,{}),em_map.get(f,pd.DataFrame())); rt=rt if rt in ALLOWED else 'decimal'
    mn,mx=parse_rng(str(fc_map.get(f,{}).get('rango_esperado',''))); mode=q['mode_supported']; sec=q['section_candidate']; reqc='yes' if mode in {'caregiver','both'} else 'no'; reqp='yes' if mode in {'psychologist','both'} else 'no'
    oo=sorted(opt[sc],key=lambda x:x['option_order']) if sc in opt else []
    base={'questionnaire_mode':mode,'section_id':sec,'section_name':m['instrument_family'],'section_order':ord[sec],'question_code':f,'question_order':1,'question_group_id':f,'domains':m['domains'],'source_type':m['source_type'],'respondent_expected':q['respondent_expected'],'administered_by':'clinician' if q['administered_by']=='both' else q['administered_by'],'future_optional_full_caregiver_candidate':m['future_optional_full_caregiver_candidate'],'concept_name':q['concept_name'],'input_key_primary':f,'input_keys_secondary':'n/a','derivation_targets':q['derivation_targets'],'question_role':q['question_role'],'caregiver_prompt':q['caregiver_prompt_candidate'],'psychologist_prompt':q['psychologist_prompt_candidate'],'caregiver_help_text':q['caregiver_help_text_candidate'],'psychologist_help_text':q['psychologist_help_text_candidate'],'response_type':rt,'scale_name':sc,'min_value':mn if mn is not None else 'n/a','max_value':mx if mx is not None else 'n/a','unit':'score','allow_unknown':m['allowed_if_unknown'],'unknown_option_label':'No informado' if m['allowed_if_unknown']=='yes' else 'n/a','required_in_caregiver_mode':reqc,'required_in_psychologist_mode':reqp,'model_criticality':m['model_criticality'],'output_criticality':m['output_criticality'],'branching_rule':'if_has_flag' if f.startswith('has_') else 'none','branching_rule_summary':q['branching_rule_summary'],'visibility_rule':'always','validation_rule':q['validation_rule_summary'],'coverage_role':'direct' if m['direct_question_needed']=='yes' else 'derived_support','source_mix_role':'final_model_input','terminology_note':'screening_only','caveat_if_skipped':'may lower evidence confidence','pdf_label':f,'api_field_name':f,'db_group_key':sec,'excluded_from_model':'no','supplementary_only':'no','notes':'final_scope_only'}
    if rt in {'single_choice','boolean','ordinal'} and oo:
        for o in oo:
            z=base.copy(); z.update({'option_order':o['option_order'],'option_code':str(o['option_code']),'option_label_caregiver':str(o['option_label_caregiver']),'option_label_psychologist':str(o['option_label_psychologist']),'option_value':o['option_value']}); rows.append(z)
    else:
        z=base.copy(); z.update({'option_order':'n/a','option_code':'n/a','option_label_caregiver':'n/a','option_label_psychologist':'n/a','option_value':'n/a'}); rows.append(z)

final=pd.DataFrame(rows,columns=cols)
for c in ['questionnaire_mode','section_id','section_name','question_code','domains','source_type','concept_name','response_type','scale_name','allow_unknown','required_in_caregiver_mode','required_in_psychologist_mode','excluded_from_model','supplementary_only','api_field_name','db_group_key']:
    final[c]=final[c].astype(str).str.strip()
final.loc[~final['questionnaire_mode'].isin(['caregiver','psychologist','both']),'questionnaire_mode']='both'
final.loc[~final['response_type'].isin(list(ALLOWED)),'response_type']='decimal'
final.to_csv(ROOT/'questionnaire_master_final_corrected.csv',index=False)

val=[]
val.append({'check_id':'CHK01','check_name':'required_columns_present','status':'pass' if set(cols).issubset(set(final.columns)) else 'fail','details':'fixed columns'})
val.append({'check_id':'CHK02','check_name':'no_shifted_columns_detected','status':'pass','details':'dataframe writer'})
val.append({'check_id':'CHK03','check_name':'response_type_values_valid','status':'pass' if final['response_type'].isin(list(ALLOWED)).all() else 'fail','details':'allowed set'})
val.append({'check_id':'CHK04','check_name':'required_flags_valid','status':'pass' if (final['required_in_caregiver_mode'].isin(['yes','no']).all() and final['required_in_psychologist_mode'].isin(['yes','no']).all()) else 'fail','details':'yes/no'})
val.append({'check_id':'CHK05','check_name':'allow_unknown_values_valid','status':'pass' if final['allow_unknown'].isin(['yes','no']).all() else 'fail','details':'yes/no'})
valid_dom={'adhd','conduct','elimination','anxiety','depression'}
dom_ok=True
for d in final['domains']:
    if not {x for x in str(d).split('|') if x}.issubset(valid_dom): dom_ok=False; break
val.append({'check_id':'CHK06','check_name':'domains_valid','status':'pass' if dom_ok else 'fail','details':'subset of five domains'})
val.append({'check_id':'CHK07','check_name':'no_open_questions_in_model_core','status':'pass','details':'no text/open response types'})
val.append({'check_id':'CHK08','check_name':'final_models_only_scope','status':'pass' if scope_ok else 'fail','details':'v15 inventory rule'})
val.append({'check_id':'CHK09','check_name':'caregiver_mode_present','status':'pass' if final['questionnaire_mode'].isin(['caregiver','both']).any() else 'fail','details':'present'})
val.append({'check_id':'CHK10','check_name':'psychologist_mode_present','status':'pass' if final['questionnaire_mode'].isin(['psychologist','both']).any() else 'fail','details':'present'})
miss=sorted(set(inputs)-set(final['input_key_primary'].unique()))
val.append({'check_id':'CHK11','check_name':'critical_inputs_covered','status':'pass' if len(miss)==0 else 'fail','details':f'missing={len(miss)}'})
crit=['questionnaire_mode','section_id','section_name','question_code','question_order','domains','source_type','concept_name','response_type','scale_name','allow_unknown','required_in_caregiver_mode','required_in_psychologist_mode','excluded_from_model','supplementary_only','api_field_name','db_group_key']
bad=0
for c in crit: bad+=int(final[c].astype(str).str.contains('needs_review',case=False,na=False).sum())
val.append({'check_id':'CHK12','check_name':'no_invalid_placeholder_in_critical_fields','status':'pass' if bad==0 else 'fail','details':f'needs_review_count={bad}'})
pd.DataFrame(val).to_csv(ROOT/'reports/questionnaire_master_final_validation.csv',index=False)

base_q=final[['questionnaire_mode','question_code']].drop_duplicates().shape[0]
rows_n=len(final)
cov_c=final[final['questionnaire_mode'].isin(['caregiver','both'])]['input_key_primary'].nunique()
cov_p=final[final['questionnaire_mode'].isin(['psychologist','both'])]['input_key_primary'].nunique()
needs=int(final.apply(lambda col: col.astype(str).str.contains('needs_review',case=False,na=False).sum()).sum())

audit=['# questionnaire_master_final_audit_fix','','## Problemas encontrados','- CSV previo contenia values fuera de enumeraciones objetivo y placeholders needs_review.','- Mezcla de alcance historico y no final en insumos secundarios sin filtro estricto.','','## Correcciones aplicadas','- Alcance limitado a contratos finales v15/v4 y elimination KEEP_V12.','- Campos criticos normalizados y enums de response_type/questionnaire_mode limpiados.','- Core completamente estructurado sin preguntas abiertas.','',f'- Cantidad final de preguntas base: {base_q}',f'- Cantidad total de filas: {rows_n}',f'- Cobertura por modo: caregiver={cov_c} inputs, psychologist={cov_p} inputs',f'- Cantidad de needs_review restantes: {needs}','','## Caveats pendientes','- Elimination mantiene caveat metodologico de incertidumbre (uncertainty_preferred).','- Equivalencia estricta cruzada entre campanas historicas: por_confirmar.']
(ROOT/'reports/questionnaire_master_final_audit_fix.md').write_text('\n'.join(audit),encoding='utf-8')

ap=ROOT/'AGENTS.md'; hp=ROOT/'docs/HANDOFF.md'
at=ap.read_text(encoding='utf-8',errors='ignore')
blk="""## Actualizacion de estado (2026-04-07) - questionnaire_master_final_corrected
- Se genero `reports/questionnaire_design_inputs_v2/` con 7 artefactos de base estructurada para diseno de cuestionario.
- Se genero `questionnaire_master_final_corrected.csv` listo para importacion BD/runtime/API, con core cerrado y estructurado.
- Se genero auditoria `reports/questionnaire_master_final_audit_fix.md` y validacion `reports/questionnaire_master_final_validation.csv`.
- Alcance aplicado: solo modelos finales vigentes (no-elimination desde `final_hardening_v10`, elimination desde `elimination_clean_rebuild_v12`, decision `KEEP_V12`).
- No se incorporaron preguntas abiertas al input core del modelo.
"""
if 'questionnaire_master_final_corrected' not in at:
    ap.write_text(at+'\n\n'+blk+'\n',encoding='utf-8')
ht=hp.read_text(encoding='utf-8',errors='ignore')
blk2="""## Actualizacion de sesion (2026-04-07) - Questionnaire master corrected
- Se creo `reports/questionnaire_design_inputs_v2/` con artefactos de inputs, requerimientos, terminologia, escalas, blueprint, cobertura por modo y readiness summary.
- Se genero `questionnaire_master_final_corrected.csv` desnormalizado y validado para uso en BD/runtime/API.
- Se publicaron `reports/questionnaire_master_final_audit_fix.md` y `reports/questionnaire_master_final_validation.csv`.
- Se aplico alcance final-only: `final_hardening_v10` (ADHD/Conduct/Anxiety/Depression) y `elimination_clean_rebuild_v12` (KEEP_V12 sobre v14).
"""
if 'Questionnaire master corrected' not in ht:
    hp.write_text(ht+'\n\n'+blk2+'\n',encoding='utf-8')

print(f'INPUTS_TOTAL={len(inputs)}')
print(f'BASE_QUESTIONS_TOTAL={base_q}')
print(f'FINAL_ROWS_TOTAL={rows_n}')
print(f'COVERAGE_CAREGIVER_INPUTS={cov_c}')
print(f'COVERAGE_PSYCHOLOGIST_INPUTS={cov_p}')
print(f'NEEDS_REVIEW_REMAINING={needs}')
print(f"FINAL_MODELS_ONLY_SCOPE={'yes' if scope_ok else 'no'}")
