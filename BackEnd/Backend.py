import socket
import numpy as np
from scipy.signal import find_peaks, butter, filtfilt
from flask import Flask, Response, jsonify, send_from_directory, request
from flask_cors import CORS
import csv
import os
import subprocess
import psutil
import time
import shutil

app = Flask(__name__, static_folder='./')
CORS(app)

host = '127.0.0.1'
port = 5000
sampling_rate_kinect_hz = 30  
butter_order = 2

mode_offline_actif = False
signal_offline_raw = []
est_fichier_sta = False  # Indicateur pour savoir si c'est un signal ventilateur pur
current_filename = ""    # Centralise le nom réel du fichier (ex: 579.mkv, 579.sta)

# Buffers globaux d'acquisition
x_data = np.array([])
y_data = np.array([])
y_filtered_data = np.array([])
dy_dx = np.array([])

flag = True
flagScale = True
scale = 0

def clean_output_directories():
    """Supprime tout le contenu des dossiers Output et output au démarrage du backend."""
    dossiers_a_vider = ['./Output', './output']
    print("=====================================================================")
    print("             NETTOYAGE DES DOSSIERS DE SORTIE (OUTPUT)")
    print("=====================================================================")
    
    for dossier in dossiers_a_vider:
        if os.path.exists(dossier):
            for filename in os.listdir(dossier):
                file_path = os.path.join(dossier, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    print(f"[Supprimé] {file_path}")
                except Exception as e:
                    print(f"[Erreur] Impossible de supprimer {file_path} : {e}")
        else:
            os.makedirs(dossier, exist_ok=True)
            print(f"[Créé] Dossier initialisé : {dossier}")
    print("=====================================================================\n")

def remove_outliers(data):
    if len(data) < 2: return data
    differences = np.diff(data)
    iqr = np.percentile(differences, 75) - np.percentile(differences, 25)
    lower_bound = np.percentile(differences, 25) - 0.5*iqr
    upper_bound = np.percentile(differences, 75) + 0.5*iqr
    for i in range(1, len(differences)):
        if differences[i] < lower_bound or differences[i] > upper_bound:
            if i + 1 < len(data): data[i + 1] = data[i]
    return data

def store_non_filtered_data_in_csv(data):
    global current_filename
    output_dir = './Output'
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{current_filename}_non_filtrered_data.csv"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for value in data: writer.writerow([value])

def store_data_in_csv(data):
    global current_filename
    output_dir = './Output'
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{current_filename}_filtered_data.csv"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for value in data: writer.writerow([value])

def generate_data():
    global x_data, y_data, scale, flag, flagScale, y_filtered_data, dy_dx
    global mode_offline_actif, signal_offline_raw, est_fichier_sta

    # INITIALISATION ET RAZ DES BUFFERS DÈS QUE REACT SE CONNECTE AU STREAM
    flag = True
    flagScale = True
    scale = 0
    y_data = np.array([])
    x_data = np.array([])
    y_filtered_data = np.array([])
    dy_dx = np.array([])

    # -------------------------------------------------------------------------
    # CAS A : SIMULATION DE TRANSMISSION OFF-LINE (900 POINTS EN 30 SECONDES)
    # -------------------------------------------------------------------------
    if mode_offline_actif and len(signal_offline_raw) > 0:
        print(f"[Streaming Offline] Diffusion de la fenêtre rééchantillonnée (900 points)...")
        
        for valeur in signal_offline_raw:
            if not flag: break
            y_data = np.append(y_data, valeur)
            x_data = np.append(x_data, x_data.size / 30)
            yield f"data: {valeur}\n\n"
            time.sleep(0.001) 
            
        yield "data: ENDRAW\n\n"

        # TRAITEMENT DU SIGNAL ADAPTATIF OFFLINE
        if len(y_data) > butter_order * 5:
            if est_fichier_sta:
                # BRANCHEMENT DIRECT VENTILATEUR : Pas de filtrage, le signal brut est préservé à 100%
                print("[Traitement] Signal .sta détecté : Shunt du filtrage Butterworth.")
                y_filtered_data = np.copy(y_data)
            else:
                # BRANCHEMENT OPTIQUE (CSV) : Nettoyage des outliers + Filtre à 1.5Hz requis
                y_data_cleaned = remove_outliers(y_data)
                nyq = 0.5 * sampling_rate_kinect_hz
                b_adapt, a_adapt = butter(N=2, Wn=1.5 / nyq, btype='low')
                y_filtered_data = filtfilt(b_adapt, a_adapt, y_data_cleaned)
            
            # Envoi des données filtrées/préservées
            for value in y_filtered_data:
                if not flag: break
                yield f"data: {value}\n\n"
            yield "data: ENDFILTERED\n\n"
            
            # Dérivée première pour obtenir le débit (Flow)
            dy_dx = np.gradient(y_filtered_data, x_data[:len(y_filtered_data)])
            for value in dy_dx:
                if not flag: break
                yield f"data: {value}\n\n"
                
        yield "data: END\n\n"
        print("[Streaming Offline] Fin de la transmission offline.")
        return

    # -------------------------------------------------------------------------
    # CAS B : MODE VIDEO ACQUISITION KINECT (D'ORIGINE INCHANGÉ)
    # -------------------------------------------------------------------------
    conn = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try: sock.bind((host, port))
            except socket.error: return
            sock.listen(1)
            print(f"En attente de connexion sur {host}:{port}...")
            conn, addr = sock.accept()

            remainder = ""
            while flag:
                packet = conn.recv(4096)
                if not packet: break
                chunk = packet.decode('ascii', errors='ignore')
                buffer_data = remainder + chunk
                lines = buffer_data.splitlines(keepends=True)

                if lines and not lines[-1].endswith('\n'): remainder = lines.pop()
                else: remainder = ""

                for line in lines:
                    data_clean = line.strip()
                    if not data_clean: continue
                    if "END" in data_clean:
                        flag = False
                        break

                    try:
                        clean_numeric = data_clean.replace(',', '.')
                        y_value = -float(clean_numeric)

                        if flagScale:
                            scale = y_value
                            flagScale = False

                        adjusted_value = y_value - scale
                        y_data = np.append(y_data, adjusted_value)
                        x_data = np.append(x_data, x_data.size / 30)

                        yield f"data: {adjusted_value}\n\n"
                    except ValueError: continue
                if not flag: break
            yield "data: ENDRAW\n\n"
    except Exception: pass
    finally:
        if conn: conn.close()

    y_data_cleaned = remove_outliers(y_data)
    store_non_filtered_data_in_csv(y_data_cleaned)

    if len(y_data_cleaned) > butter_order * 5:
        b_wide, a_wide = butter(N=2, Wn=4.0 / (0.5 * sampling_rate_kinect_hz), btype='low')
        y_wide = filtfilt(b_wide, a_wide, y_data_cleaned)
        troughs_est, _ = find_peaks(-y_wide, distance=20)
        
        FR_estimere = (len(troughs_est) - 1) * 60 / (x_data[troughs_est[-1]] - x_data[troughs_est[0]]) if len(troughs_est) >= 2 else 35.0
        fc_adaptative = min(max(FR_estimere / 60.0 * 3.0, 1.2), 4.5)
        
        b_adapt, a_adapt = butter(N=2, Wn=fc_adaptative / (0.5 * sampling_rate_kinect_hz), btype='low')
        y_filtered_data = filtfilt(b_adapt, a_adapt, y_data_cleaned)
        store_data_in_csv(y_filtered_data)
        
        for value in y_filtered_data: yield f"data: {value}\n\n"
        yield "data: ENDFILTERED\n\n"
        
        dy_dx = np.gradient(y_filtered_data, x_data[:len(y_filtered_data)])
        for value in dy_dx: yield f"data: {value}\n\n"
        yield "data: END\n\n"

@app.route('/stream')
def stream():
    return Response(generate_data(), content_type='text/event-stream')

@app.route('/run-analysis', methods=['POST'])
def run_analysis():
    global mode_offline_actif, signal_offline_raw, est_fichier_sta, current_filename
    try:
        data = request.get_json() or {}
        fichier_cible = data.get('filename', '').strip()
        current_filename = fichier_cible
        
        # FORCE LA CONVERSION EN ENTIER (ex: 28.0 devient 28)
        temps_depart_sec = int(float(data.get('start_time', 0)))
        
        ext = os.path.splitext(fichier_cible)[1].lower()
        racine_dir = os.path.dirname(os.path.abspath(__file__))

        if ext == '.mkv':
            mode_offline_actif = False
            est_fichier_sta = False
            file_path = os.path.join(racine_dir, 'Kinect_V1.exe')
            if not os.path.exists(file_path):
                return jsonify({"message": "Binaire Kinect_V1.exe introuvable."}), 404
            
            nom_mkv_pur = fichier_cible.replace('.mkv', '')
            arguments = [file_path, nom_mkv_pur, str(temps_depart_sec)]
            
            subprocess.Popen(arguments, cwd=racine_dir, creationflags=0x00000010)
            
            print(f"[Succès MKV] Lancement de {file_path} avec {nom_mkv_pur} à {temps_depart_sec} secondes.")
            return jsonify({"message": f"Acquisition vidéo démarrée pour : {fichier_cible} (Départ: {temps_depart_sec}s)"}), 200

        else:
            mode_offline_actif = True
            signal_offline_raw = []
            est_fichier_sta = (ext == '.sta')
            
            arguments = ['cmd', '/c', 'py', 'Analyse_Offline.py', fichier_cible]
            process = subprocess.Popen(arguments, cwd=racine_dir, creationflags=0x00000010)
            process.wait()

            input_dir = os.path.join(racine_dir, 'input')
            input_path = os.path.join(input_dir, fichier_cible)
            
            if est_fichier_sta:
                from Analyse_Offline import lire_fichier_sta
                signal_complet, fs, _ = lire_fichier_sta(input_path)
            elif ext == '.csv':
                with open(input_path, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    signal_complet = np.array([float(row[0].replace(',', '.')) for row in reader if row])
                fs = 30.0
            else:
                return jsonify({"message": "Format non supporté."}), 400

            if len(signal_complet) > 0:
                index_debut = int(temps_depart_sec * fs)
                index_fin = int((temps_depart_sec + 30.0) * fs)
                
                if index_debut >= len(signal_complet): index_debut = 0
                if index_fin > len(signal_complet): index_fin = len(signal_complet)
                
                signal_fenetre = signal_complet[index_debut:index_fin]
                
                temps_original = np.arange(len(signal_fenetre)) / fs
                temps_cible = np.arange(900) / 30.0
                signal_harmonisie = np.interp(temps_cible, temps_original, signal_fenetre)
                
                signal_offline_raw = [float(v) for v in (signal_harmonisie - signal_harmonisie[0])]

            return jsonify({"message": f"Fichier préparé et harmonisé de {temps_depart_sec}s à {temps_depart_sec + 30}s."}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/stats', methods=['GET'])
def send_stats():
    global y_filtered_data, dy_dx, x_data, mode_offline_actif, current_filename
    if len(y_filtered_data) == 0:
        return jsonify({"message": "Aucune donnée filtrée disponible."}), 400

    troughs_pre, _ = find_peaks(-y_filtered_data, distance=20)
    FR_mesuree = (len(troughs_pre) - 1) * 60 / (x_data[troughs_pre[-1]] - x_data[troughs_pre[0]]) if len(troughs_pre) >= 2 else 35.0

    dist_adaptative = max(int((30 * 60) / FR_mesuree * 0.6), 10)
    amp_vol = np.percentile(y_filtered_data, 98) - np.percentile(y_filtered_data, 2)
    peaks, troughs = find_peaks(y_filtered_data, distance=dist_adaptative, prominence=amp_vol * 0.15)[0], find_peaks(-y_filtered_data, distance=dist_adaptative, prominence=amp_vol * 0.15)[0]

    volume, inspiration_time, expiration_time = [], [], []
    inspiration_time_mean, expiration_time_mean, volume_minute = 0, 0, 0

    if len(peaks) > 0 and len(troughs) >= 2:
        if peaks[0] < troughs[0]: peaks = peaks[1:]
        if len(peaks) > 0 and peaks[-1] > troughs[-1]: peaks = peaks[:-1]

        if len(peaks) + 1 == len(troughs) and len(peaks) > 0:
            for i in range(2, len(troughs) + 1, 1):
                volume.append(float(y_filtered_data[peaks[i - 2]] - y_filtered_data[troughs[i - 1]]))
                inspiration_time.append(float(x_data[peaks[i - 2]] - x_data[troughs[i - 2]]))
                expiration_time.append(float(x_data[troughs[i - 1]] - x_data[peaks[i - 2]]))
            volume_minute = sum(volume) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
            inspiration_time_mean = np.mean(inspiration_time)
            expiration_time_mean = np.mean(expiration_time)

    dist_deriv = max(int(dist_adaptative / 2), 8)
    seuil_prominence_debit = (np.percentile(dy_dx, 95) - np.percentile(dy_dx, 5)) * 0.35  
    peaks_derivative, troughs_derivative = find_peaks(dy_dx, distance=dist_deriv, prominence=seuil_prominence_debit)[0], find_peaks(-dy_dx, distance=dist_deriv, prominence=seuil_prominence_debit)[0]
    
    if len(peaks_derivative) == 0: peaks_derivative = find_peaks(dy_dx, distance=dist_deriv)[0]
    if len(troughs_derivative) == 0: troughs_derivative = find_peaks(-dy_dx, distance=dist_deriv)[0]
    
    peak_flow_mean = np.mean(dy_dx[peaks_derivative]) if len(peaks_derivative) > 0 else 0
    troughs_flow_mean = np.mean(-dy_dx[troughs_derivative]) if len(troughs_derivative) > 0 else 0

    if inspiration_time_mean > 0:
        rapport_ie = f"1/{round(expiration_time_mean / inspiration_time_mean, 1)}"
    else:
        rapport_ie = "1/0"

    # =========================================================================
    # SAUVEGARDE AUTOMATIQUE SÉCURISÉE (MKV / ONLINE ONLY)
    # =========================================================================
    if not mode_offline_actif:
        try:
            import pandas as pd
            import matplotlib.pyplot as plt
            
            output_dir = './output'
            os.makedirs(output_dir, exist_ok=True)
            
            nom_base = request.args.get('filename', current_filename).strip()

            # 1. Sauvegarde du fichier Cycle par Cycle
            resultats_cycles = []
            for i in range(len(volume)):
                resultats_cycles.append({
                    "Numero_Cycle": i + 1,
                    "Temps_Sec": round(float(x_data[peaks[i]]), 2) if i < len(peaks) else 0,
                    "Duree_Cycle_Sec": round(inspiration_time[i] + expiration_time[i], 2),
                    "FR_instantanee_CPM": round(60.0 / (inspiration_time[i] + expiration_time[i]), 1) if (inspiration_time[i] + expiration_time[i]) > 0 else 0,
                    "Amplitude_Cycle": round(volume[i], 3)
                })
            
            if resultats_cycles:
                df_cycles = pd.DataFrame(resultats_cycles)
                df_cycles.to_csv(os.path.join(output_dir, f"{nom_base}_analyse_cycles.csv"), index=False, encoding='utf-8')

            # 2. Sauvegarde du Résumé Global
            df_resume = pd.DataFrame([{
                "Fichier_Source": nom_base,
                "Type_Signal": "Amplitude 3DRespiView Live",
                "Duree_Total_Sec": round(float(x_data[-1]), 2) if len(x_data) > 0 else 0,
                "Total_Cycles": len(peaks),
                "FR_Moyenne_CPM": round(FR_mesuree, 2),
                "Amplitude_Moyenne": round(np.mean(volume), 2) if len(volume) > 0 else 0
            }])
            df_resume.to_csv(os.path.join(output_dir, f"{nom_base}_resume_global.csv"), index=False, encoding='utf-8')

            # 3. Génération de la courbe graphique de contrôle
            plt.figure(figsize=(12, 6))
            plt.plot(y_filtered_data, label="Signal Filtré Adaptatif", color="blue", linewidth=1.2)
            plt.scatter(peaks, y_filtered_data[peaks], color="red", marker="^", s=50, label="Pics")
            plt.scatter(troughs, y_filtered_data[troughs], color="green", marker="v", s=50, label="Creux")
            plt.title(f"Suivi Acquisition - {nom_base}")
            plt.grid(True, linestyle="--", alpha=0.5)
            plt.legend(loc="upper right")
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{nom_base}_courbe_analyse.png"), dpi=300)
            plt.close()
            print(f"[Sauvegarde] Rapports générés avec succès pour {nom_base}")
            
        except Exception as e:
            print(f"[Erreur Sauvegarde MKV] Impossible de générer les rapports : {e}")

    return jsonify({
        "Frequence respiratoire (Rpm)": round(FR_mesuree),
        "Volume minute expire (L/min)": round(volume_minute / 1000, 2),
        "Volume courant moyen (mL)": round(np.mean(volume)) if len(volume) > 0 else 0,
        "Temps moyen inspiration (s)": round(inspiration_time_mean, 1),
        "Temps moyen expiration (s)": round(expiration_time_mean, 1),
        "Rapport I/E": rapport_ie,
        "Debit de pointe moyen (mL/s)": round(peak_flow_mean),
        "Debit de creux moyen (mL/s)": round(troughs_flow_mean),
        "Cooordonees x des pics": [float(x_data[p]) for p in peaks],
        "Cooordonees y des pics": [float(y_filtered_data[p]) for p in peaks],
        "Cooordonees x des creux": [float(x_data[t]) for t in troughs],
        "Cooordonees y des creux": [float(y_filtered_data[t]) for t in troughs],
        "Coordonnees x des pics de debit": [float(x_data[p]) for p in peaks_derivative],
        "Coordonnees y des pics de debit": [float(dy_dx[p]) for p in peaks_derivative],
        "Coordonnees x des creux de debit": [float(x_data[t]) for t in troughs_derivative],
        "Coordonnees y des creux de debit": [float(dy_dx[t]) for t in troughs_derivative],
        "Volumes (mL)": [round(v, 1) for v in volume],
        "Temps inspiration (s)": [round(t, 2) for t in inspiration_time],
        "Temps expiration (s)": [round(t, 2) for t in expiration_time]
    })

@app.route('/image/<path:filename>')
def get_image(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    RUNS_DIR = os.path.join(current_dir, 'runs/obb/predict')
    return send_from_directory(RUNS_DIR, filename)

@app.route('/close', methods=['POST'])
def close():
    try: os.system("taskkill /f /im node.exe")
    finally: os.kill(os.getpid(), 9)

if __name__ == '__main__':
    # EXECUTION DU NETTOYAGE DES DOSSIERS AVANT LE LANCEMENT DE L'APP
    clean_output_directories()
    app.run(debug=False, host='127.0.0.1', port=8000, threaded=True)