#!/usr/bin/env python3
"""
estandarizar_nombres.py — Homogeneiza nombres de archivos de microdatos y tabulados INEGI.

Convención objetivo:
    {censo}_{año}_{modulo_canonico}_{tipo}.{ext}

    censo = cngf | cnge | cngmd
    año   = 2011..2025
    modulo = nombre_canonico_completo
    tipo   = microdatos | tabulados | marco_conceptual
    ext    = dbf.zip | xlsx | txt | pdf

Uso:
    python3 estandarizar_nombres.py           # dry-run (solo muestra)
    python3 estandarizar_nombres.py --execute  # ejecuta renombrado
"""

import os, csv, hashlib, re, shutil, sys
from collections import Counter
from pathlib import Path

BASE = Path("microdatos_tabulados")
ROOT = Path(".")
LOG = Path("manifiesto_renombrado.csv")
DRY_RUN = "--execute" not in sys.argv

# ============================================================
# 1. MAPEOS DE NOMBRES CANÓNICOS DE MÓDULOS
# ============================================================

# Módulos DBF: abreviado -> canónico
DBF_MODULE_MAP = {
    # CNGF + CNGMD compartidos
    "act_estadis_geograficas": "actividades_estadisticas_geograficas",
    "act_estadis_geografica": "actividades_estadisticas_geograficas",
    "activ_estadist_geogra": "actividades_estadisticas_geograficas",
    "actividad_ayuntami": "actividades_ayuntamiento",
    "admin_agua_red": "administracion_servicio_agua_red_publica",
    "admin_agua": "administracion_servicio_agua_red_publica",
    "admin_pub_territorio": "administracion_publica_territorio",
    "admon_arch_gest_docum": "administracion_archivos_gestion_documental",
    "admon_archivo_gestion": "administracion_archivos_gestion_documental",
    "aguas_sintrat": "aguas_residuales_sin_tratamiento",
    "asen_hum_zona_riesg": "asentamientos_humanos_zonas_riesgo",
    "asent_human_irregu": "asentamientos_humanos_irregulares",
    "capac_admon_gestion": "capacitacion_administracion_archivos",
    "capac_trans_accprot": "capacitacion_transparencia_acceso_proteccion",
    "capacitacion_catastro": "capacitacion_catastro",
    "capta_agua_public": "captacion_agua_abastecimiento_publico",
    "capta_agua": "captacion_agua_abastecimiento_publico",
    "cartografia_catastral": "cartografia_catastral",
    "com_ini_aytto": "comisiones_iniciativas_ayuntamiento",
    "coordininst_intercinf": "coordinacion_interinstitucional_intercambio_informacion",
    "ctrl_inter_anticor": "control_interno_anticorrupcion",
    "ctrl_interno_anticorru": "control_interno_anticorrupcion",
    "desarr_urbano_ecc": "desarrollo_urbano_estrategia_ciudad_compacta",
    "difus_gest_agua": "difusion_informacion_gestion_agua_participacion",
    "disp_final_rsu": "disposicion_final_residuos_solidos_urbanos",
    "documento_electronico": "documentos_electronicos",
    "drenaje_alcant": "drenaje_alcantarillado",
    "ejercicio_func_espec": "ejercicio_funciones_especificas",
    "ejercicio_funcion": "ejercicio_funcion_seguridad_publica",
    "est_gen_comp_rsu": "estudios_generacion_composicion_residuos_solidos",
    "estruc_organ_catastro": "estructura_organizacional_catastro",
    "estruc_organizacional": "estructura_organizacional",
    "estruct_aytto": "estructura_ayuntamiento",
    "estructura_organizacional_catastro": "estructura_organizacional_catastro",
    "estructura_organizacional": "estructura_organizacional",
    "falleci_func_policial": "fallecimientos_funcion_policial",
    "func_esp": "funciones_especificas_catastro",
    "gob_elec": "gobierno_electronico",
    "gobierno_electronico": "gobierno_electronico",
    "impuesto_predial": "impuesto_predial",
    "inf_admon_territorial": "informacion_administracion_territorio",
    "infoestadistica_sp": "informacion_estadistica_seguridad_publica",
    "infraestructura_sp": "infraestructura_seguridad_publica",
    "infraestructura": "infraestructura_general",
    "ins_camp_imp_pred_cat": "inspecciones_campo_impuesto_predial_catastro",
    "inspecciones_campo": "inspecciones_campo",
    "inspecciones_de_campo": "inspecciones_campo",
    "inst_juri_territorial": "instrumentos_juridicos_planeacion_territorial",
    "integrantes_ayuntami": "integrantes_ayuntamiento",
    "interven_policiamun": "intervenciones_policia_municipal",
    "mando_unico_policial": "mando_unico_policial",
    "marco_regulatorio_ter": "marco_regulatorio_territorial",
    "marco_regulatorio": "marco_regulatorio",
    "pad_cart_catastral": "padron_cartografia_catastral",
    "padron_catastral": "padron_catastral",
    "part_ciud_rsu": "participacion_ciudadana_residuos_solidos",
    "participacion_ciudada": "participacion_ciudadana",
    "participacion_cuidadana": "participacion_ciudadana",  # typo corregido
    "participacion_ciudadana": "participacion_ciudadana",
    "plan_evalua": "planeacion_evaluacion",
    "planea_admon_gestion": "planeacion_administracion_archivos",
    "planea_evaluacion": "planeacion_evaluacion",
    "planeacion_evaluacion": "planeacion_evaluacion",
    "plantas_pot": "plantas_potabilizacion",
    "presunta_infracdelito": "presuntas_infracciones_delitos_intervenciones",
    "probable_infractor": "probables_infractores_responsables_intervenciones",
    "probable_victima_reg": "probables_victimas_registradas_intervenciones",
    "procesos_catastrales": "procesos_catastrales",
    "prog_gest_aguapot": "programas_gestion_sustentable_agua_potable",
    "prog_gest_agua": "programas_gestion_sustentable_agua_potable",
    "prog_gest_int_rsu": "programas_gestion_integral_residuos_solidos",
    "prog_moderni_catastral": "programa_modernizacion_catastral",
    "programa_modernizacion_catastral": "programa_modernizacion_catastral",
    "proteccion_civil": "proteccion_civil",
    "rec_admon_gestiondoc": "recursos_administracion_archivos",
    "rec_hum_territorial": "recursos_humanos_capacitacion_territorial",
    "rec_materiales": "recursos_materiales",
    "rec_presupuestal": "recursos_presupuestales",
    "rec_rsu": "recoleccion_residuos_solidos_urbanos",
    "recursos_humanos": "recursos_humanos",
    "recursos_materiales": "recursos_materiales",
    "recursos_presupuestal": "recursos_presupuestales",
    "recursos_sp": "recursos_seguridad_publica",
    "recpres_admon_gestion": "recursos_presupuestales_administracion_archivos",
    "recpresu_trans_accpro": "recursos_presupuestales_transparencia_proteccion",
    "reserv_territoriales": "reservas_territoriales",
    "resguardo_informacion_catastral": "resguardo_informacion_catastral",
    "resguar_inf_catastral": "resguardo_informacion_catastral",
    "serv_agua_red": "servicio_agua_red_publica",
    "serv_agua": "servicio_agua_red_publica",
    "serv_publicos": "servicios_publicos",
    "servicios_publicos": "servicios_publicos",
    "sist_gestion_control": "sistema_gestion_control_documentos",
    "sist_instituc_archivo": "sistema_institucional_archivos",
    "solic_acceso_protecc": "solicitudes_acceso_informacion_proteccion_datos",
    "tecno_infor_catastral": "tecnologias_informacion_catastral",
    "tecnologias_informacion_catastral": "tecnologias_informacion_catastral",
    "tramites_serv": "tramites_servicios",
    "tramites_servicios": "tramites_servicios",
    "transparencia": "transparencia",
    "transp_cont_int_anticor": "transparencia_control_interno_anticorrupcion",
    "trat_aguas_resid": "tratamiento_aguas_residuales",
    "trat_rsu": "tratamiento_residuos_solidos_urbanos",
    "tys_gob_elec": "tramites_servicios_gobierno_electronico",
    "valua_vinc_catastral": "valuacion_vinculacion_catastral",
    "valuacion_catastral": "valuacion_catastral",
    "vinculacion_catastral": "vinculacion_catastral",
    # 2011 legacy (apmd, ayu, jm, sp)
    "apmd_estructura": "administracion_publica_estructura",
    "apmd_funciones": "administracion_publica_funciones_especificas",
    "apmd_marco": "administracion_publica_marco_regulatorio",
    "apmd_participacion": "administracion_publica_participacion_ciudadana",
    "apmd_recursos": "administracion_publica_recursos",
    "apmd_tramites": "administracion_publica_tramites_servicios",
    "apmd_transparencia": "administracion_publica_transparencia_anticorrupcion",
    "ayu_comisiones": "ayuntamiento_comisiones_iniciativas",
    "ayu_estructura": "ayuntamiento_estructura_organizacional",
    # 2011 SP/JM
    "sp_ejercicio": "seguridad_publica_ejercicio_funcion",
    "sp_infraestructura": "seguridad_publica_infraestructura",
    "sp_recursos": "seguridad_publica_recursos",
    "jm_ejercicio": "justicia_municipal_ejercicio_funcion",
    "jm_infraestructura": "justicia_municipal_infraestructura",
    "jm_recursos": "justicia_municipal_recursos",
    # 2013-2015 SP/JM (prefijo JM_/SP_)
    "jm_ejercicio_funcion": "justicia_municipal_ejercicio_funcion",
    "jm_infraestructura_2013": "justicia_municipal_infraestructura",
    "jm_infraestuctura": "justicia_municipal_infraestructura",  # typo corregido
    "jm_recursos": "justicia_municipal_recursos",
    "sp_ejercicio_funcion": "seguridad_publica_ejercicio_funcion",
    "sp_infraestructura_2013": "seguridad_publica_infraestructura",
    "sp_recursos_2013": "seguridad_publica_recursos",
    "sp_seguridad_publica": "seguridad_publica",
    "sp_recursos_2015": "seguridad_publica_recursos",
    # 2013 módulos especiales
    "func_esp": "funciones_especificas_catastro",
    "tys_gob_elec": "tramites_servicios_gobierno_electronico",
    "marco_regulatorio_2013": "marco_regulatorio",
    "participacion_ciudadana_2013": "participacion_ciudadana",
    "recursos_2013": "recursos_administracion_publica",
    "estructura_organizacional_2013": "estructura_organizacional",
    "transp_cont_int_anticor": "transparencia_control_interno_anticorrupcion",
    # 2015 catch-all
    "recursos_2015": "recursos_administracion_publica",
}

# Submódulos M5/M6 (2013)
M5_M6_MODULE_MAP = {
    "m5_i": "agua_identificacion_servicio_prestador",
    "m5_ii": "agua_captacion_abastecimiento_publico",
    "m5_iv": "agua_administracion_servicio_red_publica",
    "m5_ix": "agua_difusion_participacion_ciudadana",
    "m5_v": "agua_alcantarillado_vertido",
    "m5_vi": "agua_identificacion_servicio_tratamiento",
    "m5_vii": "aguas_residuales",
    "m5_viii": "agua_programas_gestion_sustentable",
    "m6_i": "rsu_recoleccion",
    "m6_ii": "rsu_tratamiento",
    "m6_iii": "rsu_disposicion_final",
    "m6_iv": "rsu_estudios_generacion_composicion",
    "m6_v": "rsu_programas_gestion_integral",
}

# Módulos temáticos XLSX: código corto -> canónico
XLSX_THEMATIC_MAP = {
    "adm_arch": "administracion_archivos_gestion_documental",
    "adm_arc": "administracion_archivos_gestion_documental",
    "adm_archivos": "administracion_archivos_gestion_documental",
    "agua_saneam": "agua_potable_saneamiento",
    "alojam_asist": "alojamientos_asistencia_social",
    "ayunt_alcald": "ayuntamientos_alcaldias",
    "catastro": "catastro",
    "contratos": "contrataciones_publicas",
    "ctrl_int": "control_interno_anticorrupcion",
    "ctrl_int_anticor": "control_interno_anticorrupcion",
    "defensoria": "defensoria_publica",
    "est_org_rec": "estructura_organizacional_recursos",
    "estorg_rec": "estructura_organizacional_recursos",
    "gest_terr": "planeacion_gestion_territorial",
    "just_civica": "justicia_civica",
    "medio_amb": "medio_ambiente",
    "panteones": "panteones",
    "prog_social": "programas_sociales",
    "prot_civil": "proteccion_civil",
    "reg_pub_prop": "registro_publico_propiedad",
    "resid_solid": "residuos_solidos_urbanos",
    "seg_publica": "seguridad_publica",
    "serv_peri": "servicios_periciales",
    "serv_publ": "servicios_publicos",
    "serv_publicos": "servicios_publicos",
    "tramites": "tramites_servicios",
    "transparencia": "transparencia",
}

# Códigos M de XLSX (2017/2019)
CNGF_M_CODE_MAP = {
    "m1": "estructura_organizacional_recursos",
    "m2": "recursos_presupuestales_planeacion_evaluacion",
}

CNGMD_M_CODE_MAP = {
    "m1": "ayuntamiento",
    "m2": "administracion_publica",
    "m2_4": "administracion_publica_submodulo4",
    "m2_10": "administracion_publica_submodulo10",
    "m2s10": "administracion_publica_seccion10",
    "m2s4": "administracion_publica_seccion4",
    "m3": "catastro",
    "m4": "servicios_publicos",
    "m5": "agua_potable_saneamiento",
    "m6": "residuos_solidos_urbanos",
}

# ============================================================
# 2. FUNCIONES DE PARSEO
# ============================================================

def md5_file(path):
    """Calcula hash MD5 de un archivo."""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def parse_dbf_zip(filename):
    """Parsea nombre de ZIP DBF → (censo, año, módulo)."""
    name = filename.lower().replace('.zip', '')
    
    # Corregir typos conocidos primero
    name = name.replace('cngmd207', 'cngmd2017')
    name = name.replace('infraestuctura', 'infraestructura')
    name = name.replace('cuidadana', 'ciudadana')
    
    # Extraer censo
    census = None
    if '_cngf' in name:
        census = 'cngf'
        parts = name.split('_cngf')
    elif '_cngmd' in name:
        census = 'cngmd'
        parts = name.split('_cngmd')
    elif name.startswith('cngmd'):
        census = 'cngmd'
        parts = name.split('cngmd', 1)
        parts = ['', f'cngmd{parts[1]}'] if len(parts) > 1 else ['', name.replace('cngmd', '', 1)]
        idx = name.find('cngmd')
        parts = [name[:idx], name[idx:]]
    else:
        return None, None, None
    
    # Extraer año
    year_match = re.search(r'(20\d{2})', parts[1] if len(parts) > 1 else '')
    year = year_match.group(1) if year_match else None
    
    # Extraer nombre del módulo
    module_raw = parts[0].strip('_')
    
    if '_dbf' in module_raw:
        module_raw = module_raw.replace('_dbf', '')
    module_raw = re.sub(r'_dbf$', '', module_raw)
    
    # M5/M6
    if re.match(r'm[56]_[a-z]+', module_raw):
        sorted_keys = sorted(M5_M6_MODULE_MAP.keys(), key=len, reverse=True)
        for k in sorted_keys:
            if module_raw.startswith(k):
                return census, year, M5_M6_MODULE_MAP[k]
        return census, year, module_raw
    
    # Buscar en mapa canónico
    module_canonical = DBF_MODULE_MAP.get(module_raw)
    if module_canonical:
        return census, year, module_canonical
    
    # Coincidencia parcial
    if census == 'cngmd' and year:
        for k, v in DBF_MODULE_MAP.items():
            if k in module_raw and k != module_raw:
                if len(k) >= len(module_raw) * 0.5:
                    return census, year, v
    
    return census, year, module_raw


def parse_xlsx(filename):
    """Parsea nombre XLSX → (censo, año, módulo).
    
    Prioridad de patrones:
    1. Formato CNGMD M-code (CNGMD2017_M2_4.xlsx)
    2. Formato CNGF M-code (CNGF2017_M1.xlsx)
    3. CNGF/CNGE/CNGMD temático + año
    """
    name = filename.replace('.xlsx', '')
    name_lower = name.lower()
    
    # Patrón 1: CNGMD M-code (CNGMD2017_M2_4.xlsx)
    m = re.match(r'(cngmd)(\d{4})_(m\d.*)', name_lower)
    if m:
        census = 'cngmd'
        year = m.group(2)
        module = CNGMD_M_CODE_MAP.get(m.group(3), m.group(3))
        return census, year, module
    
    # Patrón 2: CNGF M-code (CNGF2017_M1.xlsx)
    m = re.match(r'(cngf)(\d{4})_(m\d.*)', name_lower)
    if m:
        census = 'cngf'
        year = m.group(2)
        module = CNGF_M_CODE_MAP.get(m.group(3), m.group(3))
        return census, year, module
    
    # Patrón 3: Genérico censo+año+módulo
    m = re.match(r'(cnge|cngf|cngmd)(\d{4})_(.+)', name_lower)
    if m:
        census = m.group(1)
        year = m.group(2)
        module_raw = m.group(3)
        
        if census == 'cngmd' and module_raw.startswith('m'):
            module = CNGMD_M_CODE_MAP.get(module_raw, module_raw)
        elif census == 'cngf' and module_raw.startswith('m'):
            module = CNGF_M_CODE_MAP.get(module_raw, module_raw)
        else:
            module = XLSX_THEMATIC_MAP.get(module_raw, module_raw)
        
        return census, year, module
    
    return None, None, None


def parse_root_file(filename):
    """Parsea nombre de archivo largo en raíz del proyecto."""
    m = re.search(r'Gobierno Federal (\d{4})', filename)
    if m:
        census = 'cngf'
        year = m.group(1)
        name_lower = filename.lower()
        
        if 'marco conceptual' in name_lower:
            module = 'marco_conceptual'
        elif 'control interno' in name_lower:
            module = 'control_interno_anticorrupcion'
        elif 'estructura organizacional' in name_lower:
            module = 'estructura_organizacional_recursos'
        elif 'tramites y servicios' in name_lower:
            module = 'tramites_servicios'
        elif 'administracion de archivos' in name_lower:
            module = 'administracion_archivos_gestion_documental'
        elif 'contrataciones publicas' in name_lower:
            module = 'contrataciones_publicas'
        elif 'programas sociales' in name_lower:
            module = 'programas_sociales'
        else:
            module = 'desconocido'
        
        ext = 'pdf' if filename.endswith('.pdf') else 'xlsx'
        return census, year, module, ext
    
    return None, None, None, None


# ============================================================
# 3. RENOMBRADO PRINCIPAL
# ============================================================

def collect_renames():
    """Recolecta todas las operaciones de renombrado, manejando duplicados entre raíz y microdatos_tabulados/."""
    operations = []
    microdatos_targets = {}
    
    # Primera pasada: microdatos_tabulados/
    for f in sorted(os.listdir(BASE)):
        src = BASE / f
        if not src.is_file():
            continue
        
        # Saltar archivos que ya siguen la convención objetivo
        if re.match(r'^(cng[fe]|cngmd)_(\d{4}|\d{4}_\d{4})_.+\.(dbf\.zip|xlsx|txt|pdf)$', f):
            continue
        
        census = year = module = ext = None
        
        if f.endswith('_dbf.zip') or '_dbf.zip' in f:
            census, year, module = parse_dbf_zip(f)
            ext = 'dbf.zip'
            ftype = 'microdatos'
        elif f.endswith('.xlsx'):
            census, year, module = parse_xlsx(f)
            ext = 'xlsx'
            ftype = 'tabulados'
        elif f.endswith('.txt'):
            ftype = 'descripcion'
            if 'estatales' in f.lower():
                census = 'cnge'
            elif 'municipales' in f.lower():
                census = 'cngmd'
            elif 'gobierno federal' in f.lower():
                census = 'cngf'
            else:
                continue
            ext = 'txt'
            module = f.replace('.txt', '').lower().replace(' ', '_').replace('.', '')
            if 'microdatos' in module:
                module = 'listado_microdatos'
            elif 'tabulados' in module:
                module = 'listado_tabulados'
            year = '2020_2025'
        else:
            continue
        
        if not census or not year or not module:
            print(f"  ⚠ SIN PARSEO: {f}")
            continue
        
        new_name = f"{census}_{year}_{module}_{ftype}.{ext}" if ftype != 'descripcion' else f"{census}_{year}_{module}.{ext}"
        dst = BASE / new_name
        
        if src == dst:
            continue
        
        md5 = md5_file(src)
        microdatos_targets[new_name] = (str(src), md5)
        operations.append((str(src), str(dst), md5, f))
    
    # Segunda pasada: archivos raíz
    root_files = [
        f for f in os.listdir(ROOT)
        if f.startswith("Censo Nacional de Gobierno Federal") and (f.endswith('.xlsx') or f.endswith('.pdf'))
    ]
    
    for f in sorted(root_files):
        src = ROOT / f
        if not src.is_file():
            continue
        census, year, module, ext = parse_root_file(f)
        if not census or not year or not module:
            print(f"  ⚠ SIN PARSEO RAÍZ: {f}")
            continue
        
        ftype = 'marco_conceptual' if 'marco_conceptual' in module else 'tabulados'
        if ftype == 'marco_conceptual':
            new_name = f"{census}_{year}_{module}.{ext}"
        else:
            new_name = f"{census}_{year}_{module}_{ftype}.{ext}"
        dst = BASE / new_name
        root_md5 = md5_file(src)
        
        # Verificar duplicados contra microdatos_tabulados
        if new_name in microdatos_targets:
            micro_md5 = microdatos_targets[new_name][1]
            if micro_md5 == root_md5:
                print(f"  ℹ DUPLICADO (omitir): {f} → ya existe como {new_name} (mismo contenido)")
                continue
            else:
                new_name2 = new_name.replace(f'.{ext}', f'_desde_raiz.{ext}')
                dst = BASE / new_name2
                print(f"  ⚠ CONTENIDO DIFERENTE: {f} → {new_name2}")
        elif dst.exists():
            existing_md5 = md5_file(dst)
            if existing_md5 == root_md5:
                print(f"  ℹ DUPLICADO (omitir): {f} → ya existe como {new_name}")
                continue
            else:
                new_name2 = new_name.replace(f'.{ext}', f'_desde_raiz.{ext}')
                dst = BASE / new_name2
        
        operations.append((str(src), str(dst), root_md5, f))
    
    return operations


def execute_renames(operations):
    """Ejecuta y registra todas las operaciones de renombrado."""
    if not operations:
        print("No hay operaciones para realizar.")
        return
    
    print(f"\n{'='*70}")
    print(f"Operaciones planificadas: {len(operations)}")
    print(f"{'='*70}\n")
    
    # Verificar colisiones
    dsts = [op[1] for op in operations]
    if len(dsts) != len(set(dsts)):
        dupes = [k for k, v in Counter(dsts).items() if v > 1]
        print(f"❌ COLISIONES DETECTADAS: {dupes}")
        print("Abortando. Corregir mapeos y reintentar.")
        return
    
    # Escribir manifiesto
    with open(LOG, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ruta_anterior', 'ruta_nueva', 'md5', 'estado'])
        
        success = 0
        for old, new, md5_hash, display_name in operations:
            try:
                os.rename(old, new)
                writer.writerow([old, new, md5_hash, 'renombrado'])
                print(f"  ✅ {display_name}")
                print(f"     → {Path(new).name}")
                success += 1
            except Exception as e:
                writer.writerow([old, new, md5_hash, f'error: {e}'])
                print(f"  ❌ {display_name}: {e}")
    
    print(f"\n{'='*70}")
    print(f"Renombrados: {success}/{len(operations)}")
    print(f"Bitácora: {LOG}")
    print(f"{'='*70}")


# ============================================================
# 4. EJECUCIÓN
# ============================================================

if __name__ == '__main__':
    print(f"{'='*70}")
    print(f"NORMALIZADOR DE NOMBRES")
    print(f"Modo: {'SOLO SIMULACIÓN' if DRY_RUN else 'EJECUTAR'}")
    print(f"{'='*70}\n")
    
    operations = collect_renames()
    
    if DRY_RUN:
        print(f"\nOperaciones planificadas: {len(operations)}")
        print("\nEjemplo de operaciones:")
        for old, new, _, display in operations[:10]:
            print(f"  {display}")
            print(f"    → {Path(new).name}")
        if len(operations) > 10:
            print(f"  ... y {len(operations)-10} más")
        print(f"\nEjecutar con --execute para aplicar.")
    else:
        execute_renames(operations)
