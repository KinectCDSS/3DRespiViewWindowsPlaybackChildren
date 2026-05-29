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
butter_order = 1

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
    """Initialise les dossiers et nettoie uniquement les résidus YOLO au démarrage."""
    os.makedirs('./Output', exist_ok=True)
    os.makedirs('./output', exist_ok=True)
    
    # Nettoyage préventif du dossier de prédiction YOLO pour éviter les conflits de session
    runs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runs')
    if os.path.exists(runs_dir):
        try:
            shutil.rmtree(runs_dir)
            print("[Démarrage] Ancien répertoire de prédictions YOLO nettoyé.")
        except Exception as e:
            print(f"[Démarrage] Avis de nettoyage du dossier runs : {e}")

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
        for value in data: writer.writerow([f"{value:.15f}"])

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

    flag = True
    flagScale = True
    scale = 0
    y_data = np.array([], dtype=np.float64)
    x_data = np.array([])
    y_filtered_data = np.array([])
    dy_dx = np.array([])

    if mode_offline_actif and len(signal_offline_raw) > 0:
        print(f"[Streaming Offline] Diffusion de la fenêtre rééchantillonnée (900 points)...")
        for valeur in signal_offline_raw:
            if not flag: break
            y_data = np.append(y_data, valeur)
            x_data = np.append(x_data, x_data.size / 30)
            yield f"data: {valeur}\n\n"
            time.sleep(0.001) 
        yield "data: ENDRAW\n\n"

        if len(y_data) > butter_order * 5:
            if est_fichier_sta:
                print("[Traitement] Signal .sta détecté : Shunt du filtrage Butterworth.")
                y_filtered_data = np.copy(y_data)
            else:
                y_data_cleaned = remove_outliers(y_data)
        
                # --- ALIGNEMENT ET CORRECTION DU BUG DE VARIABLE ---
                nyq = 0.5 * sampling_rate_kinect_hz
                b_wide, a_wide = butter(N=1, Wn=5.0 / nyq, btype='low')
                y_wide = filtfilt(b_wide, a_wide, y_data_cleaned)
                troughs_est, _ = find_peaks(-y_wide, distance=int(sampling_rate_kinect_hz * 0.66))
        
                if len(troughs_est) >= 2:
                    total_points_fenetre = troughs_est[-1] - troughs_est[0]
                    duree_fenetre_sec = total_points_fenetre / sampling_rate_kinect_hz
                    FR_estimere = (len(troughs_est) - 1) * 60 / duree_fenetre_sec
                else:
                    FR_estimere = 35.0
                
                freq_patient_hz = FR_estimere / 60.0
                fc_adaptative = max(freq_patient_hz * 5.0, 2.0)
                fc_adaptative = min(fc_adaptative, 5.5)
            
                b_adapt, a_adapt = butter(N=1, Wn=fc_adaptative / nyq, btype='low')
                y_filtered_data = filtfilt(b_adapt, a_adapt, y_data_cleaned)
            
            for value in y_filtered_data:
                if not flag: break
                yield f"data: {value}\n\n"
            yield "data: ENDFILTERED\n\n"
            
            dy_dx = np.gradient(y_filtered_data, x_data[:len(y_filtered_data)])
            for value in dy_dx:
                if not flag: break
                yield f"data: {value}\n\n"
        yield "data: END\n\n"
        return

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
                        y_value = -float(clean_numeric.replace(',', '.'))

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
        b_wide, a_wide = butter(N=1, Wn=5.0 / (0.5 * sampling_rate_kinect_hz), btype='low')
        y_wide = filtfilt(b_wide, a_wide, y_data_cleaned)
        troughs_est, _ = find_peaks(-y_wide, distance=int(sampling_rate_kinect_hz * 0.66))
        
        if len(troughs_est) >= 2:
            total_points_fenetre = troughs_est[-1] - troughs_est[0]
            duree_fenetre_sec = total_points_fenetre / sampling_rate_kinect_hz
            FR_estimere = (len(troughs_est) - 1) * 60 / duree_fenetre_sec
        else:
            FR_estimere = 35.0
            
        freq_patient_hz = FR_estimere / 60.0
        fc_adaptative = max(freq_patient_hz * 5.0, 2.0)
        fc_adaptative = min(fc_adaptative, 5.5)
        
        b_adapt, a_adapt = butter(N=1, Wn=fc_adaptative / (0.5 * sampling_rate_kinect_hz), btype='low')
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
                index_fin = index_debut + int(30.0 * fs)
    
                if index_debut >= len(signal_complet): index_debut = 0
                if index_fin > len(signal_complet): index_fin = len(signal_complet)
    
                signal_brut_fenetre = signal_complet[index_debut:index_fin]
    
                pas = max(1, len(signal_brut_fenetre) // 900)
                signal_final = signal_brut_fenetre[::pas][:900] 
    
                signal_offline_raw = [float(v) for v in (signal_final - signal_final[0])]

            return jsonify({"message": f"Fichier préparé et harmonisé de {temps_depart_sec}s à {temps_depart_sec + 30}s."}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/stats', methods=['GET'])
def send_stats():
    global y_filtered_data, dy_dx, x_data, mode_offline_actif, current_filename
    if len(y_filtered_data) == 0:
        return jsonify({"message": "Aucune donnée filtrée disponible."}), 400

    fs = float(sampling_rate_kinect_hz)

    troughs_pre, _ = find_peaks(-y_filtered_data, distance=int(fs * 0.5))
    if len(troughs_pre) >= 2:
        FR_mesuree = (len(troughs_pre) - 1) * 60 / (x_data[troughs_pre[-1]] - x_data[troughs_pre[0]])
    else:
        FR_mesuree = 35.0

    dist_adaptative = max(int((fs * 60) / FR_mesuree * 0.6), 10)
    amp_vol = np.percentile(y_filtered_data, 98) - np.percentile(y_filtered_data, 2)
    
    peaks, _ = find_peaks(y_filtered_data, distance=dist_adaptative, prominence=amp_vol * 0.15)
    troughs, _ = find_peaks(-y_filtered_data, distance=dist_adaptative, prominence=amp_vol * 0.15)

    volume, inspiration_time, expiration_time = [], [], []
    inspiration_time_mean, expiration_time_mean, volume_minute = 0, 0, 0

    # --- RESTRUCTURATION ROBUSTE DU COUPLAGE CYCLE PAR CYCLE (IDENTIQUE OFFLINE) ---
    if len(peaks) >= 2 and len(troughs) >= 1:
        for i in range(1, len(peaks)):
            vallees_avant = troughs[troughs < peaks[i]]
            if len(vallees_avant) > 0:
                derniere_vallee = vallees_avant[-1]
                volume.append(float(y_filtered_data[peaks[i]] - y_filtered_data[derniere_vallee]))
                inspiration_time.append(float(x_data[peaks[i]] - x_data[derniere_vallee]))
                expiration_time.append(float(x_data[derniere_vallee] - x_data[peaks[i - 1]]))
        
        if len(troughs) >= 2:
            volume_minute = sum(volume) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
        inspiration_time_mean = np.mean(inspiration_time) if inspiration_time else 0
        expiration_time_mean = np.mean(expiration_time) if expiration_time else 0

    if len(troughs) >= 2:
        fr_moyenne_globale = (len(troughs) - 1) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
    elif len(peaks) >= 2:
        fr_moyenne_globale = (len(peaks) - 1) * 60 / (x_data[peaks[-1]] - x_data[peaks[0]])
    else:
        fr_moyenne_globale = FR_mesuree

    dist_deriv = max(int(dist_adaptative * 0.75), 12)
    seuil_prominence_debit = (np.percentile(dy_dx, 95) - np.percentile(dy_dx, 5)) * 0.50  
    
    peaks_derivative, troughs_derivative = find_peaks(dy_dx, distance=dist_deriv, prominence=seuil_prominence_debit)[0], find_peaks(-dy_dx, distance=dist_deriv, prominence=seuil_prominence_debit)[0]
    
    if len(peaks_derivative) == 0: 
        peaks_derivative = find_peaks(dy_dx, distance=dist_deriv, prominence=seuil_prominence_debit * 0.5)[0]
    if len(troughs_derivative) == 0: 
        troughs_derivative = find_peaks(-dy_dx, distance=dist_deriv, prominence=seuil_prominence_debit * 0.5)[0]
    
    peak_flow_mean = np.mean(dy_dx[peaks_derivative]) if len(peaks_derivative) > 0 else 0
    troughs_flow_mean = np.mean(-dy_dx[troughs_derivative]) if len(troughs_derivative) > 0 else 0

    if inspiration_time_mean > 0:
        rapport_ie = f"1/{round(expiration_time_mean / inspiration_time_mean, 1)}"
    else:
        rapport_ie = "1/0"

    nom_base = request.args.get('filename', current_filename).strip()

    if not mode_offline_actif:
        try:
            import pandas as pd
            output_dir = './output'
            os.makedirs(output_dir, exist_ok=True)

            resultats_cycles = []
            for i in range(len(volume)):
                p_idx = i + 1
                if p_idx < len(peaks):
                    duree_c = float(x_data[peaks[p_idx]] - x_data[peaks[p_idx - 1]])
                    resultats_cycles.append({
                        "Numero_Cycle": i + 1,
                        "Temps_Sec": round(float(x_data[peaks[p_idx]]), 2),
                        "Duree_Cycle_Sec": round(duree_c, 2),
                        "FR_instantanee_CPM": round(60.0 / duree_c, 1) if duree_c > 0 else 0,
                        "Amplitude_Cycle": round(volume[i], 3)
                    })
            
            if resultats_cycles:
                df_cycles = pd.DataFrame(resultats_cycles)
                df_cycles.to_csv(os.path.join(output_dir, f"{nom_base}_analyse_cycles.csv"), index=False, encoding='utf-8')

            df_resume = pd.DataFrame([{
                "Fichier_Source": nom_base, "Type_Signal": "Amplitude 3DRespiView Live",
                "Duree_Total_Sec": round(float(x_data[-1]), 2) if len(x_data) > 0 else 0,
                "Total_Cycles": len(peaks), "FR_Moyenne_CPM": round(fr_moyenne_globale, 2),
                "Amplitude_Moyenne": round(np.mean(volume), 2) if len(volume) > 0 else 0
            }])
            df_resume.to_csv(os.path.join(output_dir, f"{nom_base}_resume_global.csv"), index=False, encoding='utf-8')

            racine_dir = os.path.dirname(os.path.abspath(__file__))
            yolo_img_path = os.path.join(racine_dir, 'runs/obb/predict/IR4OBB.jpg')
            if os.path.exists(yolo_img_path):
                photo_destination = os.path.join(output_dir, f"{nom_base}_detection_thorax.jpg")
                shutil.copy(yolo_img_path, photo_destination)
                print(f"[Photo Saved] Image de suivi YOLO copiée vers : {photo_destination}")

        except Exception as e:
            print(f"[Erreur Sauvegarde MKV] Impossible de générer les rapports : {e}")

    return jsonify({
        "Frequence respiratoire (Rpm)": round(fr_moyenne_globale),
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
    """Ferme proprement l'application backend, frontend et leurs terminaux."""
    try:
        racine_dir = os.path.dirname(os.path.abspath(__file__))
        runs_dir = os.path.join(racine_dir, 'runs')
        if os.path.exists(runs_dir):
            shutil.rmtree(runs_dir)
            print("[Nettoyage Final] Répertoire temporaire YOLO supprimé.")
        
        os.system("taskkill /f /im node.exe")
        os.system("taskkill /f /im cmd.exe")

    except Exception as e:
        print(f"Erreur lors de la fermeture forcée : {e}")
    finally:
        os.kill(os.getpid(), 9)

if __name__ == '__main__':
    clean_output_directories()
    app.run(debug=False, host='127.0.0.1', port=8000, threaded=True)