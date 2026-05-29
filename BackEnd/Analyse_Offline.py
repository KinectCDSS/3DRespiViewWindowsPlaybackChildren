import os
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, butter, filtfilt

def butter_lowpass_filter(data, cutoff, fs, order=1):
    """Applique un filtre passe-bas Butterworth pour lisser le signal brut."""
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    y = filtfilt(b, a, data)
    return y

def remove_outliers(data):
    """Nettoie les anomalies (outliers) sur les variations du signal (Identique au Backend)."""
    if len(data) < 2: 
        return data
    data_cleaned = np.copy(data)
    differences = np.diff(data_cleaned)
    iqr = np.percentile(differences, 75) - np.percentile(differences, 25)
    lower_bound = np.percentile(differences, 25) - 0.5 * iqr
    upper_bound = np.percentile(differences, 75) + 0.5 * iqr
    for i in range(1, len(differences)):
        if differences[i] < lower_bound or differences[i] > upper_bound:
            if i + 1 < len(data_cleaned): 
                data_cleaned[i + 1] = data_cleaned[i]
    return data_cleaned

def lire_fichier_sta(file_path):
    """Parseur optimisé pour les fichiers .sta du ventilateur SERVO-U."""
    sampling_time_ms = 10.0  # Valeur par défaut (10 ms = 100 Hz)
    data_lines = []
    headers = None

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            clean_line = line.strip()
            if "Sampling Time:" in line:
                try:
                    time_str = line.split("Sampling Time:")[1].lower().replace("ms", "").strip()
                    sampling_time_ms = float(time_str)
                except Exception:
                    pass
            elif clean_line.startswith('%% Time(ms)'):
                headers = clean_line.replace('%%', '').split()
            elif not clean_line.startswith('%') and clean_line:
                data_lines.append(clean_line)

    fs = 1000.0 / sampling_time_ms
    data_str = '\n'.join(data_lines)
    df = pd.read_csv(io.StringIO(data_str), sep=r'\s+', names=headers if headers else None)
    
    if 'Ch_002' in df.columns:
        signal = df['Ch_002'].values
        nom_signal = "Volume Ventilateur (Ch_002)"
    else:
        signal = df.iloc[:, 5].values if df.shape[1] > 5 else df.iloc[:, 3].values
        nom_signal = "Signal Ventilateur"
        
    return signal, fs, nom_signal

def analyser_donnees():
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    input_dir = os.path.join(current_dir, "input")
    output_dir = os.path.join(current_dir, "output")
    
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    os.system("title Saisie Analyse 3DRespiView Offline")
    os.system("mode con: cols=75 lines=20")
    
    print("=====================================================================")
    print("              SAISIE & ANALYSE OFF-LINE (CSV / STA)")
    print("=====================================================================")

    import sys
    if len(sys.argv) > 1 and sys.argv[1].strip():
        fichier_input = sys.argv[1].strip()
        print(f"\n[Auto] Fichier transmis par l'interface : {fichier_input}")
    else:
        fichiers_dispos = [f for f in os.listdir(input_dir) if f.endswith(('.csv', '.sta'))]
        if fichiers_dispos:
            print("\nFichiers disponibles dans le dossier 'input/' :")
            for f in fichiers_dispos:
                print(f"  - {f}")
        else:
            print("\n[Attention] Le dossier 'input/' est vide.")
            
        fichier_input = input("\nEntrez le nom complet du fichier (ex: 579.sta) : ").strip()
    input_path = os.path.join(input_dir, fichier_input)
    
    if not os.path.exists(input_path):
        print(f"\n[Erreur] Le fichier n'existe pas : {fichier_input}")
        import time; time.sleep(2); return

    ext = os.path.splitext(fichier_input)[1].lower()
    if ext == '.sta':
        print(f"\n[Format] Fichier Ventilateur SERVO-U (.sta)")
        signal_charge, fs, type_label = lire_fichier_sta(input_path)
        signal_brut = np.copy(signal_charge) 
    elif ext == '.csv':
        print(f"\n[Format] Fichier 3DRespiView (.csv)")
        df_csv = pd.read_csv(input_path, header=None, dtype=np.float64, sep=',', decimal='.')
        signal_charge = df_csv.iloc[:, 0].values.astype(np.float64)
        
        # --- AUCUNE INVERSION ICI ---
        # Le signal est pris brut tel qu'il a été enregistré par le Program.cs
        signal_brut = np.copy(signal_charge) 
        
        fs = 30.0  
        type_label = "Amplitude 3DRespiView"
    else:
        print("\n[Erreur] Format non supporté (.csv ou .sta uniquement).")
        import time; time.sleep(2); return
    
    print(f"[OK] Signal chargé tel quel : {len(signal_brut)} points à {fs} Hz.")

    # -------------------------------------------------------------------------
    # NETTOYAGE DES OUTLIERS 
    # -------------------------------------------------------------------------
    print("[Nettoyage] Suppression des anomalies de signal (Outliers)...")
    signal_propre = remove_outliers(signal_brut)

    # -------------------------------------------------------------------------
    # HARMONISATION DU FILTRAGE ADAPTATIF AVEC LE BACKEND.PY
    # -------------------------------------------------------------------------
    if ext == '.sta':
        print("[Filtrage] Signal .sta détecté : Shunt complet du filtre Butterworth.")
        signal_filtre = np.copy(signal_propre)
    else:
        if len(signal_propre) > 10:
            # Étape 1 : Pré-filtrage large pour estimer la FR brute
            b_wide, a_wide = butter(N=1, Wn=5.0 / (0.5 * fs), btype='low')
            y_wide = filtfilt(b_wide, a_wide, signal_propre)
            troughs_est, _ = find_peaks(-y_wide, distance=int(fs * 0.66))
            
            if len(troughs_est) >= 2:
                total_points_fenetre = troughs_est[-1] - troughs_est[0]
                duree_fenetre_sec = total_points_fenetre / fs
                FR_estimere = (len(troughs_est) - 1) * 60 / duree_fenetre_sec
            else:
                FR_estimere = 35.0
                
            # Étape 2 : Calcul de la fréquence de coupure adaptative exacte
            freq_patient_hz = FR_estimere / 60.0
            fc_adaptative = max(freq_patient_hz * 5.0, 2.0)
            fc_adaptative = min(fc_adaptative, 5.5)
            print(f"[Filtrage] Mode CSV Adaptatif -> FR estimée: {round(FR_estimere, 1)} RPM -> Coupure Filtre: {round(fc_adaptative, 2)} Hz")
            
            signal_filtre = butter_lowpass_filter(signal_propre, fc_adaptative, fs, order=1)
        else:
            signal_filtre = np.copy(signal_propre)

    # -------------------------------------------------------------------------
    # ANALYSE ET RECHERCHE DES PICS SUR LE SIGNAL TRAITÉ
    # -------------------------------------------------------------------------
    fr_reference = FR_estimere if 'FR_estimere' in locals() else 15.0

    # Calcul de la distance minimale adaptative basée sur la FR de référence
    troughs_pre, _ = find_peaks(-signal_filtre, distance=int(fs * 0.5))
    if len(troughs_pre) >= 2:
        FR_m = (len(troughs_pre) - 1) * 60 / ((troughs_pre[-1] - troughs_pre[0]) / fs)
    else:
        FR_m = fr_reference
        
    dist_adaptative = max(int((fs * 60) / FR_m * 0.6), 10)
    amp_vol = np.percentile(signal_filtre, 98) - np.percentile(signal_filtre, 2)

    # Détection des pics (hauts) et des vallées (bas)
    pics, _ = find_peaks(signal_filtre, distance=dist_adaptative, prominence=amp_vol * 0.15)
    vallees, _ = find_peaks(-signal_filtre, distance=dist_adaptative, prominence=amp_vol * 0.15)

    # Extraction cycle par cycle (Du creux de départ jusqu'au sommet du pic)
    resultats_cycles = []
    if len(pics) >= 2 and len(vallees) >= 1:
        for i in range(1, len(pics)):
            temps_echantillon = pics[i]
            duree_cycle_sec = (pics[i] - pics[i-1]) / fs
            
            # Recherche de la vallée qui précède immédiatement le pic
            vallees_avant = vallees[vallees < pics[i]]
            
            if len(vallees_avant) > 0:
                derniere_vallee = vallees_avant[-1]
                amplitude_cycle = signal_filtre[pics[i]] - signal_filtre[derniere_vallee]
            else:
                amplitude_cycle = np.nan
                
            resultats_cycles.append({
                "Numero_Cycle": i, 
                "Index_Echantillon_Pic": temps_echantillon,
                "Temps_Sec": temps_echantillon / fs,
                "Duree_Cycle_Sec": duree_cycle_sec,
                "FR_instantanee_CPM": 60.0 / duree_cycle_sec,
                "Amplitude_Cycle": amplitude_cycle 
            })

    df_cycles = pd.DataFrame(resultats_cycles)

    # Statistiques globales
    total_secondes = len(signal_propre) / fs
    if len(vallees) >= 2:
        fr_moyenne_globale = (len(vallees) - 1) * 60 / ((vallees[-1] - vallees[0]) / fs)
    elif len(pics) >= 2:
        fr_moyenne_globale = (len(pics) - 1) * 60 / ((pics[-1] - pics[0]) / fs)
    else:
        fr_moyenne_globale = FR_m

    amplitude_moyenne_globale = df_cycles["Amplitude_Cycle"].mean() if not df_cycles.empty else np.nan
    
    print(f"\nCalcul effectué : {len(pics)} pics trouvés (FR Globale : {round(fr_moyenne_globale, 1)} RPM)")

    df_cycles.to_csv(os.path.join(output_dir, f"{fichier_input}_analyse_cycles.csv"), index=False, encoding='utf-8', float_format='%.15f')
    
    df_resume = pd.DataFrame([{
        "Fichier_Source": fichier_input, 
        "Type_Signal": type_label, 
        "Duree_Total_Sec": round(total_secondes, 2),
        "Total_Cycles": len(pics), 
        "FR_Moyenne_CPM": round(fr_moyenne_globale, 2), 
        "Amplitude_Moyenne": round(amplitude_moyenne_globale, 2)
    }])
    df_resume.to_csv(os.path.join(output_dir, f"{fichier_input}_resume_global.csv"), index=False, encoding='utf-8', float_format='%.15f')

    print("\n[Succès] Rapports générés dans le dossier 'output/'.")
    import time; time.sleep(1)
    
if __name__ == "__main__":
    analyser_donnees()